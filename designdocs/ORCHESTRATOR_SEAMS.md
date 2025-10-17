# ORCHESTRATOR_SEAMS.md
_Last updated: 2025-08-29_

This doc freezes the core interfaces between services, so Cursor tasks remain aligned and later features slot in cleanly.

## Agent Orchestrator Flow
1. Receive `/chat` request → AgentRequest
2. Call `rag.retrieve(query)` → list of context docs (may be empty)
3. Call `toolhive.maybe_run_tool(message, enabled_tools)` → tool trace or None
4. Call `openai_client.chat_completion(...)` with context + tool_result
5. Collect assistant output
6. If Lakera enabled → `lakera.check_interaction(messages, meta, api_key)`
7. Return AgentResult

## Python Interfaces

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
# services/rag.py
async def retrieve(query: str, top_k: int = 5) -> list[dict]:
    # returns [{"text": str, "metadata": dict}]

async def ingest_file(path: str, mimetype: str, **meta) -> dict:
    # returns { "source_id": str, "chunks": int, "metadata": meta }

async def generate_seed_pack(industry: str, seed_prompt: str, options: dict, mode: str) -> str:
    # returns markdown preview (string)
```

```python
# services/toolhive.py
async def enabled_tools() -> list[dict]: ...
async def maybe_run_tool(message: str, tools: list[dict]) -> dict | None:
    # returns tool trace or None
```

```python
# services/lakera.py
async def check_interaction(messages: list[dict], meta: dict | None, api_key: str | None, project_id: str | None = None) -> dict | None:
    # returns Lakera JSON result or None
```

## TypeScript Interfaces

```ts
// types.ts
export type ChatResponse = {
  response: string;
  citations: string[];
  tool_traces: any[];
  lakera?: any | null;
};
```

## Frontend Contracts
- `ChatWidget` calls `/chat` → `ChatResponse`
- `LakeraOverlay` polls `/lakera/last`
- `UploadDropzone` calls `/rag/upload`
- `GenerateContentModal` calls `/rag/generate` with preview + ingest flow
- `ToolManager` calls `/tools/*`

---
