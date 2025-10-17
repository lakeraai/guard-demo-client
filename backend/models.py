from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AppConfig(Base):
    __tablename__ = "app_config"
    
    id = Column(Integer, primary_key=True, index=True)
    openai_api_key = Column(String, nullable=True)
    lakera_api_key = Column(String, nullable=True)
    lakera_project_id = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    tagline = Column(String, nullable=True)
    hero_text = Column(String, nullable=True)
    hero_image_url = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    openai_model = Column(String, default="gpt-4o-mini")
    temperature = Column(String, default="7")
    lakera_enabled = Column(Boolean, default=True)
    lakera_blocking_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Tool(Base):
    __tablename__ = "tools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String)  # "mcp" or "http"
    description = Column(Text, nullable=True)
    endpoint = Column(String)
    enabled = Column(Boolean, default=True)
    config_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RagSource(Base):
    __tablename__ = "rag_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    content = Column(Text)
    chunks_count = Column(Integer, default=0)
    source_type = Column(String, default="generated")  # "generated", "uploaded"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MCPToolCapabilities(Base):
    __tablename__ = "mcp_tool_capabilities"
    
    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, index=True)
    tool_name = Column(String, index=True)
    server_name = Column(String)
    session_info = Column(JSON, nullable=True)
    discovery_results = Column(JSON, default={})
    last_discovered = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DemoPrompt(Base):
    __tablename__ = "demo_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    category = Column(String, default="general")  # "general", "security", "tools", "rag", etc.
    tags = Column(JSON, default=[])  # Array of searchable tags
    is_malicious = Column(Boolean, default=False)  # Flag for security testing prompts
    usage_count = Column(Integer, default=0)  # Track popularity
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

