import openai
from typing import List, Dict, Any, Optional
import os
from .database import get_db
from .models import AppConfig

class OpenAIClient:
    def __init__(self):
        self.client = None
        self._load_config()
    
    def _load_config(self):
        """Load OpenAI configuration from database"""
        db = next(get_db())
        try:
            config = db.query(AppConfig).first()
            if config and config.openai_api_key:
                self.client = openai.OpenAI(api_key=config.openai_api_key)
        finally:
            db.close()
    
    def get_models(self) -> List[str]:
        """Get available OpenAI models"""
        return [
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4o",
            "gpt-4o-mini", 
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ]
    
    def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "gpt-4o",
        temperature: Any = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send chat completion request"""
        if not self.client:
            raise Exception("OpenAI client not configured")
        
        # Convert temperature to float and handle string inputs
        try:
            temp_float = float(temperature) if temperature is not None else 0.7
        except (ValueError, TypeError):
            temp_float = 0.7
        
        params = {
            "model": model,
            "messages": messages,
            "temperature": temp_float / 10.0,  # Convert 0-10 scale to 0-1
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        response = self.client.chat.completions.create(**params)
        return response.model_dump()
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for text chunks"""
        if not self.client:
            raise Exception("OpenAI client not configured")
        
        response = self.client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts
        )
        return [embedding.embedding for embedding in response.data]

# Global instance
openai_client = OpenAIClient()

