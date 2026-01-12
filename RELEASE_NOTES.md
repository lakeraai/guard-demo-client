# Release note — Lakera system-prompt and cleanup (2026-01-12)

- **Fix**: Ensure the Admin-configured **System Prompt** is included in all Lakera Guard API calls (pre-input, post-response, RAG scanning, and tool moderation).
  - Files changed: `backend/lakera.py`, `backend/agent.py`, `backend/rag.py`, `backend/toolhive.py`, `backend/main.py`.
  - Behavior: The system prompt (from Admin UI) is prepended to messages sent to Lakera unless a `system` role is already present. Added logging and a debug endpoint (`GET /api/lakera/last_request`) to inspect the last request payload.

- **Notes**: The change was pushed to `main` and a small PR/merge commit records the work.