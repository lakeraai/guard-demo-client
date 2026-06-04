---
covers: [backend/toolhive.py, backend/mcp.py]
synced: 94718ea
mode: explore
---
# toolhive — MCP/HTTP tool execution, discovery, moderation

Role: turn db Tool rows into OpenAI fn manifest, execute tool calls over MCP, moderate results.
toolhive.py 1057 lns + mcp.py transports. Called by [[modules/agent]] + main.py tools routes.

## Key fns
- enabled_tools / get_stored_capabilities / store_capabilities: db Tool + MCPToolCapabilities CRUD.
- openai_tools_manifest (l.87): enabled Tools → OpenAI fn defs. Uses discovery_results
  (path tools_list_params_0.response.result.tools) if present, else basic fallback def. Embeds
  _tool_metadata so execute() needs no db re-lookup.
- execute (l.147): dispatch by tool_info.type (mcp|http) × enable_multi_step → 1 of 4 exec fns.
  Then moderate_tool_response (Lakera) → blocking_mode replaces content w/ canned msg. Stringify result.
- discover_mcp_tool_capabilities_sync (l.623): tools/list + prompts/list, moderate discovery, store.
- moderate_tool_response (l.588): Lakera w/ role "tool".

## ⚠ 4 near-duplicate exec paths (gaps.md 🟠)
execute_mcp_tool · execute_http_tool · execute_mcp_tool_multi_step · execute_http_tool_multi_step
(http_multi_step just delegates to mcp_multi_step). Each repeats: build_transport → mcp_initialize →
try_list → find tool case-insensitive → mcp_call → HTTP→SSE autofix [[mcp-autofix]]. Fix-one-miss-others.
multi_step = inner LLM loop, max_loops=12 safety cap.

## 4 lenses
- State: stateless per call; reads/writes MCPToolCapabilities. Transport opened+closed per call (finally).
- Feedback: heavy print() logs. Errors → {status:error, error, details} dicts, never raised.
- Blast radius: any tool call; manifest shape change ripples to agent tool-call handling.
- Timing: sync mcp calls inside async; multi_step loops LLM↔tool up to 12×. enable_multi_step default
  False in execute() — multi-step paths exist but NOT wired from agent (dead-ish unless called directly).

## Surprises
- enable_multi_step never True from agent.py → multi_step fns are latent. Verify before relying.
- Error -35/EAGAIN → appends Node-stdio hint (l.19).
- moderate only on status==success AND content present; failure of moderation = fail-open.
