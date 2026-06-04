# integrations.md — external-service contracts

Shapes, auth, failure modes. Per-service. See [[lakera-modes]] for which Lakera path runs when.

## Lakera Guard v2 (backend/lakera.py)
- POST https://api.lakera.ai/v2/guard — moderation. Auth: Bearer lakera_api_key.
  payload: {messages[], metadata, project_id, breakdown:true, payload:true, dev_info:true}.
  resp: {flagged, breakdown[], payload[], ...}. UI overlay shape = this.
- POST https://api.lakera.ai/v2/guard/results — confidence levels (monitor-mode UI).
  Mapped to overlay shape by _guard_results_to_overlay_shape. detected = result level ∈
  {l1_confident,l2_very_likely,l3_likely} OR custom_matched.
- system_prompt prepended to messages if provided & no system role present.
- Failure: any exception → returns None (check_interaction) / logged → treated as not-flagged.
  ⚠ Lakera down = fail-OPEN (content passes). Worth knowing for a security demo.
- last result/request cached module-global for /api/lakera/last polling. See [[global-state]].

## OpenAI (backend/llm_client.py)
- openai SDK. chat.completions.create + embeddings.create(text-embedding-ada-002).
- Auth: openai_api_key. tools=manifest, tool_choice="auto" when tools present.
- GPT-5 family: temperature param dropped [[gpt5-temp]].

## LiteLLM proxy (backend/llm_client.py, OpenAI-compatible)
- base_url = litellm_base_url or http://localhost:4000, calls /v1 (chat, embeddings, /v1/models).
- Auth: litellm_virtual_key (may be empty) [[litellm-key]].
- Guardrails via extra_body.guardrails=[name] + extra_body.metadata.
- Failure: APIConnectionError → "LiteLLM proxy unreachable" (is it running?).
  APIStatusError 400 + parseable guardrail payload → LiteLLMGuardrailError(lakera_status) → block UI.
- get_models: key-specific from /v1/models; falls back to STATIC_MODELS on timeout/401/malformed.
- Config: litellm/config.yaml (model routes, guardrails, database_url). Docker image litellm-database.

## MCP / ToolHive (backend/toolhive.py + backend/mcp.py)
- Tools (db) type ∈ mcp|http; both speak MCP JSON-RPC over HTTPTransport or SSETransport.
- methods: initialize, tools/list, tools/call, prompts/list, prompts/call.
- HTTP→SSE autofix [[mcp-autofix]]. Discovery results cached in MCPToolCapabilities.discovery_results
  (path tools_list_params_0.response.result.tools — read by openai_tools_manifest).
- Each successful tool result moderated via Lakera before returning to LLM.
- Error -35/EAGAIN hint = Node stdio non-blocking stdin issue (toolhive.py:19).

## ChromaDB (backend/rag.py)
- PersistentClient(./data/chroma), collection "agentic_demo", cosine. Telemetry disabled.
- reinitialize_chromadb swaps global client/collection after import; verifies count() before swap,
  leaves old client on failure. See gaps.md (mid-swap race).

## Deps of note (SCA)
- openai SDK (used for both OpenAI + LiteLLM via base_url). httpx. chromadb. fastapi. sqlalchemy.
- Python 3.10–3.12 (3.13+ may break pandas). requirements.txt / requirements-dev.txt. ruff for lint.
