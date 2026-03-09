#!/usr/bin/env bash
# Set up LiteLLM proxy: .env from example (if missing), Prisma client generate, then print next steps.
# Run from project root. Requires: Postgres (you provide), pip install -r requirements.txt already done.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "LiteLLM setup"
echo ""

# 1. Ensure .env exists
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Edit .env (and litellm/config.yaml if your DB URL differs) as needed."
  else
    echo "Create a .env file; see .env.example for UI_USERNAME / UI_PASSWORD. Edit litellm/config.yaml for database_url."
    exit 1
  fi
else
  echo ".env exists"
fi

# 2. Prisma client for LiteLLM proxy
SCHEMA="$(python -c "import site; import os; p=site.getsitepackages()[0]; s=os.path.join(p,'litellm','proxy','schema.prisma'); print(s)" 2>/dev/null)"
if [ -z "$SCHEMA" ] || [ ! -f "$SCHEMA" ]; then
  # Fallback for venv
  for sp in "$ROOT/venv/lib/python"*/site-packages; do
    if [ -f "$sp/litellm/proxy/schema.prisma" ]; then
      SCHEMA="$sp/litellm/proxy/schema.prisma"
      break
    fi
  done
fi
if [ -n "$SCHEMA" ] && [ -f "$SCHEMA" ]; then
  prisma generate --schema="$SCHEMA"
  echo "Generated Prisma client for LiteLLM"
else
  echo "Warning: LiteLLM schema not found. Run: pip install -r requirements.txt (includes litellm[proxy]), then re-run this script."
fi

echo ""
echo "Next steps:"
echo "  1. If your Postgres URL or UI login differs: edit litellm/config.yaml (database_url) and .env (UI_USERNAME, UI_PASSWORD)."
echo "  2. In a new terminal (Terminal 3), run:"
echo "     litellm --config litellm/config.yaml"
echo "  3. Open http://localhost:4000/ui and sign in (UI_USERNAME / UI_PASSWORD from .env)."
