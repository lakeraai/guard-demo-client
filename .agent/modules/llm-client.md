---
covers: [backend/llm_client.py]
synced: 94718ea
mode: explore
---
# llm-client — OpenAI ↔ LiteLLM routing

Role: unified LLM façade. chat_completion / get_embeddings / get_models, same sig regardless of
backend. Routes on AppConfig.use_litellm. 350 lns. Uses openai SDK for BOTH (litellm via base_url).

## Key fns
- chat_completion (l.209): route → _call_openai_chat | _call_litellm_chat. temp 0-10→0-1 [[temp-scale]].
- get_embeddings (l.276): text-embedding-ada-002, same routing.
- get_models (l.333): litellm → /v1/models key-specific, else/on-fail STATIC_MODELS (l.17).
- effective_llm_api_key (l.103) / llm_credentials_configured (l.115): key selection [[litellm-key]].
- _supports_custom_temperature (l.32): gpt-5* → drop temperature [[gpt5-temp]].

## Guardrail error handling (litellm block path)
- LiteLLMGuardrailError (l.40): carries lakera_status. Raised when proxy 400 + parseable payload.
- _extract_litellm_guardrail_status (l.69): parse error.lakera_guard_response, OR ast.literal_eval the
  error.message string → lakera_guardrail_response. Brittle (depends on LiteLLM error shape).
- _normalize_litellm_lakera_message_ids (l.48): shift message_id ≥1 down 1 [[msgid-shift]].

## 4 lenses
- State: stateless; loads config via _get_config() (new db session) if not passed.
- Feedback: exceptions re-raised as Exception("LLM API error: ..") — str(e) bubbles to chat response.
- Blast radius: every LLM/embedding call (agent, rag, toolhive multi-step). Backend switch = here.
- Timing: synchronous (openai SDK sync client) called from async fns → blocks event loop. ⚠ not awaited.

## Surprises
- temperature accepted as float|str|int|None; >1.0 assumed 0-10 scale.
- LiteLLM allows empty api_key; OpenAI requires it.
- ast.literal_eval on error message = code smell but works around LiteLLM stringifying dicts.
