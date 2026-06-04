---
covers: [backend/lakera.py]
synced: 94718ea
mode: explore
---
# lakera — Lakera Guard v2 client + UI result cache

Role: moderation calls + the module-global "last result" cache the UI polls. 191 lns.
Contract detail in [[integrations]]. Mode selection in [[modules/agent]] / [[lakera-modes]].

## Key fns
- check_interaction (l.16): POST /v2/guard. Prepends system_prompt if no system role. Returns Lakera
  JSON or None. Caches _last_lakera_result + _last_lakera_request (no api key in request cache).
- get_guard_results_for_ui (l.127): POST /v2/guard/results → _guard_results_to_overlay_shape →
  same overlay shape. Used by litellm MONITOR mode for confidence panel.
- get_last_result / set_last_result / get_last_request: accessors for /api/lakera/last(_request).

## State owned — ⚠ MODULE-GLOBAL
_last_lakera_result, _last_lakera_request (l.12-13). Shared across all requests/sessions. WHY +
consequences: [[global-state]]. This is the seam most likely to surprise.

## 4 lenses
- State: globals = single source for the overlay; NOT per-session. Truth has one (global) home → leak.
- Feedback: print() debug incl full payload messages (l.54). ⚠ may log user content/PII to stdout.
- Blast radius: agent + toolhive + rag scanning all write the cache; UI reads it. Any session interleaving
  corrupts the overlay.
- Timing: overlay polls AFTER chat returns → relies on cache still holding this turn's result.

## Surprises
- FAIL-OPEN: any exception → returns None → caller treats as not-flagged. Lakera down = content passes.
- /guard/results detected levels = {l1_confident,l2_very_likely,l3_likely} OR custom_matched (l.9,102).
