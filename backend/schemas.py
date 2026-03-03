from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# Config schemas
class AppConfigBase(BaseModel):
    business_name: Optional[str] = None
    tagline: Optional[str] = None
    hero_text: Optional[str] = None
    hero_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    lakera_enabled: bool = True
    lakera_blocking_mode: bool = False
    rag_content_scanning: bool = False
    rag_lakera_project_id: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    temperature: int = 7
    system_prompt: Optional[str] = None

class AppConfigResponse(AppConfigBase):
    id: int
    openai_api_key: Optional[str] = None
    lakera_api_key: Optional[str] = None
    lakera_project_id: Optional[str] = None
    rag_lakera_project_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class AppConfigUpdate(AppConfigBase):
    openai_api_key: Optional[str] = None
    lakera_api_key: Optional[str] = None
    lakera_project_id: Optional[str] = None
    rag_lakera_project_id: Optional[str] = None

# Chat schemas
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    lakera: Optional[Dict[str, Any]] = None
    tool_traces: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None

# RAG schemas
class RagGenerateRequest(BaseModel):
    industry: str
    seed_prompt: str
    preview_only: bool = False

class RagGenerateResponse(BaseModel):
    markdown: str
    ingested: bool = False

class RagSearchResponse(BaseModel):
    chunks: List[Dict[str, Any]]

# Tool schemas
class ToolBase(BaseModel):
    name: str
    description: Optional[str] = None
    endpoint: Optional[str] = None
    type: str = "mcp"
    enabled: bool = True
    config_json: Optional[Dict[str, Any]] = None

class ToolResponse(ToolBase):
    id: int
    created_at: datetime
    updated_at: datetime

class ToolCreate(ToolBase):
    pass

class ToolUpdate(ToolBase):
    pass

# Lakera schemas
class LakeraResult(BaseModel):
    result: Dict[str, Any]
    timestamp: datetime

# Demo Prompt schemas
class DemoPromptBase(BaseModel):
    title: str
    content: str
    category: str = "general"
    tags: List[str] = []
    is_malicious: bool = False

class DemoPromptResponse(DemoPromptBase):
    id: int
    usage_count: int
    created_at: datetime
    updated_at: datetime

class DemoPromptCreate(DemoPromptBase):
    pass

class DemoPromptUpdate(DemoPromptBase):
    pass

class DemoPromptSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 10

