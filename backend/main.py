from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import json
import zipfile
import io
from datetime import datetime

from .database import get_db, engine
from .models import Base, AppConfig, Tool, RagSource, MCPToolCapabilities, DemoPrompt
from .schemas import (
    AppConfigResponse, AppConfigUpdate,
    ChatRequest, ChatResponse,
    RagGenerateRequest, RagGenerateResponse, RagSearchResponse,
    ToolResponse, ToolCreate, ToolUpdate,
    DemoPromptResponse, DemoPromptCreate, DemoPromptUpdate, DemoPromptSearchRequest
)
from .agent import run_agent, AgentRequest
from . import lakera, rag
from .toolhive import enabled_tools, discover_mcp_tool_capabilities_sync, store_capabilities

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Agentic Demo API",
    description="Backend API for the Agentic Demo application",
    version="1.0.0"
)

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

@app.get("/api/config/export")
async def export_config(db: Session = Depends(get_db)):
    """Export complete configuration as a zip file"""
    try:
        # Create in-memory zip file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Export AppConfig
            config = db.query(AppConfig).first()
            if config:
                config_dict = {
                    "id": config.id,
                    "openai_api_key": config.openai_api_key,
                    "lakera_api_key": config.lakera_api_key,
                    "lakera_project_id": config.lakera_project_id,
                    "business_name": config.business_name,
                    "tagline": config.tagline,
                    "hero_text": config.hero_text,
                    "hero_image_url": config.hero_image_url,
                    "logo_url": config.logo_url,
                    "system_prompt": config.system_prompt,
                    "openai_model": config.openai_model,
                    "temperature": config.temperature,
                    "lakera_enabled": config.lakera_enabled,
                    "lakera_blocking_mode": config.lakera_blocking_mode,
                    "created_at": config.created_at.isoformat() if config.created_at else None,
                    "updated_at": config.updated_at.isoformat() if config.updated_at else None
                }
                zip_file.writestr("config.json", json.dumps(config_dict, indent=2))
            
            # Export Tools and their capabilities
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
                    "updated_at": tool.updated_at.isoformat() if tool.updated_at else None
                }
                
                # Get MCP capabilities for this tool
                capabilities = db.query(MCPToolCapabilities).filter(MCPToolCapabilities.tool_id == tool.id).first()
                if capabilities:
                    tool_dict["mcp_capabilities"] = {
                        "id": capabilities.id,
                        "tool_name": capabilities.tool_name,
                        "server_name": capabilities.server_name,
                        "session_info": capabilities.session_info,
                        "discovery_results": capabilities.discovery_results,
                        "last_discovered": capabilities.last_discovered.isoformat() if capabilities.last_discovered else None,
                        "created_at": capabilities.created_at.isoformat() if capabilities.created_at else None,
                        "updated_at": capabilities.updated_at.isoformat() if capabilities.updated_at else None
                    }
                
                tools_data.append(tool_dict)
            
            zip_file.writestr("tools.json", json.dumps(tools_data, indent=2))
            
            # Export RAG sources
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
                    "updated_at": source.updated_at.isoformat() if source.updated_at else None
                }
                rag_data.append(rag_dict)
            
            zip_file.writestr("rag_sources.json", json.dumps(rag_data, indent=2))
            
            # Export ChromaDB instead of uploads directory
            chroma_dir = "data/chroma"
            if os.path.exists(chroma_dir):
                for root, dirs, files in os.walk(chroma_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Create relative path within zip, preserving the chroma structure
                        arcname = os.path.relpath(file_path, ".")
                        zip_file.write(file_path, arcname)
            
            # Also export the main database file
            db_file = "data/agentic_demo.db"
            if os.path.exists(db_file):
                zip_file.write(db_file, "data/agentic_demo.db")
            
            # Add metadata
            metadata = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "version": "1.0",
                "description": "Agentic Demo Configuration Export",
                "includes": [
                    "app_config",
                    "tools_and_capabilities", 
                    "rag_sources",
                    "chromadb_vector_store",
                    "main_database"
                ]
            }
            zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))
        
        # Prepare response
        zip_buffer.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"agentic_demo_config_{timestamp}.zip"
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.post("/api/config/import")
async def import_config(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import complete configuration from a zip file"""
    try:
        # Validate file type
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="File must be a .zip file")
        
        # Read the uploaded file
        file_content = await file.read()
        
        # Create temporary directory for extraction
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file to temp location
            temp_zip_path = os.path.join(temp_dir, "import.zip")
            with open(temp_zip_path, "wb") as f:
                f.write(file_content)
            
            # Extract zip file
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_file:
                zip_file.extractall(temp_dir)
            
            # Validate required files exist
            required_files = ["config.json", "tools.json", "rag_sources.json", "metadata.json"]
            for required_file in required_files:
                if not os.path.exists(os.path.join(temp_dir, required_file)):
                    raise HTTPException(status_code=400, detail=f"Missing required file: {required_file}")
            
            # Read and validate metadata
            with open(os.path.join(temp_dir, "metadata.json"), 'r') as f:
                metadata = json.load(f)
            
            if metadata.get("version") != "1.0":
                raise HTTPException(status_code=400, detail="Unsupported export version")
            
            # Import AppConfig
            with open(os.path.join(temp_dir, "config.json"), 'r') as f:
                config_data = json.load(f)
            
            # Clear existing config and create new one
            db.query(AppConfig).delete()
            new_config = AppConfig(
                openai_api_key=config_data.get("openai_api_key"),
                lakera_api_key=config_data.get("lakera_api_key"),
                lakera_project_id=config_data.get("lakera_project_id"),
                business_name=config_data.get("business_name"),
                tagline=config_data.get("tagline"),
                hero_text=config_data.get("hero_text"),
                hero_image_url=config_data.get("hero_image_url"),
                logo_url=config_data.get("logo_url"),
                system_prompt=config_data.get("system_prompt"),
                openai_model=config_data.get("openai_model", "gpt-4o-mini"),
                temperature=config_data.get("temperature", "0.7"),
                lakera_enabled=config_data.get("lakera_enabled", True),
                lakera_blocking_mode=config_data.get("lakera_blocking_mode", False)
            )
            db.add(new_config)
            
            # Import Tools and MCP Capabilities
            with open(os.path.join(temp_dir, "tools.json"), 'r') as f:
                tools_data = json.load(f)
            
            # Clear existing tools and capabilities
            db.query(MCPToolCapabilities).delete()
            db.query(Tool).delete()
            
            for tool_data in tools_data:
                # Create tool
                new_tool = Tool(
                    name=tool_data["name"],
                    type=tool_data["type"],
                    description=tool_data.get("description"),
                    endpoint=tool_data["endpoint"],
                    enabled=tool_data.get("enabled", True),
                    config_json=tool_data.get("config_json", {})
                )
                db.add(new_tool)
                db.flush()  # Get the ID
                
                # Create MCP capabilities if they exist
                if "mcp_capabilities" in tool_data:
                    cap_data = tool_data["mcp_capabilities"]
                    new_capabilities = MCPToolCapabilities(
                        tool_id=new_tool.id,
                        tool_name=cap_data["tool_name"],
                        server_name=cap_data.get("server_name"),
                        session_info=cap_data.get("session_info"),
                        discovery_results=cap_data.get("discovery_results", {})
                    )
                    db.add(new_capabilities)
            
            # Import RAG sources
            with open(os.path.join(temp_dir, "rag_sources.json"), 'r') as f:
                rag_data = json.load(f)
            
            # Clear existing RAG sources
            db.query(RagSource).delete()
            
            for rag_source_data in rag_data:
                new_rag_source = RagSource(
                    name=rag_source_data["name"],
                    content=rag_source_data["content"],
                    chunks_count=rag_source_data.get("chunks_count", 0),
                    source_type=rag_source_data.get("source_type", "generated")
                )
                db.add(new_rag_source)
            
            # Import ChromaDB
            chroma_source_dir = os.path.join(temp_dir, "data", "chroma")
            if os.path.exists(chroma_source_dir):
                # Remove existing ChromaDB
                chroma_target_dir = "data/chroma"
                if os.path.exists(chroma_target_dir):
                    shutil.rmtree(chroma_target_dir)
                
                # Copy new ChromaDB
                shutil.copytree(chroma_source_dir, chroma_target_dir)
                
                # Reinitialize ChromaDB client to use new data
                try:
                    from .rag import reinitialize_chromadb
                    reinitialize_chromadb()
                    print("✅ ChromaDB reinitialized successfully")
                except Exception as e:
                    print(f"⚠️ ChromaDB reinitialization failed: {e}")
                    print("ℹ️ This is not critical - ChromaDB will work on next restart")
                    # Continue with import even if ChromaDB reinitialization fails
                    # The RAG system will work with the new data on next restart
            
            # Note: We don't need to import the main database file since we're already
            # importing all the data through the ORM above. The database file overwrite
            # was causing schema mismatches when the imported DB had different schema.
            
            # Commit all changes
            db.commit()
            
            return {
                "message": "Configuration imported successfully",
                "imported_at": datetime.utcnow().isoformat(),
                "metadata": metadata
            }
        
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in configuration file: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

# Chat endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Get configuration
    config = db.query(AppConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="No configuration found")
    
    # Create agent request
    agent_request = AgentRequest(
        message=request.message,
        session_id=request.session_id
    )
    
    # Run agent
    result = await run_agent(agent_request, config, db)
    
    return ChatResponse(
        response=result.response,
        lakera=result.lakera_status,
        tool_traces=result.tool_traces,
        citations=result.citations
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
            mode="quick"
        )
        
        # If not preview only, ingest the content
        if not request.preview_only:
            source_meta = {
                "name": f"Generated Content - {request.industry}",
                "industry": request.industry,
                "seed_prompt": request.seed_prompt,
                "source_type": "generated"
            }
            result = await rag.ingest_markdown(markdown, source_meta, db)
            return RagGenerateResponse(
                markdown=markdown,
                ingested=True
            )
        else:
            return RagGenerateResponse(
                markdown=markdown,
                ingested=False
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate content: {str(e)}")

@app.get("/api/rag/search", response_model=RagSearchResponse)
async def search_rag_content(query: str, db: Session = Depends(get_db)):
    try:
        results = await rag.retrieve(query, top_k=5)
        return RagSearchResponse(chunks=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search: {str(e)}")

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
                    "updated_at": source.updated_at.isoformat() if source.updated_at else None
                }
                for source in sources
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RAG sources: {str(e)}")

@app.delete("/api/rag/clear")
async def clear_rag_content(db: Session = Depends(get_db)):
    """Clear all RAG content"""
    try:
        # Clear ChromaDB collection - get all IDs first, then delete them
        try:
            # Get all documents to get their IDs
            all_docs = rag.collection.get()
            if all_docs and all_docs.get('ids'):
                rag.collection.delete(ids=all_docs['ids'])
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
        raise HTTPException(status_code=500, detail=f"Failed to clear RAG content: {str(e)}")

@app.post("/api/rag/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and ingest a file into the RAG system"""
    try:
        # Validate file type
        allowed_types = {
            'application/pdf': '.pdf',
            'text/markdown': '.md',
            'text/plain': '.txt',
            'text/csv': '.csv'
        }
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file.content_type} not supported. Allowed: {list(allowed_types.keys())}"
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
            "mimetype": file.content_type
        }
        
        result = await rag.ingest_file(file_path, file.content_type, source_meta, db)
        
        return {
            "message": "File uploaded and ingested successfully",
            "filename": file.filename,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

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
            "file_path": "test_content.md"
        }
        
        result = await rag.ingest_markdown(markdown, source_meta)
        return {"message": "Test content ingested", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest test content: {str(e)}")

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
            discovery_result = await discover_mcp_tool_capabilities_sync({
                "name": tool.name,
                "endpoint": tool.endpoint
            }, lakera_api_key=lakera_api_key, lakera_project_id=lakera_project_id, lakera_blocking_mode=lakera_blocking_mode)
            # Store the discovered capabilities
            await store_capabilities(tool.id, tool.name, discovery_result, db)
            return {
                "status": "success",
                "message": f"MCP tool {tool.name} discovery completed",
                "discovery": discovery_result
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"MCP tool discovery failed: {str(e)}"
            }
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
                except:
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
        return {
            "tool_id": tool_id,
            "tool_name": tool.name,
            "capabilities": capabilities
        }
    else:
        return {
            "tool_id": tool_id,
            "tool_name": tool.name,
            "capabilities": None,
            "message": "No capabilities discovered yet. Run the test endpoint first."
        }

# Export/Import endpoints
@app.get("/api/export")
async def export_config(db: Session = Depends(get_db)):
    config = db.query(AppConfig).first()
    tools = db.query(Tool).all()
    rag_sources = db.query(RagSource).all()
    
    return {
        "config": config,
        "tools": tools,
        "rag_sources": rag_sources
    }

@app.post("/api/import")
async def import_config(data: dict, db: Session = Depends(get_db)):
    # Placeholder for import functionality
    return {"message": "Import functionality needs to be implemented"}

# Demo Prompt endpoints
@app.get("/api/demo-prompts", response_model=List[DemoPromptResponse])
async def get_demo_prompts(
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all demo prompts, optionally filtered by category"""
    query = db.query(DemoPrompt)
    
    if category:
        query = query.filter(DemoPrompt.category == category)
    
    prompts = query.order_by(DemoPrompt.usage_count.desc(), DemoPrompt.created_at.desc()).limit(limit).all()
    return prompts

@app.get("/api/demo-prompts/search")
async def search_demo_prompts(
    q: str,
    category: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Search demo prompts by title, content, or tags"""
    if not q or len(q.strip()) < 2:
        return {"prompts": [], "suggestions": []}
    
    query = q.strip().lower()
    
    # Search in title, content, and tags
    prompts = db.query(DemoPrompt).filter(
        (DemoPrompt.title.ilike(f"%{query}%")) |
        (DemoPrompt.content.ilike(f"%{query}%")) |
        (DemoPrompt.tags.contains([query]))
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
            suggestion = prompt.title[start_idx:start_idx + len(query) + 20]  # Show more context
            suggestions.append({
                "text": suggestion,
                "full_content": prompt.content,
                "title": prompt.title,
                "category": prompt.category,
                "is_malicious": prompt.is_malicious
            })
        elif query in content_lower:
            # Use content for autocomplete
            start_idx = content_lower.find(query)
            suggestion = prompt.content[start_idx:start_idx + len(query) + 20]
            suggestions.append({
                "text": suggestion,
                "full_content": prompt.content,
                "title": prompt.title,
                "category": prompt.category,
                "is_malicious": prompt.is_malicious
            })
    
    return {
        "prompts": [
            {
                "id": prompt.id,
                "title": prompt.title,
                "content": prompt.content,
                "category": prompt.category,
                "tags": prompt.tags,
                "is_malicious": prompt.is_malicious,
                "usage_count": prompt.usage_count
            }
            for prompt in results
        ],
        "suggestions": suggestions[:5]  # Limit to top 5 suggestions
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
