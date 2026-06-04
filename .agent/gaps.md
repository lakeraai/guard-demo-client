# gaps.md — known weaknesses (inverse of confidence)

Seeded from recon 2026-06-04. Distinct from /check (drift): this = known-risky/unverified code.
Prune as resolved. Line shape: `- [SEV] area | weakness → why | status:`.

## Testing / oracles
- [🔴] whole-repo | ZERO automated tests, no CI workflow → every behavior change verified by hand;
  refactors unsafe; no regression net | status:open
- [🟡] backend | broad `except Exception` + silent `pass` (import, migrations, chroma, lakera) →
  failures swallowed, weak/no oracle, masks bugs | status:open

## Secrets / trust boundary
- [🔴] models.py:13-31 | api keys (openai_api_key, lakera_api_key, litellm_virtual_key) PLAINTEXT in
  SQLite data/agentic_demo.db → leak if db/export shared. Demo-acceptable, deploy-unacceptable | status:open
- [🟠] main.py:367-368 import_config | zipfile.extractall(temp_dir) of UNTRUSTED zip → zip-slip /
  path traversal; also copies into data/chroma_import | status:open
- [🟡] main.py:814-826 rag/upload | content_type allow-list includes application/octet-stream →
  weakens type enforcement; file.filename used in path (os.path.join) → traversal risk | status:open
- [🟡] main.py:136-142 | CORS allow_methods/allow_headers = "*" (origins limited to localhost:3000/3001) | status:open
- [🟡] backend API | NO auth on any endpoint incl admin config/import → anyone w/ network access
  controls keys+config. Intentional for local demo | status:open

## State / coupling (seams)
- [🟠] lakera.py:12-13 | module-global _last_lakera_result/_last_lakera_request shared across ALL
  requests/sessions → cross-session leak + races; /api/lakera/last inherently global. Intentional
  (single-user demo) but footgun for concurrency | status:open
- [🟠] rag.py:25-32 | module-global chroma_client/collection, swapped by reinitialize_chromadb on
  import → in-flight requests may hit stale/new collection mid-swap | status:open
- [🟠] toolhive.py | 4 near-duplicate exec paths (execute_mcp_tool / execute_http_tool / *_multi_step)
  → logic duplicated, drift between them likely; fix one miss the others | status:open
- [🟡] main.py:53-131 | schema migrations = ad-hoc PRAGMA table_info + ALTER at import time, run every
  startup; no migration framework → fragile, ordering implicit | status:open

## Duplication / complexity
- [🟡] main.py import_config | v1.0 (full-replace) vs v2.0 (merge-by-section) paths ~290 lines, much
  duplicated tool/rag/prompt insert logic → high maintenance, easy to diverge | status:open
