# Copilot / AI Agent Instructions for guard-demo-client

Purpose: Provide concise, actionable guidance so an AI coding agent can be productive immediately in this repo.

Quick Start (developer-focused) ✅
- Recommended: run the unified setup:
  - python -m venv venv && source venv/bin/activate
  - python start_all.py  # installs deps, starts backend (8000) and frontend (3000)
- Manual dev:
  - Backend: python start_backend.py  (FastAPI + uvicorn; reload=True)
  - Frontend: npm install && npm run dev (Vite dev server at :3000)
- Admin Console: http://localhost:3000/admin — set `OpenAI` and `Lakera` API keys here.

Big-picture architecture ✨
- Frontend: `src/` (Vite + React + TypeScript + Tailwind)
- Backend: `backend/` (FastAPI)
  - `backend/main.py` – FastAPI app & routes
  - `backend/agent.py` – ReAct-style agent orchestrator (RAG, tools, Lakera checks)
  - `backend/toolhive.py` – Builds OpenAI tools manifest and executes MCP/HTTP tools
  - `backend/rag.py` – ChromaDB integration and chunking logic
  - `backend/openai_client.py` – Central OpenAI wrapper (loads API key from DB)
- Data: SQLite at `data/agentic_demo.db`; Chroma vectors at `data/chroma/`

Important developer workflows & conventions 🔧
- Configuration is stored in the DB model `AppConfig` — `openai_client._load_config()` reloads runtime keys.
- Temperature is exposed as 0–10 in UI and converted to 0–1 by dividing by 10 in `openai_client.py`.
- ChromaDB telemetry is intentionally disabled (`CHROMA_TELEMETRY_ENABLED = "false"`) in startup scripts.
- RAG chunking is deliberate: CSV/JSON/Markdown/PDF have specialized chunkers and summary chunks are prioritized for count queries. See `backend/rag.py` for chunking rules and `retrieve()` behavior.

Agent & Tooling specifics 🧭
- Tools manifest: `toolhive.openai_tools_manifest(db)` produces OpenAI-compatible function tools and includes `_tool_metadata` for execution.
- Tool execution: `toolhive.execute(...)` standardizes results into a `{status, content_string, raw_result}` shape used by `agent.run_agent`.
- Tool messages must be appended as role:`"tool"` messages (not system messages). The design doc `designdocs/tool_integration_refactor.md` documents expectations; follow it when changing tool flow.
- MCP vs HTTP tools: both supported; `toolhive` attempts discovery then direct calls; it gracefully falls back to prompts if no tools found.

Lakera Guard rules & placement 🛡️
- Pre-check: agent runs `lakera.check_interaction()` on user input (user-only messages) and can block if `cfg.lakera_blocking_mode` is enabled.
- Post-check: agent runs Lakera on the assistant response (user+assistant messages) and replaces/blocks the output when flagged and in blocking mode.
- Do NOT include system prompts in Lakera pre/post checks (the code intentionally uses only user or user+assistant messages).

Code patterns & gotchas ⚠️
- OpenAI usage: `openai_client.chat_completion(messages, model, temperature, tools)` — pass `tools` produced by `toolhive` and rely on `tool_choice: auto`.
- Embeddings: `openai_client.get_embeddings()` uses `text-embedding-ada-002`.
- Avoid logging-sensitive data: Admin keys live in DB; do not commit them.
- Tests: repo has no automated test suite; add tests near the feature touched and update `README.md` & `designdocs` if behavior changes.

Where to look / edit for common tasks 🗂️
- Add/change agent logic: `backend/agent.py`
- Change tool manifest behavior: `backend/toolhive.py` and `designdocs/tool_integration_refactor.md`
- Adjust RAG behavior: `backend/rag.py`
- Configure runtime keys: use Admin Console at `/admin` or update `AppConfig` directly in DB

PR & documentation rules 📣
- If changing agent/tool contracts, update `designdocs/tool_integration_refactor.md` and `designdocs/ARCHITECTURE.md` with rationale and examples.
- Keep edits small and focused: include a short description of why the change is needed (security, correctness, UX).

Examples (exact commands) ▶️
- Start everything: `python start_all.py`
- Start backend only: `python start_backend.py` (dev reload)
- Start frontend only: `npm run dev`
- Upload docs for RAG: POST to `/rag/upload` (see `README.md` endpoints)

Code snippets & patterns 🧩
- Lakera usage (pre-check):

```python
lakera_messages = [{"role": "user", "content": user_message}]
await lakera.check_interaction(messages=lakera_messages, api_key=cfg.lakera_api_key, project_id=cfg.lakera_project_id)
```

- Tool manifest shape (from `toolhive.openai_tools_manifest`):

```json
{
  "type": "function",
  "function": {"name": "tool_name", "description": "...", "parameters": {...}},
  "_tool_metadata": {"db_tool_id": 1, "db_tool_name": "tool_name", "db_tool_endpoint": "https://..."}
}
```

- Tool execution returns standardized shape from `toolhive.execute`:

```json
{ "status": "success", "content_string": "...", "raw_result": {...} }
```

- RAG: CSV/JSON/Markdown chunkers create a summary chunk (e.g., `csv_summary`, `json_summary`, `markdown_summary`) that the retrieval logic prioritizes for count/stat queries. See `backend/rag.py`.

Feedback
- If anything is missing or unclear, tell me which area you'd like expanded (agent flow, tools, Lakera, RAG, or startup). I'll iterate quickly.

--
(Automatically generated summary for AI contributors — keep it concise and repository-specific.)