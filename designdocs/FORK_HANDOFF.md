# Fork Handoff

## Summary

This fork adds provider-aware LLM configuration and admin UI support for:

- OpenAI
- Custom OpenAI-compatible endpoints
- Ollama
- LM Studio
- llama.cpp
- Azure OpenAI
- Azure OpenAI Proxy / APIM-style hybrids

It also adds separate embedding configuration so chat and embeddings can use:

- different base URLs
- different API versions
- different model/deployment names

## Backend Changes

- Generalized LLM config persisted in `app_config`
- Added DB migrations for new LLM fields
- Added provider-aware client creation in `backend/openai_client.py`
- Added separate embedding client support
- Added Azure OpenAI and Azure proxy/APIM modes
- Added APIM-aware model discovery using `GET /models`
- Fixed request-time model selection so stale prompt overrides do not silently force unsupported models
- Added chat model selection logging for debugging
- Disabled noisy Chroma telemetry logging

## Admin UI Changes

- Added provider selector and provider-specific guidance
- Added:
  - Base URL
  - Embedding Base URL
  - API Version
  - Embedding API Version
  - Chat Model
  - Embedding Model
- Added separate model discovery for chat vs embeddings
- Debounced endpoint model lookup to avoid requests on every keystroke
- Switched API version inputs to save on blur so they are editable
- Stacked LLM settings vertically for cleaner layout

## Demo Prompt Changes

- Prompt overrides now only apply when valid for the active provider/model list
- Cleared stale `gpt-3.5-turbo` prompt overrides from the local demo database

## Verification

Validated during implementation with:

- `python -m compileall backend`
- `npm run build`

## Push Prep

Recommended push flow:

```bash
git remote add fork <your-fork-url>
git push -u fork feature/openai-compatible-endpoints
```

If you want the branch opened as a PR against your fork default branch, push the branch first and open the PR from GitHub.
