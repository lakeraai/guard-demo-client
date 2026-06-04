---
covers: [src/]
synced: 94718ea
mode: explore
---
# frontend — Vite/React/TS UI (coarse, one note)

Role: landing page + admin console. Thin over the API; all logic is backend. Coarse on purpose.

## Structure
- src/App.tsx: 2 routes — `/` LandingPage, `/admin` AdminConsole (react-router).
- src/services/api.ts: THE seam — ApiService class, all fetch calls, `/api` base. Mirror of backend routes.
- src/types/index.ts (191 lns): TS mirrors of backend schemas (AppConfig, ChatResponse, LakeraResult, ...).
- pages/LandingPage.tsx (202): branded landing, hosts ChatWidget. AdminConsole.tsx (1417 ⚠ big):
  all config tabs (appearance/llm/security/rag/tools/demo-prompts/export-import).
- components/: ChatWidget (chat + autocomplete) · LakeraOverlay (moderation result panel) ·
  DemoPromptManager · GenerateContentModal · RagManagement · ToolManager · KeyInput · UploadDropzone.

## Key behaviors / surprises
- ChatWidget autocomplete: type ≥2 chars → searchDemoPrompts; RIGHT-ARROW (l.174) completes current
  suggestion. Selecting a prompt w/ preferred_llm → backend switches model (see [[modules/agent]]).
- Lakera overlay: ChatWidget fetches getLastLakeraResult on MOUNT (l.63) + uses lakera from chat
  response. Reads the backend module-global cache [[global-state]] — so overlay reflects last GLOBAL
  result, not strictly this client's. hasLakeraViolations = flagged OR any breakdown.detected.
- Export/import UI in AdminConsole drives zip flow [[import-versions]]; API keys/project_ids OFF by default.

## 4 lenses
- State: server-authoritative; component useState mirrors. AppConfig fetched/PUT round-trips.
- Feedback: errors via api.ts parseError → thrown Error(detail); shown in UI. No client logging.
- Blast radius: api.ts + types must track backend route/schema changes — the cross-cutting coupling.
- Timing: Lakera overlay relies on backend cache timing; concurrent demos could cross results.

## Note: 0 frontend tests. Vite/Tailwind config at repo root (vite/tailwind/postcss/tsconfig).
