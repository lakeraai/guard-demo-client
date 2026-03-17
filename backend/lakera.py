import httpx
from typing import List, Dict, Any, Optional
from .database import get_db
from .models import AppConfig

LAKERA_URL = "https://api.lakera.ai/v2/guard"

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
    
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json"
    }
    
    try:
        # Store last request payload (without API key) for debugging/inspection
        global _last_lakera_request
        _last_lakera_request = {
            "messages": msgs,
            "project_id": project_id,
            "system_prompt_included": any(m.get("role") == "system" for m in msgs)
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

def get_last_result() -> Optional[Dict[str, Any]]:
    """
    Get the last Lakera result for frontend polling
    """
    return _last_lakera_result


def get_last_request() -> Optional[Dict[str, Any]]:
    """
    Get the last Lakera request payload (messages, project_id, and whether system_prompt was included)
    This is intended for debugging/inspection and does NOT include sensitive headers or API keys.
    """
    return _last_lakera_request
