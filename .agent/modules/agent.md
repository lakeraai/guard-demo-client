---
covers: [backend/agent.py]
synced: 94718ea
mode: explore
---
# agent — run_agent orchestrator

Role: the chat brain. Coordinates Lakera → RAG → tools → LLM → Lakera. Called only by
/api/chat (main.py:704). 274 lns, single fn run_agent (agent.py:22) + AgentRequest/AgentResult models.

## Flow (see [[architecture]] spine)
0. pre-check user input w/ Lakera (direct mode only; blocking → return canned block msg early)
1. rag.retrieve → context + citations
2. toolhive.openai_tools_manifest(db)
3. llm_client.chat_completion(tools) → if tool_calls: toolhive.execute each → 2nd chat_completion
4. post-check assistant w/ Lakera (direct) OR pull /guard/results (litellm monitor) OR clear stale (litellm)

## 4 Lakera modes decided here — [[lakera-modes]]
use_litellm_guardrails = use_litellm AND lakera_enabled AND lakera_api_key (agent.py:30).
guardrail name = block vs monitor from config (defaults lakera-guard-block/-monitor).
Direct path: check_interaction pre+post. LiteLLM path: name in chat call; block via exception,
monitor via get_guard_results_for_ui, success-clear via set_last_result.

## 4 lenses
- State: stateless per-call EXCEPT writes last-result global via lakera/set_last_result [[global-state]].
- Feedback: print() emoji logs only (🛡️✅⚠️🚫). No metrics. Errors → caught, returned as response text.
- Blast radius: any change to chat behavior; the 4-mode branching is fragile — easy to break one mode.
- Timing: 2 sequential LLM calls when tools fire; Lakera pre/post serial. blocking short-circuits.

## Surprises
- catch LiteLLMGuardrailError (agent.py:257) → canned block msg + surface lakera_status to UI.
- catch generic Exception → returns "I encountered an error: {str(e)}" as the chat response (no raise).
- tool moderation happens INSIDE toolhive.execute, not here. Pre/post checks SKIP system prompt? no —
  check_interaction prepends system_prompt; pre-check sends user only, post sends user+assistant.
