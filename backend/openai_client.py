from typing import Any, Dict, List, Optional, Tuple

import httpx
import openai
from sqlalchemy.exc import OperationalError

from .database import get_db
from .models import AppConfig


class OpenAIClient:
    def __init__(self):
        self.client = None
        self.embedding_client = None
        self.provider = "openai"
        self.base_url = None
        self.embedding_base_url = None
        self.api_key = None
        self.api_version = None
        self.embedding_api_version = None
        self.model = "gpt-4o-mini"
        self.embedding_model = "text-embedding-3-small"

    def _resolve_config(
        self, config: Optional[AppConfig]
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], str, Optional[str]]:
        provider = ((getattr(config, "llm_provider", None) or "openai") if config else "openai").strip().lower()
        api_key = getattr(config, "llm_api_key", None) if config else None
        if api_key is None and config:
            api_key = getattr(config, "openai_api_key", None)
        base_url = (getattr(config, "llm_base_url", None) if config else None) or None
        if isinstance(base_url, str):
            base_url = base_url.strip() or None
        embedding_base_url = (getattr(config, "llm_embedding_base_url", None) if config else None) or None
        if isinstance(embedding_base_url, str):
            embedding_base_url = embedding_base_url.strip() or None
        api_version = (getattr(config, "llm_api_version", None) if config else None) or None
        if isinstance(api_version, str):
            api_version = api_version.strip() or None
        embedding_api_version = (getattr(config, "llm_embedding_api_version", None) if config else None) or None
        if isinstance(embedding_api_version, str):
            embedding_api_version = embedding_api_version.strip() or None
        model = (getattr(config, "llm_model", None) if config else None) or (
            getattr(config, "openai_model", None) if config else None
        )
        if not model:
            model = "gpt-4o-mini"

        embedding_model = getattr(config, "llm_embedding_model", None) if config else None
        if isinstance(embedding_model, str):
            embedding_model = embedding_model.strip() or None
        if not embedding_model and provider == "openai":
            embedding_model = "text-embedding-3-small"

        return provider, api_key, base_url, embedding_base_url, api_version, embedding_api_version, model, embedding_model

    def _build_client(self, provider: str, api_key: Optional[str], base_url: Optional[str], api_version: Optional[str]):
        if provider == "azure_openai":
            client_kwargs: Dict[str, Any] = {
                "api_key": api_key or "not-needed",
                "azure_endpoint": base_url,
                "api_version": api_version or "2024-06-01",
            }
            return openai.AzureOpenAI(**client_kwargs) if base_url else None
        if provider == "azure_openai_proxy":
            client_kwargs = {
                "api_key": api_key or "not-needed",
                "base_url": base_url,
                "api_version": api_version or "2024-06-01",
            }
            return openai.AzureOpenAI(**client_kwargs) if base_url else None

        client_kwargs: Dict[str, Any] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        elif base_url:
            client_kwargs["api_key"] = "not-needed"

        if base_url:
            client_kwargs["base_url"] = base_url

        return openai.OpenAI(**client_kwargs) if client_kwargs else None

    def _load_config(self):
        """Load the current OpenAI-compatible LLM configuration from the database."""
        db = next(get_db())
        try:
            config = db.query(AppConfig).first()
            provider, api_key, base_url, embedding_base_url, api_version, embedding_api_version, model, embedding_model = (
                self._resolve_config(config)
            )
            self.provider = provider
            self.api_key = api_key
            self.base_url = base_url
            self.embedding_base_url = embedding_base_url or base_url
            self.api_version = api_version
            self.embedding_api_version = embedding_api_version or api_version
            self.model = model
            self.embedding_model = embedding_model

            self.client = self._build_client(provider, api_key, base_url, api_version)
            self.embedding_client = self._build_client(
                provider, api_key, self.embedding_base_url, self.embedding_api_version
            )
        except OperationalError:
            # Startup can reach this client before app-level schema migrations run.
            self.client = None
            self.embedding_client = None
        finally:
            db.close()

    def _fetch_azure_apim_models(self, api_version: Optional[str]) -> List[str]:
        base_url = self.base_url.rstrip("/") if self.base_url else None
        if not base_url:
            return []

        versions_to_try: List[str] = []
        for candidate in [api_version, "2026-03-05", "2025-04-01-preview"]:
            if candidate and candidate not in versions_to_try:
                versions_to_try.append(candidate)

        headers = {"api-key": self.api_key or "not-needed"}
        for version in versions_to_try:
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    response = client.get(f"{base_url}/models", headers=headers, params={"api-version": version})
                if response.status_code != 200:
                    continue
                payload = response.json()
                data = payload.get("data", []) if isinstance(payload, dict) else []
                models = sorted({item.get("id") for item in data if isinstance(item, dict) and item.get("id")})
                if models:
                    return models
            except Exception:
                continue
        return []

    def get_models_metadata(self, target: str = "chat") -> Dict[str, Any]:
        """Get provider-aware model choices for the active OpenAI-compatible endpoint."""
        self._load_config()

        default_models = {
            "openai": ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
            "ollama": ["llama3.2", "qwen2.5", "mistral-small", "nomic-embed-text"],
            "lmstudio": ["local-model"],
            "llamacpp": ["local-model"],
            "azure_openai": ["deployment-name"],
            "azure_openai_proxy": ["deployment-name"],
            "foundry": ["deployment-name"],
            "custom": [],
        }

        active_client = self.embedding_client if target == "embedding" else self.client
        active_model = self.embedding_model if target == "embedding" else self.model
        active_api_version = self.embedding_api_version if target == "embedding" else self.api_version

        models: List[str] = []
        source = "fallback"
        if self.provider in {"azure_openai", "azure_openai_proxy"}:
            models = self._fetch_azure_apim_models(active_api_version)
            if models:
                source = "endpoint"

        if active_client:
            if not models:
                try:
                    listed = active_client.models.list()
                    models = sorted({item.id for item in listed.data if getattr(item, "id", None)})
                    source = "endpoint"
                except Exception:
                    models = []

        if not models:
            models = list(default_models.get(self.provider, []))

        if active_model and active_model not in models:
            models.insert(0, active_model)

        return {
            "provider": self.provider,
            "target": target,
            "models": models,
            "supports_manual_entry": True,
            "source": source,
        }

    def get_models(self, target: str = "chat") -> List[str]:
        """Get available models for the active OpenAI-compatible endpoint."""
        return self.get_models_metadata(target)["models"]

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Any = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send a chat completion request through the active OpenAI-compatible endpoint."""
        self._load_config()
        if not self.client:
            raise Exception("LLM client not configured")

        # Convert temperature to float and handle string inputs
        try:
            temp_float = float(temperature) if temperature is not None else 0.7
        except (ValueError, TypeError):
            temp_float = 0.7

        normalized_temperature = temp_float / 10.0 if temp_float > 1 else temp_float
        params = {
            "model": model or self.model,
            "messages": messages,
            "temperature": normalized_temperature,
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**params)
        return response.model_dump()

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for text chunks."""
        self._load_config()
        if not self.embedding_client:
            raise Exception("LLM client not configured")
        if not self.embedding_model:
            raise Exception("No embedding model configured for the active LLM provider")

        response = self.embedding_client.embeddings.create(model=self.embedding_model, input=texts)
        return [embedding.embedding for embedding in response.data]


# Global instance
openai_client = OpenAIClient()
