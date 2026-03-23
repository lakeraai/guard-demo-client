from typing import Any, Dict, List, Optional

import httpx

LAKERA_URL = "https://api.lakera.ai/v2/guard"
LAKERA_RESULTS_URL = "https://api.lakera.ai/v2/guard/results"

# /guard/results returns confidence levels; treat these as "hit" for UI (see Lakera docs).
_RESULTS_DETECTED_LEVELS = frozenset(
    {"l1_confident", "l2_very_likely", "l3_likely"}
)

# Global variables to store the last Lakera result and last request payload for debugging
_last_lakera_result: Optional[Dict[str, Any]] = None
_last_lakera_request: Optional[Dict[str, Any]] = None


async def check_interaction(
    messages: List[Dict[str, str]],
    meta: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    project_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check interaction with Lakera Guard
    Returns Lakera JSON result or None

    If `system_prompt` is provided and there's no existing `system` role in `messages`,
    it will be prepended to the messages sent to Lakera.
    """
    global _last_lakera_result

    if not api_key:
        return None

    # Copy messages to avoid mutating caller's list
    msgs = list(messages) if messages else []

    # Insert system prompt if provided and no system message already exists
    if system_prompt and not any(m.get("role") == "system" for m in msgs):
        print("🔔 Including system prompt in Lakera request")
        msgs.insert(0, {"role": "system", "content": system_prompt})

    payload = {
        "messages": msgs,
        "metadata": meta or {},
        "project_id": project_id,
        "breakdown": True,
        "payload": True,
        "dev_info": True,
    }

    # Debug: log the exact messages payload being sent to Lakera
    try:
        print(f"🔎 Lakera payload messages: {msgs}")
    except Exception:
        pass

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        # Store last request payload (without API key) for debugging/inspection
        global _last_lakera_request
        _last_lakera_request = {
            "messages": msgs,
            "project_id": project_id,
            "system_prompt_included": any(m.get("role") == "system" for m in msgs),
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(LAKERA_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

            # Store the last result for the frontend to poll
            _last_lakera_result = result

            return result
    except Exception as e:
        print(f"Lakera API error: {e}")
        return None


def _normalize_results_level(raw: Optional[str]) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def _guard_results_to_overlay_shape(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map POST /v2/guard/results response into the same top-level shape as /v2/guard
    (flagged, breakdown, payload) so LakeraOverlay and ChatWidget keep working.
    """
    rows = raw.get("results")
    if not isinstance(rows, list):
        rows = []
    breakdown: List[Dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        level = _normalize_results_level(item.get("result"))
        detected = level in _RESULTS_DETECTED_LEVELS or bool(item.get("custom_matched"))
        breakdown.append(
            {
                "project_id": item.get("project_id"),
                "policy_id": item.get("policy_id"),
                "detector_id": item.get("detector_id"),
                "detector_type": item.get("detector_type"),
                "detected": detected,
                "message_id": item.get("message_id"),
                "confidence_level": item.get("result"),
            }
        )
    flagged = any(b.get("detected") for b in breakdown)
    return {
        "flagged": flagged,
        "breakdown": breakdown,
        "payload": [],
        "metadata": {
            "source": "lakera_guard_results",
            "note": "From POST /v2/guard/results (not logged as a Guard screening request). "
            "UI uses L1–L3 confidence as highlighted detectors.",
        },
        "dev_info": raw.get("dev_info"),
    }


async def get_guard_results_for_ui(
    messages: List[Dict[str, str]],
    meta: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    project_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call POST /v2/guard/results for detector confidence data without creating a Guard
    screening log entry (per Lakera). Same message shaping as check_interaction.
    Returns guard-shaped dict for the frontend overlay.
    """
    global _last_lakera_result

    if not api_key:
        return None

    msgs = list(messages) if messages else []
    if system_prompt and not any(m.get("role") == "system" for m in msgs):
        msgs.insert(0, {"role": "system", "content": system_prompt})

    payload: Dict[str, Any] = {
        "messages": msgs,
        "metadata": meta or {},
        "dev_info": True,
    }
    if project_id:
        payload["project_id"] = project_id

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        global _last_lakera_request
        _last_lakera_request = {
            "endpoint": "guard/results",
            "messages": msgs,
            "project_id": project_id,
            "system_prompt_included": any(m.get("role") == "system" for m in msgs),
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(LAKERA_RESULTS_URL, json=payload, headers=headers)
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, dict):
                return None
            shaped = _guard_results_to_overlay_shape(raw)
            _last_lakera_result = shaped
            return shaped
    except Exception as e:
        print(f"Lakera /guard/results API error: {e}")
        return None


def get_last_result() -> Optional[Dict[str, Any]]:
    """
    Get the last Lakera result for frontend polling
    """
    return _last_lakera_result


def set_last_result(result: Optional[Dict[str, Any]]) -> None:
    """
    Store a Lakera-shaped moderation result for frontend polling.
    Used when moderation is enforced via LiteLLM guardrails.
    """
    global _last_lakera_result
    _last_lakera_result = result


def get_last_request() -> Optional[Dict[str, Any]]:
    """
    Get the last Lakera request payload (messages, project_id, and whether system_prompt was included)
    This is intended for debugging/inspection and does NOT include sensitive headers or API keys.
    """
    return _last_lakera_request
