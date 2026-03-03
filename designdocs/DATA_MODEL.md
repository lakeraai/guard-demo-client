# Data Model (SQLite)

- `AppConfig`
  - business_name, tagline, hero_text, hero_image_url, logo_url
  - lakera_enabled, openai_model, temperature, system_prompt
  - openai_api_key (encrypted), lakera_api_key (encrypted)

- `Tool`
  - name, description, endpoint, type ("mcp"|"http"), enabled, config_json

- `RagSource`
  - name, file_path, doc_mimetype, chunking_profile
  - source_type ("uploaded"|"generated"), industry, seed_prompt
  - created_at
