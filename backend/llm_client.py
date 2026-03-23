"""
Unified LLM client that routes to OpenAI or LiteLLM proxy based on config.
Exposes chat_completion, get_embeddings, get_models with same signatures as openai_client.
"""
import copy
import os
import ast
import openai
import httpx
from typing import List, Dict, Any, Optional, Union

from .database import get_db
from .models import AppConfig

# Timeout for LiteLLM /v1/models request (seconds)
LITELLM_MODELS_TIMEOUT = 10.0
# OpenAI allows up to 2048 inputs per request; smaller batches reduce timeouts and proxy payload issues.
_DEFAULT_EMBEDDING_BATCH = 128
LITELLM_EMBEDDINGS_CANDIDATES = [
    "text-embedding-ada-002",
    "text-embedding-3-small",
    "text-embedding-3-large",
]

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


class LiteLLMGuardrailError(Exception):
    """Raised when LiteLLM blocks a chat request via guardrails."""

    def __init__(self, message: str, lakera_status: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.lakera_status = lakera_status or {}


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
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
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
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "tools": tools,
        "tool_choice": "auto" if tools else None,
    }
    extra_body: Dict[str, Any] = {}
    if litellm_guardrail_name:
        extra_body["guardrails"] = [litellm_guardrail_name]
    if litellm_metadata:
        extra_body["metadata"] = litellm_metadata
    if extra_body:
        params["extra_body"] = extra_body
    params = {k: v for k, v in params.items() if v is not None}
    response = client.chat.completions.create(**params)
    return response.model_dump()


def _normalize_litellm_lakera_message_ids(status: Dict[str, Any]) -> Dict[str, Any]:
    """
    LiteLLM's Lakera guardrail responses use message_id values one higher than direct
    Lakera Guard API (e.g. user=2/assistant=3 vs user=1/assistant=2). The UI maps ids
    assuming direct Lakera indexing (0=system, 1=user, 2=assistant, ...).
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
    Parse LiteLLM 400 guardrail error payload into Lakera-shaped status.
    LiteLLM currently nests this as a Python dict string in error.message.
    """
    try:
        payload = e.response.json() if e.response is not None else {}
    except Exception:
        payload = {}

    error_obj = payload.get("error") if isinstance(payload, dict) else None
    raw_message = error_obj.get("message") if isinstance(error_obj, dict) else None
    if not isinstance(raw_message, str) or not raw_message.strip():
        return None

    parsed_obj: Optional[Dict[str, Any]] = None
    text = raw_message.strip()
    for parser in (ast.literal_eval,):
        try:
            candidate = parser(text)
            if isinstance(candidate, dict):
                parsed_obj = candidate
                break
        except Exception:
            continue

    if not parsed_obj:
        return None

    lakera_status = parsed_obj.get("lakera_guardrail_response")
    if isinstance(lakera_status, dict):
        return _normalize_litellm_lakera_message_ids(lakera_status)
    return None


def _embedding_batch_size() -> int:
    raw = (os.getenv("EMBEDDING_BATCH_SIZE", "") or "").strip()
    if raw:
        try:
            n = int(raw)
            return max(1, min(n, 2048))
        except ValueError:
            pass
    return _DEFAULT_EMBEDDING_BATCH


def _embedding_dimensions_for_model(model: str) -> Optional[int]:
    """
    Optional EMBEDDING_DIMENSIONS (int) for text-embedding-3-* so vectors match an existing
    Chroma collection (e.g. 1536 to align with ada-002-sized indexes).
    """
    if "embedding-3" not in model.lower():
        return None
    raw = (os.getenv("EMBEDDING_DIMENSIONS", "") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _embedding_vectors_sorted(response: Any) -> List[List[float]]:
    """Map API embedding list back to input order (index field is not guaranteed sorted)."""
    data = getattr(response, "data", None) or []
    ordered = sorted(data, key=lambda e: getattr(e, "index", 0))
    return [list(e.embedding) for e in ordered]


def _embed_texts_batched(
    client: openai.OpenAI,
    model: str,
    texts: List[str],
) -> List[List[float]]:
    if not texts:
        return []
    dims = _embedding_dimensions_for_model(model)
    bs = _embedding_batch_size()
    out: List[List[float]] = []
    for i in range(0, len(texts), bs):
        batch = texts[i : i + bs]
        params: Dict[str, Any] = {"model": model, "input": batch}
        if dims is not None:
            params["dimensions"] = dims
        response = client.embeddings.create(**params)
        out.extend(_embedding_vectors_sorted(response))
    return out


def _get_embeddings_openai(texts: List[str], api_key: str) -> List[List[float]]:
    """Get embeddings from OpenAI directly (batched)."""
    model = (os.getenv("OPENAI_EMBEDDING_MODEL", "") or "").strip() or "text-embedding-ada-002"
    client = openai.OpenAI(api_key=api_key)
    return _embed_texts_batched(client, model, texts)


def _get_embeddings_litellm(
    texts: List[str], api_key: str, base_url: str
) -> List[List[float]]:
    """Get embeddings from LiteLLM proxy using an available embedding model."""
    client = openai.OpenAI(api_key=api_key, base_url=f"{base_url.rstrip('/')}/v1")
    explicit = (os.getenv("LITELLM_EMBEDDING_MODEL", "") or "").strip() or None
    candidates = [explicit] if explicit else []
    if not explicit:
        candidates.extend(LITELLM_EMBEDDINGS_CANDIDATES)
        available = _get_models_litellm(api_key=api_key, base_url=base_url) or []
        dynamic = [m for m in available if "embedding" in m.lower()]
        for model in dynamic:
            if model not in candidates:
                candidates.append(model)

    last_error: Optional[Exception] = None
    for model_name in [c for c in candidates if c]:
        try:
            return _embed_texts_batched(client, model_name, texts)
        except openai.APIStatusError as e:
            last_error = e
            continue
        except openai.APIConnectionError as e:
            raise Exception(
                f"LiteLLM proxy unreachable: {e}. Is LiteLLM running on {base_url}?"
            ) from e

    if explicit:
        raise Exception(
            f"LiteLLM embedding model '{explicit}' failed. "
            "Set LITELLM_EMBEDDING_MODEL to a valid embedding model route."
        ) from last_error
    raise Exception(
        "No usable embedding model found for LiteLLM. "
        "Configure an embedding-capable model route or set LITELLM_EMBEDDING_MODEL."
    ) from last_error


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
                raise LiteLLMGuardrailError("LiteLLM guardrail blocked this response.", lakera_status=lakera_status) from e
        raise Exception(f"LLM API error: {e}") from e


def get_embeddings(texts: List[str], config: Optional[AppConfig] = None) -> List[List[float]]:
    """Get embeddings for text chunks. Routes to OpenAI or LiteLLM based on config."""
    if not texts:
        return []
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
