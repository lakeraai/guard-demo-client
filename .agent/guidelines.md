# Behavioral guidelines (full §1–5, caveman)

Router carries compressed version. This = full ref. Policy note, not drift-checked.
Bias caution > speed. Trivial tasks → judgment.

## 1. Think before coding
- Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicit. Uncertain → ask, w/ a baseline hypothesis ("assuming X b/c Y — right?").
- Multiple interpretations → present, don't pick silently. Simpler approach exists → say so, push back.
- Non-trivial → reason 4 lenses BEFORE writing, capture answers as "why" memory:
  - State — where does it live, who owns the one true copy? (truth has one home or it's a rumor)
  - Feedback — where's observability; how would you know this broke?
  - Blast radius — what breaks if you change/delete this? (coupling & fragility)
  - Timing — what order must happen; where are races?
- Can't answer 4 lenses for a change = STOP. flag or defer. Never ship code whose invariants you can't trace.
- Before non-trivial: read index.md → relevant notes. Verify what code ACTUALLY does.
  Note contradicts code = drift → flag, trust neither side.

## 2. Simplicity first
- Min code that solves it. Nothing speculative. No abstractions for single-use. No flexibility unasked.
- No error handling for impossible scenarios (≠ skip input validation — untrusted input IS expected).
- 200 lines could be 50 → rewrite. "Would a senior call this overcomplicated?" yes → simplify.
- Memory too: don't restate code. Simple-looking thing may be simple on purpose — read the why first.

## 3. Surgical changes
- Touch only what you must. Match existing style even if you'd differ.
- Don't improve/refactor adjacent code, comments, formatting. Notice dead code/flaw → mention, don't fix.
- Remove only what YOUR change orphaned. Leave pre-existing dead code unless asked.
- Test: every changed line traces to the request.
- Stay in lane: change needs out-of-scope work → flag dependency & STOP, ask before crossing.
  Awareness of a dependency ≠ obligation to resolve it. Don't re-implement what exists.
- Edit notes surgically — update the section, don't rewrite wholesale.

## 4. Goal-driven execution
- Define success as a check. "fix bug" → "write test reproducing it, make it pass."
- ⚠ THIS REPO HAS NO TESTS. Oracle = manual run / inspection. Weak oracle (status-only, no payload
  check) = gap not coverage → record in gaps.md. Be louder about verification here.
- Multi-step → state brief plan (step → verify: check). Adversarially self-check before claiming done:
  compiles/runs? edge cases? Claim done only when confident; flag deferred.
- Hard debug / non-obvious decision → verified outcome + reasoning becomes decision record or howto.

## 5. Security baseline (always on) — full: security.md
- Treat security as foundational. Bugs cluster at SEAMS: service↔DB, frontend↔backend, async, trust bounds.
- Assume external input malicious: allow-list validate, parameterize queries, output-encode (XSS).
- Never hardcode secrets — env/vault. Never log secrets/PII/stack traces/raw SQL to users.
- Least privilege. No homemade crypto (Argon2id/bcrypt/PBKDF2; TLS).
- Asked to violate → brief Security Warning (risk + secure alt), then do what I decide.
- Reconciliations: simplicity ≠ skip input validation. Surgical ≠ ignore security — in focused task,
  flag adjacent vulns + fix in-scope live vulns in code you touch. Dedicated review = different mode,
  surface every flaw at top severity.
- DEMO CONTEXT: app intentionally moderates/ingests malicious prompts (that's the product). Real
  infra holes (plaintext secrets, zip-slip, global state) are still real — see gaps.md.
