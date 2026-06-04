# architecture.md — pieces + request flow

Lakera Guard sales-demo. Skinnable B2B landing + admin console driving an LLM agent; Lakera
content-moderation is the headline feature. Coarse by design (drifts slow).

## Stack
- Frontend: Vite + React + TS + Tailwind. 2 routes (src/App.tsx): `/`=LandingPage, `/admin`=AdminConsole.
- Backend: FastAPI + SQLite (SQLAlchemy) + ChromaDB. All routes in backend/main.py.
- LLM: OpenAI direct OR LiteLLM proxy (localhost:4000) — chat + embeddings. Toggle = AppConfig.use_litellm.
- Vector DB: ChromaDB (data/chroma), collection "agentic_demo", cosine.
- Security: Lakera Guard v2 API (direct) OR LiteLLM-native Lakera guardrails.
- LiteLLM stack: Docker (litellm-database image) + Postgres, auto-bootstrapped by start_all.py.

## Chat spine (the one flow that matters)
```
src/components/ChatWidget.tsx
  → POST /api/chat (main.py:679 chat)
    → run_agent (agent.py:22)
      0. lakera.check_interaction(user msg)          # pre-check; block if blocking_mode
      1. rag.retrieve(message)                        # ChromaDB context + citations
      2. toolhive.openai_tools_manifest(db)           # enabled Tool rows → OpenAI fn defs
      3. llm_client.chat_completion(..tools)          # OpenAI or LiteLLM
         → if tool_calls: toolhive.execute(each)      # MCP/HTTP via mcp.py + per-result Lakera moderate
           → llm_client.chat_completion(2nd, w/ tool results)
      4. lakera.check_interaction(assistant msg)      # post-check; block if blocking_mode
    → ChatResponse{response, lakera, tool_traces, citations}
  → LakeraOverlay polls GET /api/lakera/last          # last moderation result (module-global)
```

## 4 Lakera moderation modes (agent.py decides) — see [[lakera-modes]]
- direct + blocking · direct + monitor · litellm + blocking · litellm + monitor
- direct = lakera.check_interaction (pre+post+tool). litellm = guardrail names passed to proxy,
  block surfaces via LiteLLMGuardrailError, monitor pulls /guard/results for UI.

## Other request groups (all main.py, /api prefix)
- config: GET/PUT /api/config · GET /api/config/export (zip) · POST /api/config/import (zip, v1/v2)
- rag: POST /rag/generate, /rag/upload · GET /rag/search, /rag/sources · DELETE /rag/clear
- tools: CRUD /api/tools · POST /tools/test/{id} (discover MCP caps) · GET /tools/{id}/capabilities
- demo-prompts: CRUD + /search (autocomplete) + /{id}/use (usage_count)
- lakera/rag introspection: /lakera/last, /lakera/last_request, /rag/scanning/last, /rag/scanning/progress
- models: GET /api/models

## Data model (models.py, 5 tables) — see [[modules/backend-api]]
AppConfig (singleton-ish, first() row) · Tool · RagSource · MCPToolCapabilities · DemoPrompt.
Schema evolves via ad-hoc PRAGMA migrations in main.py (no Alembic). data/ gitignored.

## State homes (truth locations)
- config + tools + prompts + rag-source meta → SQLite data/agentic_demo.db
- rag vectors → ChromaDB data/chroma (module-global collection in rag.py)
- last Lakera result/request → MODULE-GLOBAL in lakera.py (NOT db, NOT session) ⚠ [[global-state]]
- last rag-scan result/progress → module-global in rag.py ⚠

## Startup
start_all.py = deps install + Postgres + LiteLLM container + backend(8000) + frontend(3000).
start_backend.py = backend only. Ports: FE 3000, BE 8000, LiteLLM 4000.
