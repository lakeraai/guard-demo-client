#!/usr/bin/env bash
# Full stop then start the demo (same terminal; Ctrl+C stops the stack).
# Optional: pass --postgres to stop_demo_stack.sh --postgres first.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PG_ARGS=()
for arg in "$@"; do
  [[ "$arg" == "--postgres" ]] && PG_ARGS+=(--postgres)
done

if ((${#PG_ARGS[@]} > 0)); then
  "${ROOT}/scripts/stop_demo_stack.sh" "${PG_ARGS[@]}"
else
  "${ROOT}/scripts/stop_demo_stack.sh"
fi

echo "==> Starting stack (python start_all.py)"
exec python -u start_all.py
