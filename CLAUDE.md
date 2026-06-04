# Operating agreement (router — detail in .agent/)

## How to work
- Think first: state assumptions, surface tradeoffs, propose a baseline when asking.
- Non-trivial → reason state / feedback / blast-radius / timing; can't → flag/defer.
- Verify what code does, don't trust intent/notes/comments. Simplicity first. Surgical: stay in lane.
- Goal-driven: verifiable checks; test oracle = truth. ⚠ NO tests exist here → oracles are manual.
- Full rules: .agent/guidelines.md

## Security (always on)
- Input is malicious: allow-list validate, parameterize, encode. No hardcoded secrets.
- Least privilege; no homemade crypto; bugs cluster at seams. Violate only on my call, w/ risk + alt.
- This is a Lakera Guard DEMO → app deliberately ingests malicious prompts. That intent ≠ license for real holes (plaintext secrets, zip-slip). Full: .agent/security.md

## Memory (.agent/)
- .agent/ = persistent repo memory & cross-agent source of truth. Caveman style (.agent/conventions.md).
  Prefer it over re-reading code & over native auto-memory.
- BEFORE non-trivial work: read .agent/index.md → relevant module/notes.
- AFTER a change (same commit): update affected notes (set `synced`), add to notes.md /
  file a decision as needed, append 1 line to .agent/log.md.
- Capture WHY > restating code. Track weaknesses in .agent/gaps.md.
- Multi-step/multi-agent: add .agent/plan.md + .agent/tasks/ (not present yet). CLAIM before work.
- Detect backend at start: git MCP → CLI → standalone. Run scripts/agent-check before a PR.

## Ops
/recon  /capture  /ask  /plan  /check
Each runs in a work mode (write-scope contract): explore reads code (may write memory) ·
build writes code+notes · review writes findings-only · plan writes roadmap, no code.
Default build. Changing CODE from explore = build, only on my say.

## This repo (1-line)
Lakera Guard sales-demo: FastAPI+SQLite+ChromaDB backend (backend/), Vite/React/TS frontend (src/),
LLM via OpenAI or LiteLLM proxy. Spine: src/ChatWidget → /api/chat → backend/agent.run_agent.
