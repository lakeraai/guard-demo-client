---
covers: [backend/main.py, backend/models.py, backend/database.py, backend/schemas.py]
synced: 94718ea
mode: explore
---
# backend-api — FastAPI app, routes, models, export/import

Role: HTTP surface. ALL routes live in main.py (no router split). ~1198 lns = god-file, high churn.

## Entry / key
- app = FastAPI (main.py:133). CORS origins localhost:3000/3001, methods/headers "*".
- Base.metadata.create_all at import (main.py:50, also database.py:17).
- Route groups: config · chat (→ [[modules/agent]]) · rag (→ [[modules/rag]]) · tools (→ [[modules/toolhive]])
  · demo-prompts · lakera/rag introspection · models. Full list in [[architecture]].

## Models (models.py) — 5 tables, SQLite data/agentic_demo.db (gitignored)
AppConfig (singleton via .first()) · Tool(type mcp|http, name unique) · RagSource ·
MCPToolCapabilities(tool_id, discovery_results JSON) · DemoPrompt(is_malicious, preferred_llm, usage_count).
database.py: engine, get_db() dependency, check_same_thread=False.

## Migrations — ⚠ ad-hoc, no Alembic
_migrate_* fns (main.py:53-131) = PRAGMA table_info + ALTER ADD COLUMN, run at IMPORT every startup.
Added over time: use_litellm, litellm_base_url, preferred_llm, theme, litellm_virtual_key,
litellm_guardrail_name/_monitor_name. Fragile, implicit order. See gaps.md.

## Export/import (the gnarly part) — [[import-versions]]
- export_config (main.py:221): zip w/ config.json + tools/rag/demo_prompts json + chroma files +
  metadata.json(v2.0, includes[]). Sections = EXPORT_SECTIONS; SAFE_DEFAULT_INCLUDE excludes api_keys+project_ids.
- import_config (main.py:353): v1.0 full-replace vs v2.0 merge-by-section. zipfile.extractall of
  UNTRUSTED zip → zip-slip (gaps.md 🟠). Lots of duplicated insert logic across v1/v2.

## 4 lenses
- State: AppConfig is the config singleton; tools/prompts/rag-meta in same db. Truth = SQLite.
- Feedback: HTTPException detail to client (⚠ leaks str(e) in 500s — info disclosure). No structured logs.
- Blast radius: every UI action hits here; changing AppConfig schema → touch migrations + export sections
  + schemas.py + frontend types. High coupling.
- Timing: migrations at import; create_all idempotent. import_config mutates db in one txn (rollback on err).

## Surprises
- /api/import + /api/export (legacy, main.py:1000) ≠ /api/config/import|export. Legacy = stubs/JSON.
- chat may PERMANENTLY switch config.openai_model if demo prompt has preferred_llm (main.py:687).
- upload allow-list includes application/octet-stream; filename used in path. gaps.md 🟡.
