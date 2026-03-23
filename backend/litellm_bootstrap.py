import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import httpx


DEFAULT_LITELLM_URL = "http://localhost:4000"
DEFAULT_CONFIG_PATH = "litellm/config.yaml"
DEFAULT_LITELLM_IMAGE = "litellm/litellm-database:v1.82.3"
DEFAULT_LITELLM_CONTAINER = "guard-demo-litellm-proxy"
DEFAULT_LITELLM_DOCKER_PLATFORM = "linux/amd64"
DEFAULT_LITELLM_HEALTHCHECK_WAIT_SECS = 120


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


def _docker_available() -> bool:
    return bool(shutil.which("docker"))


def _container_exists(name: str) -> bool:
    result = _run(["docker", "ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"])
    if result.returncode != 0:
        return False
    return any(line.strip() == name for line in result.stdout.splitlines())


def _container_running(name: str) -> bool:
    result = _run(["docker", "inspect", "-f", "{{.State.Running}}", name])
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _runtime_database_url_for_container(database_url: str) -> str:
    host, port, user, password, db_name = _parse_pg_parts(database_url)
    mapped_host = "host.docker.internal" if host in {"localhost", "127.0.0.1"} else host
    return f"postgresql://{user}:{password}@{mapped_host}:{port}/{db_name}"


def _write_runtime_config(config_path: Path) -> Tuple[bool, str, Optional[Path], Optional[str]]:
    original_db = _read_database_url(config_path)
    if not original_db:
        return False, "LiteLLM config is missing database_url.", None, None

    runtime_db = _runtime_database_url_for_container(original_db)
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return False, f"Failed reading LiteLLM config: {e}", None, None

    replaced = False
    out_lines = []
    for line in lines:
        if line.strip().startswith("database_url:"):
            indent = line[: len(line) - len(line.lstrip())]
            out_lines.append(f'{indent}database_url: "{runtime_db}"')
            replaced = True
        else:
            out_lines.append(line)
    if not replaced:
        return False, "LiteLLM config has no database_url field to patch for container runtime.", None, None

    runtime_path = config_path.parent.parent / "data" / "litellm-runtime-config.yaml"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return True, "Prepared LiteLLM runtime config for container.", runtime_path, runtime_db


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
    if not _docker_available():
        return False, "Docker is not installed; cannot start LiteLLM container."

    ok_cfg, cfg_msg, runtime_config, runtime_db = _write_runtime_config(config_path)
    if not ok_cfg:
        return False, cfg_msg

    container_name = os.getenv("LITELLM_DOCKER_CONTAINER", DEFAULT_LITELLM_CONTAINER)
    image = os.getenv("LITELLM_DOCKER_IMAGE", DEFAULT_LITELLM_IMAGE)
    platform = (os.getenv("LITELLM_DOCKER_PLATFORM", DEFAULT_LITELLM_DOCKER_PLATFORM) or "").strip()
    env_file = config_path.parent.parent / ".env"

    if _container_exists(container_name):
        if not _container_running(container_name):
            started = _run(["docker", "start", container_name])
            if started.returncode != 0:
                detail = (started.stderr or started.stdout).strip()
                return False, f"Failed to start LiteLLM container {container_name}: {detail}"
    else:
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            "4000:4000",
            "-v",
            f"{str(runtime_config)}:/app/config.yaml:ro",
            image,
            "--config",
            "/app/config.yaml",
        ]
        if platform:
            cmd[2:2] = ["--platform", platform]
        if env_file.exists():
            cmd[2:2] = ["--env-file", str(env_file)]

        launched = _run(cmd)
        if launched.returncode != 0:
            detail = (launched.stderr or launched.stdout).strip()
            return False, f"Failed to launch LiteLLM container {container_name}: {detail}"

    output_lines: List[str] = []
    wait_secs_raw = (os.getenv("LITELLM_HEALTHCHECK_WAIT_SECS", "") or "").strip()
    try:
        wait_secs = int(wait_secs_raw) if wait_secs_raw else DEFAULT_LITELLM_HEALTHCHECK_WAIT_SECS
    except ValueError:
        wait_secs = DEFAULT_LITELLM_HEALTHCHECK_WAIT_SECS
    wait_secs = max(10, wait_secs)

    for _ in range(wait_secs):
        if is_litellm_running(base_url):
            return True, f"LiteLLM container {container_name} running at {base_url}"
        logs = _run(["docker", "logs", "--tail", "12", container_name])
        if logs.returncode == 0:
            output_lines = [line for line in logs.stdout.splitlines() if line.strip()]
        time.sleep(1)

    tail = "\n".join(output_lines[-12:]).strip()
    extra = f" Output:\n{tail}" if tail else ""
    return (
        False,
        "LiteLLM container did not become healthy at "
        f"{base_url} after {wait_secs}s (runtime db: {runtime_db}).{extra}",
    )


def maybe_bootstrap_litellm(project_root: Path) -> None:
    mode = (os.getenv("DEMO_LITELLM_BOOTSTRAP", "1") or "1").strip().lower()
    if mode in {"0", "false", "off", "no"}:
        print("ℹ️ LiteLLM bootstrap disabled via DEMO_LITELLM_BOOTSTRAP")
        return

    base_url = os.getenv("LITELLM_BASE_URL", DEFAULT_LITELLM_URL)
    config_rel = os.getenv("LITELLM_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    config_path = (project_root / config_rel).resolve()
    if not _docker_available():
        print("ℹ️ Docker not available; skipping LiteLLM container bootstrap")
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
