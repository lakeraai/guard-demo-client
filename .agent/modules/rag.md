---
covers: [backend/rag.py]
synced: 94718ea
mode: explore
---
# rag — ChromaDB retrieval, chunking, embeddings, content scanning

Role: RAG store. Ingest (file/markdown/csv) → chunk → embed → ChromaDB; retrieve for agent context;
optional Lakera content-scanning of ingested material. Contract in [[integrations]].

## Key state/fns
- module-global chroma_client + collection "agentic_demo" (l.25-32), cosine. ⚠ swapped by
  reinitialize_chromadb (l.40) after import (data/chroma_import). Verifies count() before swap, keeps
  old on failure. Mid-swap race → gaps.md 🟠.
- get_chroma_export_path (l.35): current chroma dir (for export zip).
- chunk_text (l.64, 800/200 overlap) · chunk_csv (l.80) · generate_seed_pack · ingest_file/ingest_markdown
  · retrieve(query, top_k) · embeddings via [[modules/llm-client]] get_embeddings.
- scanning result/progress = module-global (l.20-21), polled via /api/rag/scanning/last|progress.

## 4 lenses
- State: vectors in data/chroma (global collection); source meta rows in SQLite RagSource. TWO homes
  for "what's ingested" → can desync (clear handles both, l.773).
- Feedback: scanning progress/result globals for UI; print() on chroma errors. Errors often swallowed.
- Blast radius: retrieve feeds agent context; reinit on import affects all subsequent retrievals.
- Timing: embeddings sync-in-async (blocks loop). Global swap not atomic w/ in-flight requests.

## Surprises
- CHROMA_TELEMETRY_ENABLED=false set as env at import top (l.3) before chromadb import — order matters.
- /api/rag/test-ingest reads literal "test_content.md" from CWD (l.863) — dev-only, fragile path.
- rag_content_scanning config gates Lakera scan of ingested content (separate from chat moderation).
