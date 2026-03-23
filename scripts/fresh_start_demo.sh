#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Stopping existing demo listeners"
./scripts/stop_demo_stack.sh

if [[ ! -d "venv" ]]; then
  echo "==> Creating venv"
  python3 -m venv venv
fi

source venv/bin/activate
echo "==> Starting demo (backend + frontend + LiteLLM container bootstrap)"
python start_all.py
