# notes.md — the WHY, surprises, intentional weirdness, domain terms

The gold. Type-(b): not recoverable from reading code. Link anchors used by other notes.

## <a id="global-state"></a>global-state — Lakera/RAG last-result is module-global
lakera.py:12-13 `_last_lakera_result`/`_last_lakera_request`; rag.py:20-21 scan result/progress.
NOT db, NOT session-scoped. WHY: single-user local demo — frontend LakeraOverlay POLLS
GET /api/lakera/last out-of-band (not in the /api/chat response chain) so the overlay can update
after the chat returns. Cost: concurrent users/sessions clobber each other; races. Fine for demo,
footgun if ever multi-user. See gaps.md. set_last_result() = the writer used by litellm paths.

## <a id="lakera-modes"></a>lakera-modes — 4 moderation modes, decided in agent.py
Cross of {direct Lakera API, LiteLLM-native guardrails} × {blocking, monitor}.
- use_litellm_guardrails = use_litellm AND lakera_enabled AND lakera_api_key (agent.py:30).
- DIRECT (not litellm): agent calls lakera.check_interaction pre (user), post (assistant), and per
  tool result (toolhive.moderate_tool_response). blocking_mode → replace content w/ canned block msg.
- LITELLM: guardrail NAME passed to proxy via extra_body.guardrails=[name]. block name vs monitor name
  from config (litellm_guardrail_name / _monitor_name), default "lakera-guard-block"/"lakera-guard-monitor".
  These MUST match litellm/config.yaml. blocking → proxy returns 400 → LiteLLMGuardrailError carries
  detector detail → UI. monitor → agent calls /guard/results separately for UI confidence panel.
- litellm blocking success turn → agent sets a CLEAR result {flagged:false,...source:litellm} so UI
  drops stale red state (agent.py:242-251).

## <a id="msgid-shift"></a>litellm message_id off-by-one
llm_client.py:48 _normalize_litellm_lakera_message_ids. LiteLLM Lakera payload indexes messages +1 vs
direct Lakera indexing the UI expects → shift any message_id ≥ 1 down by one. Pure compatibility glue.

## <a id="temp-scale"></a>temperature is a 0–10 STRING scaled to 0–1
AppConfig.temperature = String default "7" (models.py:23). UI uses 0–10 scale. llm_client.chat_completion:
if temp_float > 1.0 → /10.0 (llm_client.py:237). So "7" → 0.7. Stored as string b/c sqlite/UI quirk.

## <a id="gpt5-temp"></a>GPT-5 family rejects custom temperature
llm_client.py:32 _supports_custom_temperature → name.startswith("gpt-5") → False → temperature param
DROPPED from the call (set None, filtered out). Else OpenAI/LiteLLM 400s. STATIC_MODELS lists gpt-5*.

## <a id="litellm-key"></a>two API-key fields: openai_api_key vs litellm_virtual_key
effective_llm_api_key (llm_client.py:103): use_litellm → litellm_virtual_key (may be ""), else
openai_api_key. LiteLLM mode allows EMPTY virtual key (proxy may not require one);
llm_credentials_configured returns True for litellm regardless. Legacy migration copies old
openai_api_key → litellm_virtual_key for existing litellm rows (main.py:91, import paths).

## <a id="import-versions"></a>config export/import = ZIP, v1.0 vs v2.0
Export always v2 (UI sends ?version=2). v2 = merge-by-section (EXPORT_SECTIONS, main.py:202); only
sections in metadata.includes applied → a "safe" export (no api_keys/project_ids) won't wipe live keys.
v1.0 = legacy full-replace (delete all rows). v1 can read demo_prompts from demo_prompts.json OR from
an embedded data/agentic_demo.db. SAFE_DEFAULT_INCLUDE excludes api_keys + project_ids.

## <a id="mcp-autofix"></a>MCP transport HTTP→SSE autofix
toolhive + mcp.py: build_transport tries HTTP; if RuntimeError hints SSE (SSE_BODY_ON_HTTP /
text/event-stream / "event:") and transport is HTTPTransport → retry with SSETransport. Same pattern
copied across execute_mcp_tool / execute_http_tool / discover / multi_step (the 4 dup paths).

## Domain terms
- "Lakera Guard" = Lakera content-moderation API (api.lakera.ai/v2/guard). "breakdown" = per-detector
  results; "flagged" = any detector hit; "payload" = matched spans.
- "ToolHive" = MCP tool hosting; tools are mcp or http type, both speak MCP over the transport layer.
- "seed pack" = AI-generated RAG content (rag.generate_seed_pack). "demo prompt corpus" = curated
  prompts w/ is_malicious flag for security demos; autocomplete via right-arrow in ChatWidget.
- AppConfig is effectively a SINGLETON: code uses db.query(AppConfig).first() everywhere.
