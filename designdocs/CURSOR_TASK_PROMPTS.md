# CURSOR_TASK_PROMPTS.md
_Last updated: 2025-08-29_

Paste these one-by-one into Cursor to implement in order.

## Task 1 — OpenAI Integration (Core)
**Goal:** Implement `/chat` with model config, orchestrator hooks for RAG/Tools, and clean return shape.

**Do:**
- Wire `services/openai_client.py` (chat + embeddings helper).
- Implement `services/agent.py::run_agent()` calling:
  1) `rag.retrieve(message)` → `context`
  2) `toolhive.maybe_run_tool(message, enabled_tools())` → `tool_result`
  3) `openai_client.chat_completion(message, context=context, tool_result=tool_result)`
- Return `{ response, citations, tool_traces }` (citations from RAG, traces from tools).
- Frontend: connect `ChatWidget` to `/chat`.

**Definition of Done:**
- Send a prompt; receive a response. No errors when RAG/tools are empty.
- Config (model/temp/system prompt/key) affects responses.

---

## Task 2 — Lakera Guardrails
**Goal:** Add Lakera middleware and overlay wiring.

**Do:**
- Implement `lakera.check_interaction(payload, api_key)`; store `_last`.
- In `agent.run_agent`, after you have `model_output` and `tool_traces`, if enabled:
  - Call Lakera, attach result to response, and cache `_last`.
- Frontend: add top-right toggle; when ON, show `LakeraOverlay` and poll `/lakera/last` after each `/chat` call.

**Definition of Done:**
- Toggle ON → `lakera.check_interaction` called; overlay shows results.
- Toggle OFF → no Lakera calls.

**Reference:** See `docs/LAKERA_MAPPING.md` for schema, models, helper, and UI mapping.

---

## Task 3 — RAG Processing (Retrieval + Seed Packs)
**Goal:** Attach retrieval to chat and implement industry-specific content generation.

**Do:**
- Implement `rag.retrieve(query, top_k=5)` using Chroma and OpenAI embeddings.
- Include `citations` (filenames or `generated:<Industry>` labels) in `/chat` response.
- Implement `/rag/generate` supporting **quick** and **guided** modes (see `docs/SEED_PACKS.md`):
  - **Quick**: auto-fill from Branding + LLM config (business name, tagline, hero text, system prompt).
  - **Guided**: modal form inputs; return preview markdown on `preview_only=true`; persist + ingest when false.
- Frontend Admin → RAG tab: wire “Generate Content” button to modal → preview → ingest.
- Ensure generated sources have provenance metadata and appear in citations.

**Definition of Done:**
- Retrieval works with seeded content in Chroma.
- “Generate Content” produces preview markdown, allows ingest, and appears in retrieval results.

**Reference:** See `SEED_PACKS.md` for request/response schema, UX, and ingestion rules.

---

## Task 4 — File Upload Handling
**Goal:** Ingest uploads into RAG.

**Do:**
- Implement `/rag/upload` with size/type limits.
- In `rag.ingest_file`, parse → chunk → embed → upsert + provenance metadata.
- Frontend: `UploadDropzone` calls upload, shows progress & result.

**Definition of Done:**
- Upload a small file → it appears in `rag.retrieve` results and can be cited in `/chat`.

---

### Additional References
- See `ORCHESTRATOR_SEAMS.md` to keep interfaces stable while implementing Tasks 1–4.
