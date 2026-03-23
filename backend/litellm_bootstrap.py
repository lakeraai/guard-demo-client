import os
import select
import shutil
import socket
import subprocess
import sys
import time
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx


DEFAULT_LITELLM_URL = "http://localhost:4000"
DEFAULT_CONFIG_PATH = "litellm/config.yaml"
DEFAULT_SUBMODULE_PATH = "third_party/litellm"


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _http_status(url: str, timeout: float = 2.0) -> Optional[int]:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url)
        return r.status_code
    except Exception:
        return None


def is_litellm_running(base_url: str = DEFAULT_LITELLM_URL) -> bool:
    status = _http_status(f"{base_url.rstrip('/')}/health")
    # Some LiteLLM configs protect /health with auth; 401/403 still confirms process is up.
    return status in {200, 401, 403}


def _read_database_url(config_path: Path) -> Optional[str]:
    if not config_path.exists():
        return None
    try:
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("database_url:"):
                return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def _parse_pg_parts(database_url: str) -> Tuple[str, int, str, str, str]:
    parsed = urlparse(database_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "litellm"
    password = parsed.password or "litellm"
    db_name = (parsed.path or "/litellm").lstrip("/") or "litellm"
    return host, port, user, password, db_name


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def ensure_postgres(database_url: str, container_name: str) -> Tuple[bool, str]:
    host, port, user, password, db_name = _parse_pg_parts(database_url)
    if _is_port_open(host, port):
        return True, f"Postgres reachable at {host}:{port}"

    if not shutil.which("docker"):
        return False, "Docker is not installed; cannot auto-start Postgres for LiteLLM"

    exists = _run(["docker", "ps", "-a", "--filter", f"name=^/{container_name}$", "--format", "{{.Names}}"])
    if exists.returncode != 0:
        return False, f"Failed to query docker containers: {(exists.stderr or exists.stdout).strip()}"

    names = {n.strip() for n in exists.stdout.splitlines() if n.strip()}
    if container_name in names:
        started = _run(["docker", "start", container_name])
        if started.returncode != 0:
            return False, f"Failed to start Postgres container: {(started.stderr or started.stdout).strip()}"
    else:
        launched = _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-e",
                f"POSTGRES_USER={user}",
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-e",
                f"POSTGRES_DB={db_name}",
                "-p",
                f"{port}:5432",
                "postgres:16-alpine",
            ]
        )
        if launched.returncode != 0:
            return False, f"Failed to create Postgres container: {(launched.stderr or launched.stdout).strip()}"

    for _ in range(30):
        if _is_port_open(host, port, timeout=1.5):
            return True, f"Postgres ready at {host}:{port}"
        time.sleep(1)
    return False, f"Postgres did not become reachable at {host}:{port}"


def ensure_litellm_proxy(config_path: Path, base_url: str) -> Tuple[bool, str]:
    if is_litellm_running(base_url):
        return True, f"LiteLLM already running at {base_url}"
    if not config_path.exists():
        return False, f"LiteLLM config missing at {config_path}"

    submodule_rel = os.getenv("LITELLM_SUBMODULE_PATH", DEFAULT_SUBMODULE_PATH)
    submodule_root = (config_path.parent.parent / submodule_rel).resolve()
    submodule_proxy_cli = submodule_root / "litellm" / "proxy" / "proxy_cli.py"
    if submodule_proxy_cli.exists():
        installed, install_msg = _ensure_submodule_runtime(submodule_root)
        if not installed:
            return False, install_msg
        generated, prisma_msg = _ensure_submodule_prisma_generated(
            submodule_root=submodule_root, database_url=_read_database_url(config_path)
        )
        if not generated:
            return False, prisma_msg
        cmd = [sys.executable, str(submodule_proxy_cli), "--config", str(config_path)]
    elif shutil.which("litellm"):
        cmd = ["litellm", "--config", str(config_path)]
    else:
        cmd = [sys.executable, "-m", "litellm.proxy.proxy_cli", "--config", str(config_path)]

    env: Dict[str, str] = os.environ.copy()
    if sys.platform == "darwin" and not (env.get("HOST") or "").strip():
        env["HOST"] = "::"
    if submodule_proxy_cli.exists():
        existing_py_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{str(submodule_root)}{os.pathsep}{existing_py_path}" if existing_py_path else str(submodule_root)
        )

    try:
        process = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=str(config_path.parent.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
            text=True,
        )
    except OSError as e:
        return False, f"Failed to start LiteLLM process: {e}"

    output_lines: List[str] = []
    for _ in range(45):
        if process.poll() is not None:
            remaining = process.stdout.read() if process.stdout else ""
            if remaining:
                output_lines.extend(remaining.splitlines())
            tail = "\n".join(output_lines[-12:]).strip()
            extra = f" Output:\n{tail}" if tail else ""
            return False, f"LiteLLM exited before health check.{extra}"
        try:
            if process.stdout:
                ready, _w, _x = select.select([process.stdout], [], [], 0)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
        except Exception:
            pass
        if is_litellm_running(base_url):
            return True, f"LiteLLM started at {base_url}"
        time.sleep(1)
    tail = "\n".join(output_lines[-12:]).strip()
    extra = f" Output:\n{tail}" if tail else ""
    return False, f"LiteLLM did not become healthy at {base_url}.{extra}"


def maybe_bootstrap_litellm(project_root: Path) -> None:
    mode = (os.getenv("DEMO_LITELLM_BOOTSTRAP", "1") or "1").strip().lower()
    if mode in {"0", "false", "off", "no"}:
        print("ℹ️ LiteLLM bootstrap disabled via DEMO_LITELLM_BOOTSTRAP")
        return

    base_url = os.getenv("LITELLM_BASE_URL", DEFAULT_LITELLM_URL)
    config_rel = os.getenv("LITELLM_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    config_path = (project_root / config_rel).resolve()
    submodule_rel = os.getenv("LITELLM_SUBMODULE_PATH", DEFAULT_SUBMODULE_PATH)
    submodule_root = (project_root / submodule_rel).resolve()
    submodule_proxy_cli = submodule_root / "litellm" / "proxy" / "proxy_cli.py"

    if not submodule_proxy_cli.exists() and not shutil.which("litellm"):
        print(
            "ℹ️ LiteLLM runtime not found. Initialize submodule with "
            "`git submodule update --init --recursive` or install `litellm` in your venv."
        )
        return

    db_url = _read_database_url(config_path)
    if not db_url:
        print(f"ℹ️ LiteLLM database_url not found in {config_path}; skipping LiteLLM bootstrap")
        return

    pg_container = os.getenv("LITELLM_POSTGRES_CONTAINER", "guard-demo-litellm-postgres")
    ok_db, db_msg = ensure_postgres(db_url, pg_container)
    if ok_db:
        print(f"✅ {db_msg}")
    else:
        print(f"⚠️ {db_msg}")
        return

    ok_proxy, proxy_msg = ensure_litellm_proxy(config_path=config_path, base_url=base_url)
    if ok_proxy:
        print(f"✅ {proxy_msg}")
    else:
        print(f"⚠️ {proxy_msg}")


def _ensure_submodule_runtime(submodule_root: Path) -> Tuple[bool, str]:
    """
    Ensure LiteLLM submodule runtime deps are installed in the active interpreter.
    """
    marker = submodule_root / ".bootstrap_runtime_done"
    if marker.exists() and _submodule_runtime_compatible():
        return True, "LiteLLM submodule runtime already installed."

    install_cmd = [sys.executable, "-m", "pip", "install", "-e", f"{str(submodule_root)}[proxy]"]
    result = subprocess.run(install_cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        tail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-20:])
        return False, f"Failed installing LiteLLM submodule runtime deps.\n{tail}"

    try:
        marker.write_text("ok\n", encoding="utf-8")
    except OSError:
        pass
    return True, "Installed LiteLLM submodule runtime dependencies."


def _openai_runtime_compatible() -> bool:
    """
    LiteLLM submodule expects openai>=2.8.0 and openai.lib._parsing.
    """
    try:
        openai_mod = importlib.import_module("openai")
        version_str = getattr(openai_mod, "__version__", "0.0.0")
        parts = [int(p) for p in version_str.split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        if tuple(parts) < (2, 8, 0):
            return False
        lib = importlib.import_module("openai.lib")
        return hasattr(lib, "_parsing")
    except Exception:
        return False


def _submodule_runtime_compatible() -> bool:
    """OpenAI + proxy-critical deps LiteLLM imports at startup."""
    if not _openai_runtime_compatible():
        return False
    # Keep this list focused on modules that have repeatedly caused proxy boot failures.
    required_modules = ("fastuuid", "orjson", "apscheduler")
    for mod in required_modules:
        try:
            importlib.import_module(mod)
        except ImportError:
            return False
    return True


def _ensure_submodule_prisma_generated(submodule_root: Path, database_url: Optional[str]) -> Tuple[bool, str]:
    """
    Always run prisma generate for the submodule schema when DB URL is set.
    A stale .bootstrap_prisma_done skip caused "Unable to find Prisma binaries" after
    fresh venv installs or dependency changes even though the marker file existed.
    """
    if not database_url:
        return False, "LiteLLM config is missing database_url; cannot run prisma generate."

    schema = submodule_root / "litellm" / "proxy" / "schema.prisma"
    if not schema.exists():
        return False, f"LiteLLM prisma schema missing at {schema}"

    prisma_cmd = [sys.executable, "-m", "prisma", "generate", "--schema", str(schema)]
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(prisma_cmd, capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        tail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-20:])
        return False, f"Failed prisma generate for LiteLLM submodule.\n{tail}"
    return True, "Generated LiteLLM prisma client (submodule)."
