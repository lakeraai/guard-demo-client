# Frontend Spec

## Pages
- `/` Landing: header (logo, business name, tagline, **Lakera toggle**), hero (image + text), ChatWidget (bottom-right).
- `/admin` Admin: Tabs – Branding, LLM, RAG, Tools, Security, Export/Import.

## Components
- `ChatWidget` – chat UI, calls `/chat`, triggers overlay polling if Lakera ON.
- `LakeraOverlay` – slide-out with status + guardrails + JSON accordion.
- `UploadDropzone` – accepts PDF/MD/TXT/CSV; shows progress + list.
- `ToolManager` – search ToolHive, add/enable/disable, test.
- `KeyInput` – masked fields for OpenAI/Lakera keys.

## LLM model dropdown
- Seed list: `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `o4-mini` (editable).
