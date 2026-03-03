# Architecture

```
frontend/ (Vite React TS Tailwind)
  routes: / (Landing+Chat), /admin (Admin console)
  components: ChatWidget, LakeraOverlay, AdminForms, ToolManager, RagUploader
backend/ (FastAPI, Python)
  routes: /chat, /tools/*, /rag/*, /config/*, /lakera/*
  services: openai_client, agent_orchestrator, rag_service, lakera_service, toolhive_client
  db: sqlite for config+tools; chroma (local vectors)
```

**Chat Flow:** UI → /chat → Agent (RAG? tools?) → OpenAI → Lakera (if ON) → response + guardrail summary.
**RAG Flow:** Upload or Generate → chunk/embed → Chroma → retrieval at chat time.
**Tools Flow:** ToolHive discovery → tool registry → agent uses tools by simple intent policy.
