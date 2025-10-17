import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import uuid
from .openai_client import openai_client
from .database import get_db
from .models import AppConfig, RagSource
import re

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(
    path="./data/chroma",
    settings=Settings(
        anonymized_telemetry=False,  # disables telemetry
        allow_reset=True
    )
)
collection = chroma_client.get_or_create_collection(
    name="agentic_demo",
    metadata={"hnsw:space": "cosine"}
)

def reinitialize_chromadb():
    """Reinitialize ChromaDB client and collection after import"""
    global chroma_client, collection
    try:
        # Close existing client if possible
        if 'chroma_client' in globals() and chroma_client is not None:
            try:
                # ChromaDB doesn't have an explicit close method, but we can try to clean up
                pass
            except:
                pass
        
        # Create new client with explicit settings to avoid tenant issues
        chroma_client = chromadb.PersistentClient(
            path="./data/chroma",
            settings=Settings(
                anonymized_telemetry=False,  # disables telemetry
                allow_reset=True
            )
        )
        
        # Try to get existing collection first, then create if needed
        try:
            collection = chroma_client.get_collection(name="agentic_demo")
            print("🔄 ChromaDB client reinitialized with existing collection")
        except:
            # Collection doesn't exist, create it
            collection = chroma_client.create_collection(
                name="agentic_demo",
                metadata={"hnsw:space": "cosine"}
            )
            print("🔄 ChromaDB client reinitialized with new collection")
        
        # Test the connection
        try:
            count = collection.count()
            print(f"🔄 ChromaDB reinitialized successfully with {count} documents")
        except Exception as e:
            print(f"⚠️ ChromaDB reinitialized but connection test failed: {e}")
            
    except Exception as e:
        print(f"❌ Failed to reinitialize ChromaDB: {e}")
        # Fallback: try to create a new client anyway
        try:
            chroma_client = chromadb.PersistentClient(
                path="./data/chroma",
                settings=Settings(
                    anonymized_telemetry=False,  # disables telemetry
                    allow_reset=True
                )
            )
            collection = chroma_client.get_or_create_collection(
                name="agentic_demo",
                metadata={"hnsw:space": "cosine"}
            )
            print("🔄 ChromaDB fallback reinitialization successful")
        except Exception as e2:
            print(f"❌ ChromaDB fallback reinitialization also failed: {e2}")
            # Don't raise - just log the error and continue
            print("ℹ️ ChromaDB will be reinitialized on next application restart")

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    
    return chunks

async def retrieve(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve relevant documents from RAG system
    Returns list of dicts with "text" and "metadata" keys
    """
    try:
        # Get embeddings for the query
        query_embeddings = openai_client.get_embeddings([query])
        
        # Search in ChromaDB
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=top_k
        )
        
        documents = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {}
                documents.append({
                    "text": doc,
                    "metadata": metadata
                })
        
        return documents
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return []

async def ingest_file(path: str, mimetype: str, meta: Dict[str, Any], db=None) -> Dict[str, Any]:
    """
    Ingest a file into the RAG system
    Returns dict with source_id, chunks count, and metadata
    """
    try:
        # Read file content based on type
        content = ""
        
        if mimetype == "text/markdown" or mimetype == "text/plain" or mimetype == "text/csv":
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif mimetype == "application/pdf":
            # For PDF, we'll use a simple text extraction
            # In a real implementation, you'd use PyPDF2 or similar
            try:
                import PyPDF2
                with open(path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    content = ""
                    for page in pdf_reader.pages:
                        content += page.extract_text() + "\n"
            except ImportError:
                # Fallback: return error message
                content = f"PDF processing not available. Please install PyPDF2 for PDF support."
        else:
            raise Exception(f"Unsupported file type: {mimetype}")
        
        # Ingest the content
        return await ingest_markdown(content, meta, db)
        
    except Exception as e:
        print(f"File ingestion error: {e}")
        return {
            "source_id": "error",
            "chunks": 0,
            "metadata": meta
        }

async def generate_seed_pack(industry: str, seed_prompt: str, options: Dict[str, Any], mode: str) -> str:
    """
    Generate seed pack content for an industry
    Returns markdown preview string
    """
    try:
        # Get configuration for branding
        db = next(get_db())
        config = db.query(AppConfig).first()
        db.close()
        
        if not config:
            raise Exception("No configuration found")
        
        # Prepare the prompt template
        system_prompt = """You write concise industry knowledge packs for B2B demo purposes.
Respond ONLY in markdown. Use bullet points, FAQs, and glossary style.
Cap length to 2000 tokens. Avoid hallucinating policies."""
        
        user_prompt = f"""Industry: {industry}
Brand: {config.business_name}
Tagline: {config.tagline}
Hero: {config.hero_text}
Audience: {options.get('audience', 'B2B professionals')}
Tone: {options.get('tone', 'professional')}
Sections: {options.get('include_sections', ['faqs', 'glossary'])}
Constraints: {options.get('constraints', '')}

{seed_prompt}"""
        
        # Call OpenAI to generate content
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = openai_client.chat_completion(
            messages=messages,
            model=config.openai_model,
            temperature=float(config.temperature) / 10.0
        )
        
        markdown = response["choices"][0]["message"]["content"]
        return markdown
        
    except Exception as e:
        print(f"Seed pack generation error: {e}")
        return f"# Error generating content for {industry}\n\nFailed to generate content: {str(e)}"

async def ingest_markdown(markdown: str, source_meta: Dict[str, Any], db=None) -> Dict[str, Any]:
    """
    Ingest markdown content into RAG system
    """
    try:
        # Chunk the markdown
        chunks = chunk_text(markdown)
        
        # Get embeddings for chunks
        try:
            embeddings = openai_client.get_embeddings(chunks)
        except Exception as e:
            print(f"Embeddings error: {e}")
            raise Exception(f"Failed to get embeddings: {str(e)}. Please configure OpenAI API key.")
        
        # Generate IDs for chunks
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        
        # Add to ChromaDB
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=chunk_ids,
            metadatas=[{
                **source_meta,
                "chunk_index": i,
                "total_chunks": len(chunks)
            } for i in range(len(chunks))]
        )
        
        # Save to database
        if db is None:
            db = next(get_db())
            should_close = True
        else:
            should_close = False
            
        rag_source = RagSource(
            name=source_meta.get("name", "Generated Content"),
            content=markdown[:1000] + "..." if len(markdown) > 1000 else markdown,  # Store first 1000 chars as preview
            source_type=source_meta.get("source_type", "generated"),
            chunks_count=len(chunks)
        )
        db.add(rag_source)
        db.commit()
        
        if should_close:
            db.close()
        
        return {
            "source_id": str(rag_source.id),
            "chunks": len(chunks),
            "metadata": source_meta
        }
        
    except Exception as e:
        print(f"Markdown ingestion error: {e}")
        return {
            "source_id": "error",
            "chunks": 0,
            "metadata": source_meta
        }
