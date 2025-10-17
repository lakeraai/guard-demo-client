# Backend Spec

- `openai_client.py` – chat completion & embeddings helpers
- `rag.py` – file parsing, chunking, embedding, ingest; **generate_seed_pack(industry, prompt)** using OpenAI; returns markdown preview and optionally persists.
- `agent.py` – MVP ReAct loop (RAG intent + tool intent + synthesis)
- `lakera.py` – `check_interaction(payload, api_key)`; stores last result in-memory
- `toolhive.py` – MCP placeholder with mock tools; structured tool schema; simple HTTP tool fallback
