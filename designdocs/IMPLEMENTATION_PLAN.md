# IMPLEMENTATION_PLAN.md
_Last updated: 2025-08-29_

This plan sequences the core features so each layer cleanly composes with the next.

## Order of Work (why this order)
1) **OpenAI Integration (Core Chat + Orchestrator Hooks)**
   - Establishes the core `/chat` path, config, and response streaming. 
   - Defines **stable interfaces** for Lakera, RAG, and Tools so later features plug in without rework.

2) **Lakera Guardrails (Middleware Wrapper + UI Overlay Wiring)**
   - Adds safety gates and the ON/OFF toggle logic *without* disturbing the chat code.
   - Ensures payload shape (prompt, tool traces, model output) is finalized early.

3) **RAG Processing (Query-time Retrieval)**
   - Adds retrieval to the orchestrator (before model call).
   - Can operate immediately with AI-generated Seed Packs (no file upload needed yet).

4) **File Upload Handling (RAG Ingestion)**
   - Adds ingestion pipeline (parse → chunk → embed → persist).
   - Once working, uploaded documents will augment RAG retrieval seamlessly.

> After these four: add MCP/ToolHive execution to the orchestrator and adjust the Lakera payload to include tool traces.

---

## Interfaces to Freeze Early

### Backend (Python, FastAPI)

```python
# services/agent.py
class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None

class AgentResult(BaseModel):
    response: str
    citations: list[str] = []
    tool_traces: list[dict] = []
    lakera_status: dict | None = None

async def run_agent(req: AgentRequest, cfg: AppConfig) -> AgentResult:
    ...
```

```python
# services/lakera.py
async def check_interaction(payload: dict, api_key: str | None) -> dict | None:
    """Return Lakera result or None if disabled/missing key."""
```

```python
# services/rag.py
async def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Return list of docs: {'text': str, 'metadata': dict}."""

async def ingest_file(path: str, mimetype: str, **meta) -> dict:
    """Parse → chunk → embed → upsert. Returns counts and source id."""

async def generate_seed_pack(industry: str, seed_prompt: str) -> str:
    """Return markdown for preview; separate endpoint persists + ingests."""
```

```python
# services/toolhive.py
async def enabled_tools() -> list[dict]:
    ...

async def maybe_run_tool(message: str, tools: list[dict]) -> dict | None:
    """Return {'name':..., 'input':..., 'output':..., 'trace':[...] } or None."""
```

### Frontend (TypeScript)

```ts
// types.ts
export type ChatResponse = {
  response: string;
  citations: string[];
  tool_traces: any[];
  lakera?: any | null;
};
```

---

## Acceptance Criteria per Step

### 1) OpenAI Integration
- `/chat` accepts `{ message, session_id? }` and returns `{ response, citations, tool_traces }`.
- Respects config (model, temperature, system prompt, API key).
- **Hooks present**: calls `rag.retrieve` (no-op ok), `toolhive.maybe_run_tool` (no-op ok), and returns their outputs.
- Unit test for `openai_client.chat_completion` with stubbed dependencies.

### 2) Lakera Guardrails
- If `app_config.lakera_enabled` **and** `lakera_api_key` present:
  - `lakera.check_interaction({prompt, tool_calls, model_output, meta})` is invoked after model/tool steps.
  - Result cached and exposed at `/lakera/last`.
- Frontend toggle triggers overlay; overlay shows overall status + guardrail list + raw JSON accordion.
- Toggle OFF = no calls to Lakera.

### 3) RAG Processing
- `rag.retrieve` returns top-k chunks and citations; the agent concatenates the top chunks into context.
- `/chat` response includes `citations` (filenames or `generated:Industry` labels).
- Unit test: with a seeded Chroma collection, retrieval returns expected chunks.

### 4) File Upload Handling
- `/rag/upload` accepts PDF/MD/TXT/CSV ≤10MB; shows progress in UI; returns source id + counts.
- Ingest pipeline sanitizes & parses safely.
- Uploaded content appears in retrieval results with correct provenance metadata.

---

## Next Steps (post-4)
- **Tools/MCP execution** in agent loop.
- Streaming responses from OpenAI to the chat widget.
- Conversation memory keyed by `session_id`.
- Rate limiting & graceful error handling.
