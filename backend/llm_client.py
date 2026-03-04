"""
Unified LLM client that routes to OpenAI or LiteLLM proxy based on config.
Exposes chat_completion, get_embeddings, get_models with same signatures as openai_client.
"""
import openai
from typing import List, Dict, Any, Optional, Union

from .database import get_db
from .models import AppConfig


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
) -> Dict[str, Any]:
    """
    Send chat completion request. Routes to OpenAI or LiteLLM based on config.
    temperature: 0-10 scale (converted to 0-1 internally), or float 0-1.
    """
    cfg = config or _get_config()
    if not cfg:
        raise Exception("Configure LLM API key in Admin → Security")

    api_key = cfg.openai_api_key
    if not api_key:
        raise Exception("Configure LLM API key in Admin → Security")

    try:
        temp_float = float(temperature) if temperature is not None else 0.7
    except (ValueError, TypeError):
        temp_float = 0.7
    # Convert 0-10 scale to 0-1 (openai_client behavior)
    if temp_float > 1.0:
        temp_float = temp_float / 10.0

    use_litellm = getattr(cfg, "use_litellm", False)
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
        raise Exception(f"LLM API error: {e}") from e


def get_embeddings(texts: List[str], config: Optional[AppConfig] = None) -> List[List[float]]:
    """Get embeddings for text chunks. Routes to OpenAI or LiteLLM based on config."""
    cfg = config or _get_config()
    if not cfg:
        raise Exception("Configure LLM API key in Admin → Security")

    api_key = cfg.openai_api_key
    if not api_key:
        raise Exception("Configure LLM API key in Admin → Security")

    use_litellm = getattr(cfg, "use_litellm", False)
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


def get_models(config: Optional[AppConfig] = None) -> List[str]:
    """Get available models. Includes OpenAI, LiteLLM proxy models (anthropic-claude, ollama-*), etc."""
    return [
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
