# index.md — catalog of .agent/ memory

Read this first. Then the relevant note(s). Caveman style — see conventions.md.
Backend: MODE=cli (git). Baseline commit: 94718ea. Run scripts/agent-check before a PR.

## Policy (no frontmatter, not drift-checked)
- [guidelines.md](guidelines.md) — full behavioral rules §1–5
- [security.md](security.md) — security standard + this-repo posture
- [conventions.md](conventions.md) — caveman spec + all file formats

## Global / cross-cutting
- [architecture.md](architecture.md) — pieces + the chat spine + state homes
- [notes.md](notes.md) — WHY / surprises / intentional weirdness / domain terms (the gold)
- [integrations.md](integrations.md) — Lakera v2, OpenAI, LiteLLM, MCP/ToolHive, ChromaDB contracts
- [gaps.md](gaps.md) — known weaknesses (🔴 no tests, plaintext secrets; 🟠 zip-slip, global state, dup paths)

## Module notes (drift-checked vs covers)
- [modules/backend-api.md](modules/backend-api.md) — main.py routes + models + export/import + migrations
- [modules/agent.md](modules/agent.md) — run_agent orchestrator + 4 Lakera modes
- [modules/llm-client.md](modules/llm-client.md) — OpenAI↔LiteLLM routing, guardrail-error parse, temp/gpt-5 quirks
- [modules/lakera.md](modules/lakera.md) — Lakera Guard client + module-global UI cache
- [modules/toolhive.md](modules/toolhive.md) — MCP/HTTP tool exec (4 dup paths) + discovery + moderation
- [modules/rag.md](modules/rag.md) — ChromaDB retrieval/chunking/embeddings/scanning
- [modules/frontend.md](modules/frontend.md) — React UI (coarse); api.ts = the seam

## Not yet present
- decisions/ , howto/ — empty until first non-obvious decision / hard-debug recipe
- plan.md , tasks/ — add when work spans multiple stages/sessions
