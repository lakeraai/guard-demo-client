import io
import json
import logging
import os
import shutil
import sys
import zipfile
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import lakera, rag
from .agent import AgentRequest, run_agent
from .database import engine, get_db
from .models import AppConfig, Base, DemoPrompt, MCPToolCapabilities, RagSource, Tool
from .openai_client import openai_client
from .schemas import (
    AppConfigResponse,
    AppConfigUpdate,
    ChatRequest,
    ChatResponse,
    DemoPromptCreate,
    DemoPromptResponse,
    DemoPromptUpdate,
    RagGenerateRequest,
    RagGenerateResponse,
    RagSearchResponse,
    ToolCreate,
    ToolResponse,
    ToolUpdate,
)
from .toolhive import (
    discover_mcp_tool_capabilities_sync,
    store_capabilities,
)

# Configure logging to prevent blocking I/O issues
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Create database tables
Base.metadata.create_all(bind=engine)


# Migration: add preferred_llm to demo_prompts if missing (existing DBs)
def _migrate_demo_prompts_preferred_llm():
    with engine.connect() as conn:
        r = conn.execute(text("PRAGMA table_info(demo_prompts)"))
        columns = [row[1] for row in r.fetchall()]
        if "preferred_llm" not in columns:
            conn.execute(text("ALTER TABLE demo_prompts ADD COLUMN preferred_llm VARCHAR"))
            conn.commit()


# Migration: add theme to app_config if missing (for UI theming)
def _migrate_app_config_theme():
    with engine.connect() as conn:
        r = conn.execute(text("PRAGMA table_info(app_config)"))
        columns = [row[1] for row in r.fetchall()]
        if "theme" not in columns:
            conn.execute(text("ALTER TABLE app_config ADD COLUMN theme VARCHAR"))
            # Set a sensible default for existing rows
            conn.execute(text("UPDATE app_config SET theme = 'blue' WHERE theme IS NULL"))
            conn.commit()


_migrate_demo_prompts_preferred_llm()
_migrate_app_config_theme()

app = FastAPI(title="Agentic Demo API", description="Backend API for the Agentic Demo application", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Agentic Demo API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# App Config endpoints
@app.get("/api/config", response_model=AppConfigResponse)
async def get_config(db: Session = Depends(get_db)):
    config = db.query(AppConfig).first()
    if not config:
        # Create default config
        config = AppConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@app.put("/api/config", response_model=AppConfigResponse)
async def update_config(config_update: AppConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(AppConfig).first()
    if not config:
        config = AppConfig()
        db.add(config)

    # Update fields
    for field, value in config_update.dict(exclude_unset=True).items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)
    return config


# Export sections: which config fields belong to which section (for selective export/import)
EXPORT_SECTIONS = {
    "appearance": ["business_name", "tagline", "hero_text", "hero_image_url", "logo_url", "theme"],
    "llm": ["openai_model", "temperature", "system_prompt"],
    "security": ["lakera_enabled", "lakera_blocking_mode"],
    "rag_scanning": ["rag_content_scanning"],
    "api_keys": ["openai_api_key", "lakera_api_key"],
    "project_ids": ["lakera_project_id", "rag_lakera_project_id"],
}
SAFE_DEFAULT_INCLUDE = ["appearance", "llm", "security", "rag_scanning", "demo_prompts", "tools", "rag"]


@app.get("/api/config/export")
async def export_config(include: Optional[str] = None, version: Optional[str] = None, db: Session = Depends(get_db)):
    """Export configuration as a zip file (v2.0 format with metadata.json and section includes).
    Query params: include=appearance,llm,... (comma-separated; omit = safe default); version=2 (UI sends this to request v2 export)."""
    try:
        # Parse include list; empty or missing = safe default
        if include and include.strip():
            included_sections = [s.strip() for s in include.split(",") if s.strip()]
        else:
            included_sections = list(SAFE_DEFAULT_INCLUDE)
        if not included_sections:
            included_sections = list(SAFE_DEFAULT_INCLUDE)

        config = db.query(AppConfig).first()
        config_dict = {}
        if config:
            for section, fields in EXPORT_SECTIONS.items():
                if section not in included_sections:
                    continue
                for field in fields:
                    val = getattr(config, field, None)
                    if hasattr(val, "isoformat"):
                        val = val.isoformat() if val else None
                    config_dict[field] = val
            # Timestamps for reference (not section-gated)
            config_dict["created_at"] = config.created_at.isoformat() if config.created_at else None
            config_dict["updated_at"] = config.updated_at.isoformat() if config.updated_at else None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("config.json", json.dumps(config_dict, indent=2))

            if "tools" in included_sections:
                tools = db.query(Tool).all()
                tools_data = []
                for tool in tools:
                    tool_dict = {
                        "id": tool.id,
                        "name": tool.name,
                        "type": tool.type,
                        "description": tool.description,
                        "endpoint": tool.endpoint,
                        "enabled": tool.enabled,
                        "config_json": tool.config_json,
                        "created_at": tool.created_at.isoformat() if tool.created_at else None,
                        "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
                    }
                    capabilities = db.query(MCPToolCapabilities).filter(MCPToolCapabilities.tool_id == tool.id).first()
                    if capabilities:
                        tool_dict["mcp_capabilities"] = {
                            "id": capabilities.id,
                            "tool_name": capabilities.tool_name,
                            "server_name": capabilities.server_name,
                            "session_info": capabilities.session_info,
                            "discovery_results": capabilities.discovery_results,
                            "last_discovered": capabilities.last_discovered.isoformat()
                            if capabilities.last_discovered
                            else None,
                            "created_at": capabilities.created_at.isoformat() if capabilities.created_at else None,
                            "updated_at": capabilities.updated_at.isoformat() if capabilities.updated_at else None,
                        }
                    tools_data.append(tool_dict)
                zip_file.writestr("tools.json", json.dumps(tools_data, indent=2))

            if "rag" in included_sections:
                rag_sources = db.query(RagSource).all()
                rag_data = []
                for source in rag_sources:
                    rag_dict = {
                        "id": source.id,
                        "name": source.name,
                        "content": source.content,
                        "chunks_count": source.chunks_count,
                        "source_type": source.source_type,
                        "created_at": source.created_at.isoformat() if source.created_at else None,
                        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
                    }
                    rag_data.append(rag_dict)
                zip_file.writestr("rag_sources.json", json.dumps(rag_data, indent=2))
                from .rag import get_chroma_export_path

                chroma_dir = get_chroma_export_path()
                if os.path.exists(chroma_dir):
                    for root, _dirs, files in os.walk(chroma_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, ".")
                            zip_file.write(file_path, arcname)
            else:
                zip_file.writestr("rag_sources.json", "[]")

            if "demo_prompts" in included_sections:
                prompts = db.query(DemoPrompt).all()
                prompts_data = []
                for p in prompts:
                    prompts_data.append(
                        {
                            "title": p.title,
                            "content": p.content,
                            "category": p.category,
                            "tags": p.tags or [],
                            "is_malicious": p.is_malicious,
                            "preferred_llm": getattr(p, "preferred_llm", None),
                        }
                    )
                zip_file.writestr("demo_prompts.json", json.dumps(prompts_data, indent=2))
            else:
                zip_file.writestr("demo_prompts.json", "[]")

            if "tools" not in included_sections:
                zip_file.writestr("tools.json", "[]")

            metadata = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "version": "2.0",
                "description": "Agentic Demo Configuration Export",
                "includes": included_sections,
            }
            zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))

        zip_buffer.seek(0)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"agentic_demo_config_{timestamp}.zip"
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}") from e


@app.post("/api/config/import")
async def import_config(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import configuration from a zip file. Supports v1.0 (full replace) and v2.0 (merge by section)."""
    try:
        if not file.filename.endswith(".zip"):
            raise HTTPException(status_code=400, detail="File must be a .zip file")
        file_content = await file.read()
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_zip_path = os.path.join(temp_dir, "import.zip")
            with open(temp_zip_path, "wb") as f:
                f.write(file_content)
            with zipfile.ZipFile(temp_zip_path, "r") as zip_file:
                zip_file.extractall(temp_dir)

            metadata_path = os.path.join(temp_dir, "metadata.json")
            if not os.path.exists(metadata_path):
                raise HTTPException(status_code=400, detail="Missing metadata.json")
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            version = metadata.get("version", "1.0")
            includes = metadata.get("includes") or []

            if version == "1.0":
                # Legacy: full replace; require all files
                for required in ["config.json", "tools.json", "rag_sources.json"]:
                    if not os.path.exists(os.path.join(temp_dir, required)):
                        raise HTTPException(status_code=400, detail=f"Missing required file: {required}")
                with open(os.path.join(temp_dir, "config.json"), "r") as f:
                    config_data = json.load(f)
                db.query(AppConfig).delete()
                new_config = AppConfig(
                    openai_api_key=config_data.get("openai_api_key"),
                    lakera_api_key=config_data.get("lakera_api_key"),
                    lakera_project_id=config_data.get("lakera_project_id"),
                    rag_lakera_project_id=config_data.get("rag_lakera_project_id"),
                    business_name=config_data.get("business_name"),
                    tagline=config_data.get("tagline"),
                    hero_text=config_data.get("hero_text"),
                    hero_image_url=config_data.get("hero_image_url"),
                    logo_url=config_data.get("logo_url"),
                    system_prompt=config_data.get("system_prompt"),
                    openai_model=config_data.get("openai_model", "gpt-4o-mini"),
                    temperature=config_data.get("temperature", "7"),
                    lakera_enabled=config_data.get("lakera_enabled", True),
                    lakera_blocking_mode=config_data.get("lakera_blocking_mode", False),
                    rag_content_scanning=config_data.get("rag_content_scanning", False),
                )
                db.add(new_config)
                with open(os.path.join(temp_dir, "tools.json"), "r") as f:
                    tools_data = json.load(f)
                db.query(MCPToolCapabilities).delete()
                db.query(Tool).delete()
                for tool_data in tools_data:
                    new_tool = Tool(
                        name=tool_data["name"],
                        type=tool_data["type"],
                        description=tool_data.get("description"),
                        endpoint=tool_data["endpoint"],
                        enabled=tool_data.get("enabled", True),
                        config_json=tool_data.get("config_json", {}),
                    )
                    db.add(new_tool)
                    db.flush()
                    if "mcp_capabilities" in tool_data:
                        cap_data = tool_data["mcp_capabilities"]
                        db.add(
                            MCPToolCapabilities(
                                tool_id=new_tool.id,
                                tool_name=cap_data["tool_name"],
                                server_name=cap_data.get("server_name"),
                                session_info=cap_data.get("session_info"),
                                discovery_results=cap_data.get("discovery_results", {}),
                            )
                        )
                with open(os.path.join(temp_dir, "rag_sources.json"), "r") as f:
                    rag_data = json.load(f)
                db.query(RagSource).delete()
                for rag_source_data in rag_data:
                    db.add(
                        RagSource(
                            name=rag_source_data["name"],
                            content=rag_source_data["content"],
                            chunks_count=rag_source_data.get("chunks_count", 0),
                            source_type=rag_source_data.get("source_type", "generated"),
                        )
                    )
                chroma_source_dir = os.path.join(temp_dir, "data", "chroma")
                if os.path.exists(chroma_source_dir):
                    chroma_import_dir = "data/chroma_import"
                    if os.path.exists(chroma_import_dir):
                        shutil.rmtree(chroma_import_dir)
                    shutil.copytree(chroma_source_dir, chroma_import_dir)
                    try:
                        from .rag import reinitialize_chromadb

                        reinitialize_chromadb(chroma_import_dir)
                    except Exception:
                        pass
                # v1.0: import demo_prompts from demo_prompts.json if present, else from data/agentic_demo.db (old export format)
                prompts_path_v1 = os.path.join(temp_dir, "demo_prompts.json")
                db_path_v1 = os.path.join(temp_dir, "data", "agentic_demo.db")
                if os.path.exists(prompts_path_v1):
                    try:
                        with open(prompts_path_v1, "r") as f:
                            prompts_data_v1 = json.load(f)
                        if isinstance(prompts_data_v1, list):
                            db.query(DemoPrompt).delete()
                            for p in prompts_data_v1:
                                if not isinstance(p, dict):
                                    continue
                                title = p.get("title") or ""
                                content = p.get("content") or ""
                                if not title and not content:
                                    continue
                                db.add(
                                    DemoPrompt(
                                        title=title,
                                        content=content,
                                        category=p.get("category", "general"),
                                        tags=p.get("tags") if isinstance(p.get("tags"), list) else [],
                                        is_malicious=p.get("is_malicious", False),
                                        preferred_llm=p.get("preferred_llm"),
                                    )
                                )
                    except Exception:
                        pass
                elif os.path.exists(db_path_v1):
                    try:
                        import sqlite3

                        conn = sqlite3.connect(db_path_v1)
                        conn.row_factory = sqlite3.Row
                        cur = conn.execute("PRAGMA table_info(demo_prompts)")
                        columns = [row[1] for row in cur.fetchall()]
                        conn.close()
                        if "title" in columns and "content" in columns:
                            conn = sqlite3.connect(db_path_v1)
                            conn.row_factory = sqlite3.Row
                            cur = conn.execute(
                                "SELECT title, content, category, tags, is_malicious FROM demo_prompts"
                                + (", preferred_llm" if "preferred_llm" in columns else "")
                            )
                            rows = cur.fetchall()
                            conn.close()
                            db.query(DemoPrompt).delete()
                            for row in rows:
                                r = dict(row)
                                tags = r.get("tags")
                                if isinstance(tags, str):
                                    try:
                                        tags = json.loads(tags) if tags else []
                                    except Exception:
                                        tags = []
                                if not isinstance(tags, list):
                                    tags = []
                                db.add(
                                    DemoPrompt(
                                        title=r.get("title") or "",
                                        content=r.get("content") or "",
                                        category=r.get("category") or "general",
                                        tags=tags,
                                        is_malicious=bool(r.get("is_malicious", False)),
                                        preferred_llm=r.get("preferred_llm") if "preferred_llm" in columns else None,
                                    )
                                )
                    except Exception:
                        pass
                db.commit()
                return {
                    "message": "Configuration imported successfully",
                    "imported_at": datetime.utcnow().isoformat(),
                    "metadata": metadata,
                }

            # Version 2.0: merge by section
            config_path = os.path.join(temp_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                config_row = db.query(AppConfig).first()
                if not config_row:
                    config_row = AppConfig()
                    db.add(config_row)
                    db.flush()
                for section, fields in EXPORT_SECTIONS.items():
                    if section not in includes:
                        continue
                    for field in fields:
                        if field in config_data:
                            setattr(config_row, field, config_data[field])

            if "tools" in includes:
                tools_path = os.path.join(temp_dir, "tools.json")
                if os.path.exists(tools_path):
                    with open(tools_path, "r") as f:
                        tools_data = json.load(f)
                    if isinstance(tools_data, list) and len(tools_data) > 0:
                        db.query(MCPToolCapabilities).delete()
                        db.query(Tool).delete()
                        for tool_data in tools_data:
                            new_tool = Tool(
                                name=tool_data["name"],
                                type=tool_data["type"],
                                description=tool_data.get("description"),
                                endpoint=tool_data["endpoint"],
                                enabled=tool_data.get("enabled", True),
                                config_json=tool_data.get("config_json", {}),
                            )
                            db.add(new_tool)
                            db.flush()
                            if "mcp_capabilities" in tool_data:
                                cap_data = tool_data["mcp_capabilities"]
                                db.add(
                                    MCPToolCapabilities(
                                        tool_id=new_tool.id,
                                        tool_name=cap_data["tool_name"],
                                        server_name=cap_data.get("server_name"),
                                        session_info=cap_data.get("session_info"),
                                        discovery_results=cap_data.get("discovery_results", {}),
                                    )
                                )

            if "rag" in includes:
                rag_path = os.path.join(temp_dir, "rag_sources.json")
                if os.path.exists(rag_path):
                    with open(rag_path, "r") as f:
                        rag_data = json.load(f)
                    if isinstance(rag_data, list):
                        db.query(RagSource).delete()
                        for rag_source_data in rag_data:
                            db.add(
                                RagSource(
                                    name=rag_source_data["name"],
                                    content=rag_source_data["content"],
                                    chunks_count=rag_source_data.get("chunks_count", 0),
                                    source_type=rag_source_data.get("source_type", "generated"),
                                )
                            )
                chroma_source_dir = os.path.join(temp_dir, "data", "chroma")
                if os.path.exists(chroma_source_dir):
                    chroma_import_dir = "data/chroma_import"
                    if os.path.exists(chroma_import_dir):
                        shutil.rmtree(chroma_import_dir)
                    shutil.copytree(chroma_source_dir, chroma_import_dir)
                    try:
                        from .rag import reinitialize_chromadb

                        reinitialize_chromadb(chroma_import_dir)
                    except Exception:
                        pass

            if "demo_prompts" in includes:
                prompts_path = os.path.join(temp_dir, "demo_prompts.json")
                if os.path.exists(prompts_path):
                    with open(prompts_path, "r") as f:
                        prompts_data = json.load(f)
                    if isinstance(prompts_data, list):
                        db.query(DemoPrompt).delete()
                        for p in prompts_data:
                            if not isinstance(p, dict):
                                continue
                            title = p.get("title") or ""
                            content = p.get("content") or ""
                            if not title and not content:
                                continue
                            db.add(
                                DemoPrompt(
                                    title=title,
                                    content=content,
                                    category=p.get("category", "general"),
                                    tags=p.get("tags") if isinstance(p.get("tags"), list) else [],
                                    is_malicious=p.get("is_malicious", False),
                                    preferred_llm=p.get("preferred_llm"),
                                )
                            )

            db.commit()
            return {
                "message": "Configuration imported successfully",
                "imported_at": datetime.utcnow().isoformat(),
                "metadata": metadata,
            }
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail="Invalid zip file") from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in configuration file: {str(e)}") from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}") from e


# Chat endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Get configuration
    config = db.query(AppConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="No configuration found")

    # If sent from a demo prompt suggestion with a preferred LLM, switch model permanently
    if request.prompt_id:
        demo_prompt = db.query(DemoPrompt).filter(DemoPrompt.id == request.prompt_id).first()
        if demo_prompt and demo_prompt.preferred_llm:
            valid_models = openai_client.get_models()
            if demo_prompt.preferred_llm in valid_models:
                config.openai_model = demo_prompt.preferred_llm
                db.commit()

    # Create agent request
    agent_request = AgentRequest(message=request.message, session_id=request.session_id)

    # Run agent
    result = await run_agent(agent_request, config, db)

    return ChatResponse(
        response=result.response,
        lakera=result.lakera_status,
        tool_traces=result.tool_traces,
        citations=result.citations,
    )


# RAG endpoints
@app.post("/api/rag/generate", response_model=RagGenerateResponse)
async def generate_rag_content(request: RagGenerateRequest, db: Session = Depends(get_db)):
    try:
        # Generate content
        markdown = await rag.generate_seed_pack(
            industry=request.industry,
            seed_prompt=request.seed_prompt,
            options={},  # Will be expanded in guided mode
            mode="quick",
        )

        # If not preview only, ingest the content
        if not request.preview_only:
            source_meta = {
                "name": f"Generated Content - {request.industry}",
                "industry": request.industry,
                "seed_prompt": request.seed_prompt,
                "source_type": "generated",
            }
            await rag.ingest_markdown(markdown, source_meta, db)
            return RagGenerateResponse(markdown=markdown, ingested=True)
        else:
            return RagGenerateResponse(markdown=markdown, ingested=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate content: {str(e)}") from e


@app.get("/api/rag/search", response_model=RagSearchResponse)
async def search_rag_content(query: str, db: Session = Depends(get_db)):
    try:
        results = await rag.retrieve(query, top_k=5)
        return RagSearchResponse(chunks=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search: {str(e)}") from e


@app.get("/api/rag/sources")
async def get_rag_sources(db: Session = Depends(get_db)):
    """Get all RAG sources"""
    try:
        sources = db.query(RagSource).order_by(RagSource.created_at.desc()).all()
        return {
            "sources": [
                {
                    "id": source.id,
                    "name": source.name,
                    "source_type": source.source_type,
                    "chunks_count": source.chunks_count,
                    "created_at": source.created_at.isoformat() if source.created_at else None,
                    "updated_at": source.updated_at.isoformat() if source.updated_at else None,
                }
                for source in sources
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RAG sources: {str(e)}") from e


@app.delete("/api/rag/clear")
async def clear_rag_content(db: Session = Depends(get_db)):
    """Clear all RAG content"""
    try:
        # Clear ChromaDB collection - get all IDs first, then delete them
        try:
            # Get all documents to get their IDs
            all_docs = rag.collection.get()
            if all_docs and all_docs.get("ids"):
                rag.collection.delete(ids=all_docs["ids"])
        except Exception as chroma_error:
            print(f"ChromaDB clear error: {chroma_error}")
            # If ChromaDB fails, continue with database cleanup

        # Clear database sources
        db.query(RagSource).delete()
        db.commit()

        # Clear uploaded files from uploads directory
        uploads_dir = "uploads"
        if os.path.exists(uploads_dir):
            try:
                for filename in os.listdir(uploads_dir):
                    file_path = os.path.join(uploads_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"Deleted uploaded file: {filename}")
            except Exception as file_error:
                print(f"Error deleting uploaded files: {file_error}")
                # Continue even if file deletion fails

        return {"message": "RAG content and uploaded files cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear RAG content: {str(e)}") from e


@app.post("/api/rag/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and ingest a file into the RAG system"""
    try:
        # Validate file type
        allowed_types = {
            "application/pdf": ".pdf",
            "text/markdown": ".md",
            "text/plain": ".txt",
            "text/csv": ".csv",
            "application/octet-stream": ".csv",  # Allow CSV files detected as octet-stream
        }

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file.content_type} not supported. Allowed: {list(allowed_types.keys())}",
            )

        # Validate file size (10MB limit)
        if file.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

        # Create uploads directory if it doesn't exist
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Ingest file into RAG
        source_meta = {
            "name": file.filename,
            "source_type": "uploaded",
            "file_path": file_path,
            "mimetype": file.content_type,
        }

        result = await rag.ingest_file(file_path, file.content_type, source_meta, db)

        return {"message": "File uploaded and ingested successfully", "filename": file.filename, "result": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}") from e


@app.post("/api/rag/test-ingest")
async def test_ingest():
    """Test endpoint to ingest sample content"""
    try:
        with open("test_content.md", "r") as f:
            markdown = f.read()

        source_meta = {
            "name": "Digital Banking Guide",
            "industry": "FinTech",
            "source_type": "uploaded",
            "file_path": "test_content.md",
        }

        result = await rag.ingest_markdown(markdown, source_meta)
        return {"message": "Test content ingested", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest test content: {str(e)}") from e


# Tool endpoints
@app.get("/api/tools", response_model=List[ToolResponse])
async def get_tools(db: Session = Depends(get_db)):
    tools = db.query(Tool).all()
    return tools


@app.post("/api/tools", response_model=ToolResponse)
async def create_tool(tool: ToolCreate, db: Session = Depends(get_db)):
    db_tool = Tool(**tool.dict())
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool


@app.put("/api/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(tool_id: int, tool: ToolUpdate, db: Session = Depends(get_db)):
    db_tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    for field, value in tool.dict(exclude_unset=True).items():
        setattr(db_tool, field, value)

    db.commit()
    db.refresh(db_tool)
    return db_tool


@app.delete("/api/tools/{tool_id}")
async def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    db_tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    db.delete(db_tool)
    db.commit()
    return {"message": "Tool deleted"}


@app.post("/api/tools/test/{tool_id}")
async def test_tool(tool_id: int, db: Session = Depends(get_db)):
    """Test a tool's connectivity and basic functionality"""
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Get configuration for Lakera parameters
    config = db.query(AppConfig).first()
    lakera_api_key = config.lakera_api_key if config and config.lakera_enabled else None
    lakera_project_id = config.lakera_project_id if config else None
    lakera_blocking_mode = config.lakera_blocking_mode if config and config.lakera_enabled else True

    if tool.type in ["mcp", "http"]:
        # For MCP tools, try to discover capabilities
        try:
            discovery_result = await discover_mcp_tool_capabilities_sync(
                {"name": tool.name, "endpoint": tool.endpoint},
                lakera_api_key=lakera_api_key,
                lakera_project_id=lakera_project_id,
                lakera_blocking_mode=lakera_blocking_mode,
            )
            # Store the discovered capabilities
            await store_capabilities(tool.id, tool.name, discovery_result, db)
            return {
                "status": "success",
                "message": f"MCP tool {tool.name} discovery completed",
                "discovery": discovery_result,
            }
        except Exception as e:
            return {"status": "error", "message": f"MCP tool discovery failed: {str(e)}"}
    else:
        # For HTTP tools, test basic connectivity
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try HEAD first, then GET if HEAD fails
                try:
                    response = await client.head(tool.endpoint)
                    if response.status_code < 400:
                        return {"status": "success", "message": f"HTTP tool {tool.name} is reachable"}
                except Exception:
                    pass

                # Try GET as fallback
                response = await client.get(tool.endpoint, timeout=10.0)
                if response.status_code < 400:
                    return {"status": "success", "message": f"HTTP tool {tool.name} is reachable"}
                else:
                    return {"status": "error", "message": f"HTTP tool returned status {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"HTTP tool test failed: {str(e)}"}


@app.get("/api/tools/{tool_id}/capabilities")
async def get_tool_capabilities(tool_id: int, db: Session = Depends(get_db)):
    """Get stored capabilities for an MCP tool"""
    from .toolhive import get_stored_capabilities

    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if tool.type != "mcp":
        raise HTTPException(status_code=400, detail="Only MCP tools have capabilities")

    capabilities = await get_stored_capabilities(tool_id, db)
    if capabilities:
        return {"tool_id": tool_id, "tool_name": tool.name, "capabilities": capabilities}
    else:
        return {
            "tool_id": tool_id,
            "tool_name": tool.name,
            "capabilities": None,
            "message": "No capabilities discovered yet. Run the test endpoint first.",
        }


# Export/Import endpoints (legacy)
@app.get("/api/export")
async def legacy_export_config(db: Session = Depends(get_db)):
    config = db.query(AppConfig).first()
    tools = db.query(Tool).all()
    rag_sources = db.query(RagSource).all()

    return {"config": config, "tools": tools, "rag_sources": rag_sources}


@app.post("/api/import")
async def legacy_import_config(data: dict, db: Session = Depends(get_db)):
    # Placeholder for import functionality
    return {"message": "Import functionality needs to be implemented"}


# Demo Prompt endpoints
@app.get("/api/demo-prompts", response_model=List[DemoPromptResponse])
async def get_demo_prompts(category: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    """Get all demo prompts, optionally filtered by category"""
    query = db.query(DemoPrompt)

    if category:
        query = query.filter(DemoPrompt.category == category)

    prompts = query.order_by(DemoPrompt.usage_count.desc(), DemoPrompt.created_at.desc()).limit(limit).all()
    return prompts


@app.get("/api/demo-prompts/search")
async def search_demo_prompts(q: str, category: Optional[str] = None, limit: int = 10, db: Session = Depends(get_db)):
    """Search demo prompts by title, content, or tags"""
    if not q or len(q.strip()) < 2:
        return {"prompts": [], "suggestions": []}

    query = q.strip().lower()

    # Search in title, content, and tags
    prompts = db.query(DemoPrompt).filter(
        (DemoPrompt.title.ilike(f"%{query}%"))
        | (DemoPrompt.content.ilike(f"%{query}%"))
        | (DemoPrompt.tags.contains([query]))
    )

    if category:
        prompts = prompts.filter(DemoPrompt.category == category)

    results = prompts.order_by(DemoPrompt.usage_count.desc()).limit(limit).all()

    # Generate suggestions for autocomplete
    suggestions = []
    for prompt in results:
        # Find the best matching part for autocomplete
        title_lower = prompt.title.lower()
        content_lower = prompt.content.lower()

        if query in title_lower:
            # Use title for autocomplete
            start_idx = title_lower.find(query)
            suggestion = prompt.title[start_idx : start_idx + len(query) + 20]  # Show more context
            suggestions.append(
                {
                    "text": suggestion,
                    "full_content": prompt.content,
                    "title": prompt.title,
                    "category": prompt.category,
                    "is_malicious": prompt.is_malicious,
                    "prompt_id": prompt.id,
                    "preferred_llm": getattr(prompt, "preferred_llm", None),
                }
            )
        elif query in content_lower:
            # Use content for autocomplete
            start_idx = content_lower.find(query)
            suggestion = prompt.content[start_idx : start_idx + len(query) + 20]
            suggestions.append(
                {
                    "text": suggestion,
                    "full_content": prompt.content,
                    "title": prompt.title,
                    "category": prompt.category,
                    "is_malicious": prompt.is_malicious,
                    "prompt_id": prompt.id,
                    "preferred_llm": getattr(prompt, "preferred_llm", None),
                }
            )

    return {
        "prompts": [
            {
                "id": prompt.id,
                "title": prompt.title,
                "content": prompt.content,
                "category": prompt.category,
                "tags": prompt.tags,
                "is_malicious": prompt.is_malicious,
                "usage_count": prompt.usage_count,
                "preferred_llm": getattr(prompt, "preferred_llm", None),
            }
            for prompt in results
        ],
        "suggestions": suggestions[:5],  # Limit to top 5 suggestions
    }


@app.post("/api/demo-prompts", response_model=DemoPromptResponse)
async def create_demo_prompt(prompt: DemoPromptCreate, db: Session = Depends(get_db)):
    """Create a new demo prompt"""
    db_prompt = DemoPrompt(**prompt.dict())
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt


@app.put("/api/demo-prompts/{prompt_id}", response_model=DemoPromptResponse)
async def update_demo_prompt(prompt_id: int, prompt: DemoPromptUpdate, db: Session = Depends(get_db)):
    """Update an existing demo prompt"""
    db_prompt = db.query(DemoPrompt).filter(DemoPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Demo prompt not found")

    for field, value in prompt.dict(exclude_unset=True).items():
        setattr(db_prompt, field, value)

    db.commit()
    db.refresh(db_prompt)
    return db_prompt


@app.delete("/api/demo-prompts/{prompt_id}")
async def delete_demo_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """Delete a demo prompt"""
    db_prompt = db.query(DemoPrompt).filter(DemoPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Demo prompt not found")

    db.delete(db_prompt)
    db.commit()
    return {"message": "Demo prompt deleted"}


@app.post("/api/demo-prompts/{prompt_id}/use")
async def use_demo_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """Increment usage count for a demo prompt"""
    db_prompt = db.query(DemoPrompt).filter(DemoPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Demo prompt not found")

    db_prompt.usage_count += 1
    db.commit()
    return {"message": "Usage count updated", "usage_count": db_prompt.usage_count}


# Lakera endpoints
@app.get("/api/lakera/last")
async def get_last_lakera_result():
    """Get the last Lakera result for frontend polling"""
    result = lakera.get_last_result()
    if result is None:
        raise HTTPException(status_code=404, detail="No Lakera result available")
    return result


@app.get("/api/lakera/last_request")
async def get_last_lakera_request():
    """Get the last Lakera request payload for debugging (messages + metadata)"""
    req = lakera.get_last_request()
    if req is None:
        raise HTTPException(status_code=404, detail="No Lakera request recorded yet")
    return req


@app.get("/api/rag/scanning/last")
async def get_last_rag_scanning_result():
    """Get the last RAG content scanning result"""
    result = rag.get_last_rag_scanning_result()
    if result is None:
        raise HTTPException(status_code=404, detail="No RAG scanning result available")
    return result


@app.get("/api/rag/scanning/progress")
async def get_rag_scanning_progress():
    """Get the current RAG scanning progress"""
    progress = rag.get_rag_scanning_progress()
    if progress is None:
        raise HTTPException(status_code=404, detail="No RAG scanning in progress")
    return progress


@app.get("/api/models")
async def get_available_models():
    """Get available OpenAI models"""
    try:
        models = openai_client.get_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}") from e
