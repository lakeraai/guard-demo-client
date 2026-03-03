# Diff from Upstream / Initial Pull

## Git setup

- **Initial commit:** `ca9c064` (baseline)
- **Upstream:** Not configured. Add when you have the repo URL:

```bash
git remote add upstream <repository-url>
git fetch upstream
git diff upstream/main --stat   # summary
git diff upstream/main          # full diff
```

## Current diff vs initial commit

```bash
git diff HEAD
```

(Empty after initial commit—no uncommitted changes.)

## Changes made in this session (vs hypothetical vanilla pull)

These edits were applied to reach the current vanilla state:

| Area | Change |
|------|--------|
| **litellm/config.yaml** | Minimal config: `forward_client_headers_to_llm_api`, `drop_params`, model list. No Lakera guardrail, no callbacks. |
| **litellm/litellm_hooks.py** | Removed (was StripNonTextForLakeraHandler) |
| **docs/** | `PR_LITELLM_LAKERA_MASKING.md` and `LAKERA_ENTERPRISE_REGEXES.md` moved to `~/coding-todos/lakera-litelmm/` |
| **venv/** | LiteLLM venv patches reverted (lakera_ai_v2.py, guardrails.py). `venv/` is gitignored. |

## Project-specific additions (vs generic template)

- **litellm/** – LiteLLM proxy config
- **scripts/setup_litellm.sh** – LiteLLM setup
- **docs/LAKERA_ENTERPRISE_REGEXES.md** – Lakera custom detector regexes (if present)
- **SETUP_INSTRUCTIONS.md** – Includes LiteLLM setup

## To compare against upstream

1. Add remote: `git remote add upstream <url>`
2. Fetch: `git fetch upstream`
3. Diff: `git diff upstream/main` or `git log upstream/main..HEAD`
