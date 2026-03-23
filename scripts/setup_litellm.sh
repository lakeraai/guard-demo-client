#!/usr/bin/env bash
# Set up LiteLLM proxy container prerequisites: .env from example (if missing), then print next steps.
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

echo ""
echo "Next steps:"
echo "  1. If your Postgres URL or UI login differs: edit litellm/config.yaml (database_url) and .env."
echo "  2. Ensure Docker is running."
echo "  3. Start the full demo stack:"
echo "     source venv/bin/activate && python start_all.py"
echo "  4. Open http://localhost:4000/ui and sign in (UI_USERNAME / UI_PASSWORD from .env)."
