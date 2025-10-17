# LAKERA_MAPPING.md
_Last updated: 2025-08-29_

This doc defines the request/response schema and the UI mapping for the Lakera Guard integration (Task 2).

## Endpoint
`POST https://api.lakera.ai/v2/guard`

## Request Shape (JSON)
```jsonc
{
  "messages": [
    {"role": "system", "content": "You are a helpful AI assistant for healthcare inquiries."},
    {"role": "user", "content": "Is it safe to brush my teeth 8 times a day"},
    {"role": "assistant", "content": "That might be a bit overkill"}
  ],
  "project_id": "project-8541012967",
  "metadata": {
    "user_id": "",
    "ip_address": "123.222.121.009",
    "session_id": "randomuuid"
  },
  "breakdown": true,
  "payload": true,
  "dev_info": true
}
```

### Notes
- `messages` should contain the **full turn** we want to evaluate (system + user + assistant). For pre-response checks, send system + user; for post-response checks, include assistant content.
- Include `project_id` if available; otherwise omit or use a default from config.
- `metadata` can be enriched with your session/user identifiers.
- Set `breakdown=true` to get detector-by-detector results and `payload=true` to include category payloads (if any).

## Response Shape (example, abridged)
```jsonc
{
  "payload": [],
  "flagged": true,
  "dev_info": {
    "git_revision": "e421af45",
    "git_timestamp": "2025-08-27T15:20:16+00:00",
    "model_version": "lakera-guard-1",
    "version": "2.0.242"
  },
  "metadata": {
    "request_uuid": "ce50530c-315c-47db-aba3-35244f0f8a1b"
  },
  "breakdown": [
    {
      "project_id": "project-7539648934",
      "policy_id": "policy-lakera-public",
      "detector_id": "detector-lakera-public-moderated-content",
      "detector_type": "moderated_content/crime",
      "detected": false,
      "message_id": 1
    },
    { "... many more detector results ..." }
  ]
}
```

## Minimal Pydantic Models (Backend)
```python
# schemas.py
from pydantic import BaseModel
from typing import List, Optional, Literal

Role = Literal["system", "user", "assistant"]

class LakeraMessage(BaseModel):
    role: Role
    content: str

class LakeraMeta(BaseModel):
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

class LakeraRequest(BaseModel):
    messages: List[LakeraMessage]
    project_id: Optional[str] = None
    metadata: Optional[LakeraMeta] = None
    breakdown: bool = True
    payload: bool = True
    dev_info: bool = True

class LakeraDetectorResult(BaseModel):
    project_id: Optional[str] = None
    policy_id: Optional[str] = None
    detector_id: Optional[str] = None
    detector_type: Optional[str] = None  # e.g., "prompt_attack", "pii/ip_address"
    detected: bool
    message_id: Optional[int] = None

class LakeraResponse(BaseModel):
    payload: list
    flagged: bool
    dev_info: Optional[dict] = None
    metadata: Optional[dict] = None
    breakdown: List[LakeraDetectorResult] = []
```

## Backend Helper
```python
# services/lakera.py
import httpx
from .config import get_config  # wherever you keep it

LAKERA_URL = "https://api.lakera.ai/v2/guard"

async def check_interaction(messages: list[dict], meta: dict | None, api_key: str | None, project_id: str | None = None):
    if not api_key:
        return None
    payload = {
        "messages": messages,
        "metadata": meta or {},
        "project_id": project_id,
        "breakdown": True,
        "payload": True,
        "dev_info": True,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(LAKERA_URL, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()
```

> **Where to call it:** in `agent.run_agent` **after** you have the assistant output (post-response check). For pre-checks, call before completion with only system+user messages.

## UI Mapping (Overlay)
- **Overall Status Pill**: 
  - `OK` if `flagged == false` and no `detected == true` in `breakdown`
  - `WARN` if `flagged == true` but only low-risk detector types
  - `BLOCK` if specific high-risk detector types are `detected` (policy up to you)
- **Guardrails List** (chips or rows):
  - `detector_type` → `detected` (True/False) → small label (from policy map)
  - Group by **category**: `prompt_attack`, `unknown_links`, `moderated_content/*`, `pii/*`.
- **Raw JSON Accordion**: pretty-print the whole response.
- **Meta Footer**: show `metadata.request_uuid` and `dev_info.version` if present.

## Detector → UX Label Map (example)
```ts
export const DETECTOR_LABELS: Record<string, string> = {
  "prompt_attack": "Prompt Attack",
  "unknown_links": "Unknown Links",
  "moderated_content/crime": "Crime",
  "moderated_content/hate": "Hate",
  "moderated_content/profanity": "Profanity",
  "moderated_content/sexual": "Sexual Content",
  "moderated_content/violence": "Violence",
  "moderated_content/weapons": "Weapons",
  "pii/address": "PII: Address",
  "pii/credit_card": "PII: Credit Card",
  "pii/iban_code": "PII: IBAN",
  "pii/ip_address": "PII: IP Address",
  "pii/us_social_security_number": "PII: SSN"
};
```

## Frontend Call Example
```ts
// after receiving modelOutput from /chat
if (lakeraEnabled) {
  await fetch("/lakera/last"); // or trigger server-side call during /chat and then poll /lakera/last
}
```

## Privacy & Safety
- Do not send secrets or file contents unnecessarily. Send only what Lakera needs to assess safety.
- For RAG, consider sending only the **user prompt** + any **assistant draft** (not the whole retrieved context) if you want to minimize data exposure.
- Redact obvious PII in `metadata` unless required for policy.

## cURL Example (provided)
Included in this repo under `docs/examples/lakera_curl_example.sh`.
