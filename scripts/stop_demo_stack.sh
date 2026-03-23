#!/usr/bin/env bash
# Stop demo processes bound to common ports (LiteLLM, backend, Vite).
# Usage:
#   ./scripts/stop_demo_stack.sh              # kill listeners on 4000, 8000, 3000, 3001
#   ./scripts/stop_demo_stack.sh --postgres # also: docker stop LiteLLM Postgres container
set -euo pipefail

STOP_PG=false
for arg in "$@"; do
  case "$arg" in
    --postgres) STOP_PG=true ;;
    -h|--help)
      echo "Usage: $0 [--postgres]"
      echo "  --postgres  also stop Docker container \$LITELLM_POSTGRES_CONTAINER (default: guard-demo-litellm-postgres)"
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

echo "==> Stopping listeners on 4000 (LiteLLM), 8000 (backend), 3000/3001 (Vite)"
for p in 4000 8000 3000 3001; do
  kill_port "$p"
done

if [[ "$STOP_PG" == true ]]; then
  CONTAINER="${LITELLM_POSTGRES_CONTAINER:-guard-demo-litellm-postgres}"
  if docker info >/dev/null 2>&1; then
    if docker ps -q --filter "name=^/${CONTAINER}$" | grep -q .; then
      echo "==> docker stop ${CONTAINER}"
      docker stop "${CONTAINER}" >/dev/null
    else
      echo "Postgres container ${CONTAINER} not running (skip)"
    fi
  else
    echo "Docker not available; skip --postgres"
  fi
fi

echo "Done. Start again from repo root, e.g.: source venv/bin/activate && python start_all.py"
