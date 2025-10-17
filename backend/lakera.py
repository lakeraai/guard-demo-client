import httpx
from typing import List, Dict, Any, Optional
from .database import get_db
from .models import AppConfig

LAKERA_URL = "https://api.lakera.ai/v2/guard"

# Global variable to store the last Lakera result
_last_lakera_result: Optional[Dict[str, Any]] = None

async def check_interaction(
    messages: List[Dict[str, str]], 
    meta: Optional[Dict[str, Any]] = None, 
    api_key: Optional[str] = None, 
    project_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Check interaction with Lakera Guard
    Returns Lakera JSON result or None
    """
    global _last_lakera_result
    
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
    
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json"
    }
    
    try:
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
