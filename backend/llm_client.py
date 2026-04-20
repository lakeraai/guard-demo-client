"""
Unified LLM client that routes to OpenAI or LiteLLM proxy based on config.
Exposes chat_completion, get_embeddings, get_models with same signatures as openai_client.
"""
import ast
import copy
import openai
import httpx
from typing import List, Dict, Any, Optional, Union

from .database import get_db
from .models import AppConfig

# Timeout for LiteLLM /v1/models request (seconds)
LITELLM_MODELS_TIMEOUT = 10.0

STATIC_MODELS = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "anthropic-claude",
    "ollama-llama",
    "ollama-mistral",
]


def _supports_custom_temperature(model: str) -> bool:
    """
    GPT-5 family currently rejects non-default temperature values on chat completions.
    """
    name = (model or "").strip().lower()
    return not name.startswith("gpt-5")


class LiteLLMGuardrailError(Exception):
    """Raised when LiteLLM guardrails block a response and return detector details."""

    def __init__(self, message: str, lakera_status: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.lakera_status = lakera_status or {}


def _normalize_litellm_lakera_message_ids(status: Dict[str, Any]) -> Dict[str, Any]:
    """
    LiteLLM Lakera payloads can be offset by +1 vs direct Lakera indexing expected by UI.
    Shift message_id >= 1 down by one.
    """
    out = copy.deepcopy(status)

    def shift_entry(entry: Any) -> None:
        if not isinstance(entry, dict):
            return
        mid = entry.get("message_id")
        if isinstance(mid, int) and mid >= 1:
            entry["message_id"] = mid - 1

    for item in out.get("breakdown") or []:
        shift_entry(item)
    for item in out.get("payload") or []:
        shift_entry(item)
    return out


def _extract_litellm_guardrail_status(e: openai.APIStatusError) -> Optional[Dict[str, Any]]:
    """
    Parse LiteLLM 400 guardrail error payload into a Lakera-shaped status object.
    """
    try:
        payload = e.response.json() if e.response is not None else {}
    except Exception:
        payload = {}

    error_obj = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_obj, dict):
        return None

    # Preferred shape
    direct = error_obj.get("lakera_guard_response")
    if isinstance(direct, dict):
        return _normalize_litellm_lakera_message_ids(direct)

    # Some LiteLLM errors embed a Python-dict-like string in error.message
    raw_message = error_obj.get("message")
    if not isinstance(raw_message, str) or not raw_message.strip():
        return None
    try:
        parsed_obj = ast.literal_eval(raw_message.strip())
    except Exception:
        return None
    if not isinstance(parsed_obj, dict):
        return None
    nested = parsed_obj.get("lakera_guardrail_response")
    if isinstance(nested, dict):
        return _normalize_litellm_lakera_message_ids(nested)
    return None


def effective_llm_api_key(cfg: Optional[AppConfig]) -> Optional[str]:
    """
    Bearer / API key for the current mode: direct OpenAI uses openai_api_key;
    LiteLLM proxy uses litellm_virtual_key (may be empty string if unset).
    """
    if not cfg:
        return None
    if getattr(cfg, "use_litellm", False):
        return getattr(cfg, "litellm_virtual_key", None) or ""
    return cfg.openai_api_key


def llm_credentials_configured(cfg: Optional[AppConfig]) -> bool:
    """OpenAI direct mode requires an API key; LiteLLM mode allows an empty virtual key."""
    if not cfg:
        return False
    if getattr(cfg, "use_litellm", False):
        return True
    return bool(cfg.openai_api_key)


def _get_config() -> Optional[AppConfig]:
    """Load config from database"""
    db = next(get_db())
    try:
        return db.query(AppConfig).first()
    finally:
        db.close()


def _call_openai_chat(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    api_key: str,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Call OpenAI API directly for chat completion"""
    client = openai.OpenAI(api_key=api_key)
    effective_temperature = temperature if _supports_custom_temperature(model) else None
    params = {
        "model": model,
        "messages": messages,
        "temperature": effective_temperature,
        "tools": tools,
        "tool_choice": "auto" if tools else None,
    }
    params = {k: v for k, v in params.items() if v is not None}
    response = client.chat.completions.create(**params)
    return response.model_dump()


def _call_litellm_chat(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    api_key: str,
    base_url: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    litellm_guardrail_name: Optional[str] = None,
    litellm_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call LiteLLM proxy for chat completion (OpenAI-compatible API)"""
    client = openai.OpenAI(api_key=api_key, base_url=f"{base_url.rstrip('/')}/v1")
    effective_temperature = temperature if _supports_custom_temperature(model) else None
    extra_body: Dict[str, Any] = {}
    if litellm_guardrail_name:
        # LiteLLM expects guardrails as a list; singular guardrail_name can be forwarded upstream.
        extra_body["guardrails"] = [litellm_guardrail_name]
    if litellm_metadata:
        extra_body["metadata"] = litellm_metadata
    params = {
        "model": model,
        "messages": messages,
        "temperature": effective_temperature,
        "tools": tools,
        "tool_choice": "auto" if tools else None,
        "extra_body": extra_body if extra_body else None,
    }
    params = {k: v for k, v in params.items() if v is not None}
    response = client.chat.completions.create(**params)
    return response.model_dump()


def _get_embeddings_openai(texts: List[str], api_key: str) -> List[List[float]]:
    """Get embeddings from OpenAI directly"""
    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=texts,
    )
    return [embedding.embedding for embedding in response.data]


def _get_embeddings_litellm(
    texts: List[str], api_key: str, base_url: str
) -> List[List[float]]:
    """Get embeddings from LiteLLM proxy"""
    client = openai.OpenAI(api_key=api_key, base_url=f"{base_url.rstrip('/')}/v1")
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=texts,
    )
    return [embedding.embedding for embedding in response.data]


def chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o",
    temperature: Union[float, str, int, None] = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    config: Optional[AppConfig] = None,
    litellm_guardrail_name: Optional[str] = None,
    litellm_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send chat completion request. Routes to OpenAI or LiteLLM based on config.
    temperature: 0-10 scale (converted to 0-1 internally), or float 0-1.
    """
    cfg = config or _get_config()
    if not cfg:
        raise Exception("Configure LLM API key in Admin → Security")

    use_litellm = getattr(cfg, "use_litellm", False)
    if not use_litellm and not cfg.openai_api_key:
        raise Exception("Configure LLM API key in Admin → Security")

    api_key = effective_llm_api_key(cfg) or ""

    try:
        temp_float = float(temperature) if temperature is not None else 0.7
    except (ValueError, TypeError):
        temp_float = 0.7
    # Convert 0-10 scale to 0-1 (openai_client behavior)
    if temp_float > 1.0:
        temp_float = temp_float / 10.0

    litellm_base_url = getattr(cfg, "litellm_base_url", None) or "http://localhost:4000"

    try:
        if use_litellm:
            return _call_litellm_chat(
                messages=messages,
                model=model,
                temperature=temp_float,
                api_key=api_key,
                base_url=litellm_base_url,
                tools=tools,
                litellm_guardrail_name=litellm_guardrail_name,
                litellm_metadata=litellm_metadata,
            )
        else:
            return _call_openai_chat(
                messages=messages,
                model=model,
                temperature=temp_float,
                api_key=api_key,
                tools=tools,
            )
    except openai.APIConnectionError as e:
        if use_litellm:
            raise Exception(
                f"LiteLLM proxy unreachable: {e}. Is LiteLLM running on {litellm_base_url}?"
            ) from e
        raise
    except openai.APIStatusError as e:
        if use_litellm and getattr(e, "status_code", None) == 400:
            lakera_status = _extract_litellm_guardrail_status(e)
            if lakera_status:
                raise LiteLLMGuardrailError("LiteLLM guardrail blocked this response.", lakera_status) from e
        raise Exception(f"LLM API error: {e}") from e


def get_embeddings(texts: List[str], config: Optional[AppConfig] = None) -> List[List[float]]:
    """Get embeddings for text chunks. Routes to OpenAI or LiteLLM based on config."""
    cfg = config or _get_config()
    if not cfg:
        raise Exception("Configure LLM API key in Admin → Security")

    use_litellm = getattr(cfg, "use_litellm", False)
    if not use_litellm and not cfg.openai_api_key:
        raise Exception("Configure LLM API key in Admin → Security")

    api_key = effective_llm_api_key(cfg) or ""

    litellm_base_url = getattr(cfg, "litellm_base_url", None) or "http://localhost:4000"

    try:
        if use_litellm:
            return _get_embeddings_litellm(
                texts=texts,
                api_key=api_key,
                base_url=litellm_base_url,
            )
        else:
            return _get_embeddings_openai(texts=texts, api_key=api_key)
    except openai.APIConnectionError as e:
        if use_litellm:
            raise Exception(
                f"LiteLLM proxy unreachable: {e}. Is LiteLLM running on {litellm_base_url}?"
            ) from e
        raise
    except openai.APIStatusError as e:
        raise Exception(f"LLM API error: {e}") from e


def _get_models_litellm(api_key: str, base_url: str) -> Optional[List[str]]:
    """
    Fetch key-specific models from LiteLLM proxy.
    Returns list of model ids on success, None on failure (malformed response, timeout, 401, etc).
    """
    url = f"{base_url.rstrip('/')}/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        with httpx.Client(timeout=LITELLM_MODELS_TIMEOUT) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError, ValueError):
        return None
    data_list = data.get("data")
    if not isinstance(data_list, list):
        return None
    result = []
    for m in data_list:
        if isinstance(m, dict) and m.get("id"):
            result.append(str(m["id"]))
    return result if result else None


def get_models(config: Optional[AppConfig] = None) -> List[str]:
    """
    Get available models. When using LiteLLM, returns key-specific models from proxy.
    Falls back to static list when not using LiteLLM, or when LiteLLM fetch fails/returns empty.
    """
    cfg = config or _get_config()
    if not cfg:
        return STATIC_MODELS
    use_litellm = getattr(cfg, "use_litellm", False)
    api_key = effective_llm_api_key(cfg)
    if not use_litellm or not api_key:
        return STATIC_MODELS
    litellm_base_url = getattr(cfg, "litellm_base_url", None) or "http://localhost:4000"
    models = _get_models_litellm(api_key=api_key, base_url=litellm_base_url)
    if models:
        return models
    return STATIC_MODELS
