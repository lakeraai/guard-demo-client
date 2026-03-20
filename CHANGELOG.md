# Changelog

## [Unreleased] – LiteLLM Integration & Model Selection

### Added

- **`litellm_virtual_key` on `AppConfig`** – LiteLLM virtual key is stored separately from `openai_api_key`; startup migration copies the old single field into `litellm_virtual_key` once for existing LiteLLM installs.
- **LiteLLM proxy support** – Use either an OpenAI API key or a LiteLLM virtual key (Admin → Security).
- **Unified LLM client** (`backend/llm_client.py`) – Routes chat, embeddings, and model listing to OpenAI or LiteLLM based on config.
- **Key-specific model list** – When using LiteLLM, the model dropdown shows only models allowed for the current virtual key (fetched from `/v1/models`).
- **Auto-pick model on save** – Saving a LiteLLM key with an invalid model (e.g. `gpt-4o-mini` when key only allows `ollama-phi3`) auto-selects the first allowed model.
- **Auto-pick on config import** – Same logic runs when importing a config with LiteLLM or an invalid model for direct OpenAI.
- **Admin UI** – Security tab: "Use LiteLLM proxy" toggle, separate OpenAI vs LiteLLM virtual key inputs (no cross-copy on toggle), optional LiteLLM base URL.
- **LLM tab** – Model dropdown restricted to allowed models; warning if current model is not available.
- **`.env.example`** – Template for LiteLLM UI credentials and optional Lakera/LiteLLM overrides.

### Changed

- **Backend** – Replaced `openai_client.py` with `llm_client.py`; all AI call sites (agent, RAG, toolhive, main) use the unified client.
- **Data model** – Added `use_litellm` and `litellm_base_url` to `AppConfig`; migration runs on startup for existing DBs.
- **Config API** – GET/PUT and export/import include `use_litellm` and `litellm_base_url`.

### Removed

- **`backend/openai_client.py`** – Replaced by `llm_client.py`.

### Fixed

- **401 "key not allowed to access model"** – When using restricted LiteLLM keys, the app no longer uses an invalid model; dropdown and auto-pick ensure a valid model is always selected.

### Dependencies

- LiteLLM proxy must be running and reachable when saving a LiteLLM key (for model fetch and auto-pick).
- PostgreSQL required for LiteLLM (default: `localhost:5433`).
