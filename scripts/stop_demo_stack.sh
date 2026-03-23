#!/usr/bin/env bash
# Stop demo processes bound to common ports (backend, Vite) and LiteLLM containers.
# Usage:
#   ./scripts/stop_demo_stack.sh              # stop LiteLLM container + kill 8000/3000/3001 listeners
#   ./scripts/stop_demo_stack.sh --postgres   # also stop LiteLLM Postgres docker container
#   ./scripts/stop_demo_stack.sh --litellm    # explicit LiteLLM stop (same as default)
set -euo pipefail

STOP_PG=false
STOP_LITELLM=true
for arg in "$@"; do
  case "$arg" in
    --postgres) STOP_PG=true ;;
    --litellm) STOP_LITELLM=true ;;
    -h|--help)
      echo "Usage: $0 [--postgres] [--litellm]"
      exit 0
      ;;
  esac
done

kill_port() {
  local port="$1"
  if lsof -ti "tcp:${port}" >/dev/null 2>&1; then
    lsof -ti "tcp:${port}" | while read -r pid; do
      echo "Stopping PID ${pid} on port ${port}"
      kill -9 "${pid}" 2>/dev/null || true
    done
  else
    echo "No process on port ${port}"
  fi
}

echo "==> Stopping listeners on 8000 (backend), 3000/3001 (Vite)"
for p in 8000 3000 3001; do
  kill_port "$p"
done

if docker info >/dev/null 2>&1; then
  if [[ "$STOP_LITELLM" == true ]]; then
    LITELLM_CONTAINER="${LITELLM_DOCKER_CONTAINER:-guard-demo-litellm-proxy}"
    if docker ps -q --filter "name=^/${LITELLM_CONTAINER}$" | grep -q .; then
      echo "==> docker stop ${LITELLM_CONTAINER}"
      docker stop "${LITELLM_CONTAINER}" >/dev/null
    else
      echo "LiteLLM container ${LITELLM_CONTAINER} not running (skip)"
    fi
  fi
  if [[ "$STOP_PG" == true ]]; then
    PG_CONTAINER="${LITELLM_POSTGRES_CONTAINER:-guard-demo-litellm-postgres}"
    if docker ps -q --filter "name=^/${PG_CONTAINER}$" | grep -q .; then
      echo "==> docker stop ${PG_CONTAINER}"
      docker stop "${PG_CONTAINER}" >/dev/null
    else
      echo "Postgres container ${PG_CONTAINER} not running (skip)"
    fi
  fi
fi

echo "Done. Start again from repo root, e.g.: source venv/bin/activate && python start_all.py"
