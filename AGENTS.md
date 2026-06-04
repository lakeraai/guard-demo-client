# Operating agreement (router — detail in .agent/)

Same workspace as CLAUDE.md. Claude Code auto-loads CLAUDE.md; Cursor/Codex/others load this.
Do not duplicate rules — both point at .agent/.

## How to work
- Think first: state assumptions, surface tradeoffs, propose a baseline when asking.
- Non-trivial → reason state / feedback / blast-radius / timing; can't → flag/defer.
- Verify what code does, don't trust intent/notes/comments. Simplicity first. Surgical: stay in lane.
- Goal-driven: verifiable checks; test oracle = truth. ⚠ NO tests exist here → oracles are manual.
- Full rules: .agent/guidelines.md

## Security (always on)
- Input is malicious: allow-list validate, parameterize, encode. No hardcoded secrets.
- Least privilege; no homemade crypto; bugs cluster at seams. Violate only on my call, w/ risk + alt.
- Lakera Guard DEMO → app deliberately ingests malicious prompts; intent ≠ license for real holes.
- Full: .agent/security.md

## Memory (.agent/)
- .agent/ = persistent repo memory & cross-agent source of truth. Caveman style (.agent/conventions.md).
- BEFORE non-trivial work: read .agent/index.md → relevant module/notes.
- AFTER a change (same commit): update affected notes (set `synced`), add notes.md / decision,
  append 1 line to .agent/log.md. Capture WHY > restating code. Weaknesses → .agent/gaps.md.
- Backend detect at start: git MCP → CLI → standalone. Run scripts/agent-check before a PR.

## Ops
/recon  /capture  /ask  /plan  /check — each runs in a work mode (explore/build/review/plan).
Default build. Changing CODE from explore = build, only on my say.

## This repo (1-line)
Lakera Guard sales-demo: FastAPI+SQLite+ChromaDB backend (backend/), Vite/React/TS frontend (src/),
LLM via OpenAI or LiteLLM proxy. Spine: src/ChatWidget → /api/chat → backend/agent.run_agent.
