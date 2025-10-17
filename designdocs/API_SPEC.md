# API Spec (FastAPI)

## Config
- `GET /config` – returns config (secrets redacted)
- `PUT /config` – update config (accepts secrets)
- `POST /config/export` – download JSON skin
- `POST /config/import` – upload JSON skin (validate & apply)

## Chat
- `POST /chat` – `{ message, session_id? }` → `{ response, lakera?, tool_traces?, citations? }`

## RAG
- `POST /rag/upload` – multipart file → ingest
- `POST /rag/generate` – `{ industry, seed_prompt, preview_only? }` → when preview: generated markdown only; otherwise persist + ingest
- `GET /rag/search?q=` – dev inspection of stored chunks (metadata only)

## Tools
- `GET /tools` / `POST /tools` / `PUT /tools/{id}` / `DELETE /tools/{id}`
- `POST /tools/test/{id}` – run a sample invocation

## Lakera
- `GET /lakera/last` – latest guardrail result stored by backend
