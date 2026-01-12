import os
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Tuple
import uuid
import csv
import json
import re
from .openai_client import openai_client
from .database import get_db
from .models import AppConfig, RagSource
from .lakera import check_interaction

# Global variables to store RAG scanning results and progress
_last_rag_scanning_result: Optional[Dict[str, Any]] = None
_rag_scanning_progress: Optional[Dict[str, Any]] = None

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
    """Split text into overlapping chunks (fallback for unknown file types)"""
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

def chunk_csv(content: str, filename: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Chunk CSV content row by row with headers as metadata
    Returns list of (chunk_text, metadata) tuples
    """
    try:
        import io
        csv_reader = csv.DictReader(io.StringIO(content))
        rows = list(csv_reader)
        
        if not rows:
            return []
        
        # Get headers for metadata
        headers = list(rows[0].keys())
        
        chunks = []
        
        # Add summary chunk first (most important for count queries)
        summary_text = f"Dataset Summary: {len(rows)} total records in {filename}. Columns: {', '.join(headers)}. This dataset contains {len(rows)} rows of data with {len(headers)} columns."
        summary_metadata = {
            "file_type": "csv",
            "filename": filename,
            "headers": ", ".join(headers),
            "total_rows": len(rows),
            "total_columns": len(headers),
            "chunk_type": "csv_summary"
        }
        chunks.append((summary_text, summary_metadata))
        
        # Add individual row chunks
        for i, row in enumerate(rows):
            # Create a readable text representation of the row
            row_text = f"Row {i+1}: " + " | ".join([f"{k}: {v}" for k, v in row.items()])
            
            # Create metadata with headers and row info
            metadata = {
                "file_type": "csv",
                "filename": filename,
                "headers": ", ".join(headers),  # Convert list to comma-separated string
                "row_number": i + 1,
                "total_rows": len(rows),
                "chunk_type": "csv_row"
            }
            
            chunks.append((row_text, metadata))
        
        return chunks
        
    except Exception as e:
        print(f"CSV chunking error: {e}")
        # Fallback to text chunking
        return [(content, {"file_type": "csv", "filename": filename, "chunk_type": "csv_fallback"})]

def chunk_json(content: str, filename: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Chunk JSON content object by object
    Returns list of (chunk_text, metadata) tuples
    """
    try:
        data = json.loads(content)
        chunks = []
        
        if isinstance(data, list):
            # Array of objects - add summary chunk
            if len(data) > 1:  # Only add summary for arrays with multiple items
                summary_text = f"JSON Dataset Summary: {len(data)} items in {filename}. This JSON array contains {len(data)} objects."
                if data and isinstance(data[0], dict):
                    keys = list(data[0].keys())
                    summary_text += f" Each object has {len(keys)} fields: {', '.join(keys)}."
                
                summary_metadata = {
                    "file_type": "json",
                    "filename": filename,
                    "total_items": len(data),
                    "chunk_type": "json_summary"
                }
                chunks.append((summary_text, summary_metadata))
            
            # Add individual items
            for i, item in enumerate(data):
                item_text = json.dumps(item, indent=2)
                metadata = {
                    "file_type": "json",
                    "filename": filename,
                    "item_index": i,
                    "total_items": len(data),
                    "chunk_type": "json_object"
                }
                chunks.append((item_text, metadata))
                
        elif isinstance(data, dict):
            # Single object - add summary chunk
            summary_text = f"JSON Object Summary: {len(data)} top-level keys in {filename}: {', '.join(data.keys())}."
            summary_metadata = {
                "file_type": "json",
                "filename": filename,
                "total_keys": len(data),
                "chunk_type": "json_summary"
            }
            chunks.append((summary_text, summary_metadata))
            
            # Add individual key-value pairs
            for key, value in data.items():
                item_text = f"{key}: {json.dumps(value, indent=2)}"
                metadata = {
                    "file_type": "json",
                    "filename": filename,
                    "key": key,
                    "chunk_type": "json_key_value"
                }
                chunks.append((item_text, metadata))
        else:
            # Primitive value - no summary needed
            chunks.append((str(data), {
                "file_type": "json",
                "filename": filename,
                "chunk_type": "json_primitive"
            }))
        
        return chunks
        
    except Exception as e:
        print(f"JSON chunking error: {e}")
        # Fallback to text chunking
        return [(content, {"file_type": "json", "filename": filename, "chunk_type": "json_fallback"})]

def chunk_markdown(content: str, filename: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Chunk Markdown content by sections (headers)
    Returns list of (chunk_text, metadata) tuples
    """
    try:
        # Split by markdown headers (# ## ###)
        sections = re.split(r'\n(?=#{1,6}\s)', content)
        
        chunks = []
        
        # Add summary chunk for multi-section documents
        if len(sections) > 1:
            # Extract section titles for summary
            section_titles = []
            for section in sections:
                header_match = re.match(r'^(#{1,6})\s+(.+)', section)
                if header_match:
                    section_titles.append(header_match.group(2).strip())
            
            summary_text = f"Document Summary: {len(sections)} sections in {filename}. Sections: {', '.join(section_titles[:5])}{'...' if len(section_titles) > 5 else ''}."
            summary_metadata = {
                "file_type": "markdown",
                "filename": filename,
                "total_sections": len(sections),
                "chunk_type": "markdown_summary"
            }
            chunks.append((summary_text, summary_metadata))
        
        # Add individual section chunks
        for i, section in enumerate(sections):
            if not section.strip():
                continue
                
            # Extract header level and title
            header_match = re.match(r'^(#{1,6})\s+(.+)', section)
            if header_match:
                header_level = len(header_match.group(1))
                header_title = header_match.group(2).strip()
            else:
                header_level = 0
                header_title = f"Section {i+1}"
            
            metadata = {
                "file_type": "markdown",
                "filename": filename,
                "section_index": i,
                "header_level": header_level,
                "header_title": header_title,
                "chunk_type": "markdown_section"
            }
            
            chunks.append((section.strip(), metadata))
        
        return chunks
        
    except Exception as e:
        print(f"Markdown chunking error: {e}")
        # Fallback to text chunking
        return [(content, {"file_type": "markdown", "filename": filename, "chunk_type": "markdown_fallback"})]

def chunk_pdf(content: str, filename: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Chunk PDF content by pages with structure preservation
    Returns list of (chunk_text, metadata) tuples
    """
    try:
        # Split by page breaks (if available) or by paragraphs
        pages = content.split('\f') if '\f' in content else content.split('\n\n')
        
        chunks = []
        
        # Add summary chunk for multi-page documents
        if len(pages) > 1:
            summary_text = f"PDF Document Summary: {len(pages)} pages in {filename}. This document contains {len(pages)} pages of content."
            summary_metadata = {
                "file_type": "pdf",
                "filename": filename,
                "total_pages": len(pages),
                "chunk_type": "pdf_summary"
            }
            chunks.append((summary_text, summary_metadata))
        
        # Add individual page chunks
        for i, page in enumerate(pages):
            if not page.strip():
                continue
                
            metadata = {
                "file_type": "pdf",
                "filename": filename,
                "page_number": i + 1,
                "total_pages": len(pages),
                "chunk_type": "pdf_page"
            }
            
            chunks.append((page.strip(), metadata))
        
        return chunks
        
    except Exception as e:
        print(f"PDF chunking error: {e}")
        # Fallback to text chunking
        return [(content, {"file_type": "pdf", "filename": filename, "chunk_type": "pdf_fallback"})]

def chunk_by_file_type(content: str, filename: str, mimetype: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Route to appropriate chunking strategy based on file type
    Returns list of (chunk_text, metadata) tuples
    """
    # Determine file type from mimetype and filename
    if mimetype == "text/csv" or filename.endswith('.csv'):
        return chunk_csv(content, filename)
    elif mimetype == "application/json" or filename.endswith('.json'):
        return chunk_json(content, filename)
    elif mimetype == "text/markdown" or filename.endswith(('.md', '.markdown')):
        return chunk_markdown(content, filename)
    elif mimetype == "application/pdf" or filename.endswith('.pdf'):
        return chunk_pdf(content, filename)
    else:
        # Fallback to generic text chunking
        chunks = chunk_text(content)
        return [(chunk, {
            "file_type": "text",
            "filename": filename,
            "chunk_type": "text_generic"
        }) for chunk in chunks]

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
        
        # Smart retrieval: prioritize summary chunks for count/statistical queries
        count_keywords = ['how many', 'total', 'count', 'number of', 'records', 'items', 'customers', 'users', 'pages', 'sections']
        is_count_query = any(keyword in query.lower() for keyword in count_keywords)
        
        if is_count_query:
            # For count queries, do a separate search specifically for summary chunks
            try:
                # Get all documents and filter for summary chunks
                all_docs = collection.get()
                summary_chunks = []
                
                for i, metadata in enumerate(all_docs['metadatas']):
                    if metadata.get('chunk_type', '').endswith('_summary'):
                        summary_chunks.append({
                            'text': all_docs['documents'][i],
                            'metadata': metadata
                        })
                
                print(f"🔍 Count query detected. Found {len(summary_chunks)} summary chunks in database")
                if summary_chunks:
                    print(f"📊 Summary chunk text: {summary_chunks[0]['text'][:100]}...")
                    # Return summary chunks first, then other relevant chunks
                    other_chunks = [doc for doc in documents if not doc.get('metadata', {}).get('chunk_type', '').endswith('_summary')]
                    return summary_chunks + other_chunks[:top_k - len(summary_chunks)]
            except Exception as e:
                print(f"Error searching for summary chunks: {e}")
                # Fall back to regular search
        
        return documents
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return []

def get_last_rag_scanning_result() -> Optional[Dict[str, Any]]:
    """Get the last RAG content scanning result"""
    global _last_rag_scanning_result
    return _last_rag_scanning_result

def get_rag_scanning_progress() -> Optional[Dict[str, Any]]:
    """Get the current RAG scanning progress"""
    global _rag_scanning_progress
    return _rag_scanning_progress

async def scan_chunk_content(chunk_text: str, config: AppConfig) -> Tuple[bool, Optional[str]]:
    """
    Scan a single chunk for malicious content using Lakera Guard
    Returns (is_safe, reason_if_unsafe)
    """
    try:
        print(f"🔍 Scanning chunk: {chunk_text[:100]}...")
        if not config.lakera_enabled or not config.lakera_api_key:
            print("⚠️ Lakera not enabled or no API key")
            return True, None
        
        # Create a simple message format for Lakera
        messages = [{"role": "user", "content": chunk_text}]
        
        # Use RAG-specific project ID if available, otherwise fall back to main project ID
        project_id = config.rag_lakera_project_id or config.lakera_project_id
        
        # Scan the content
        result = await check_interaction(
            messages=messages,
            api_key=config.lakera_api_key,
            project_id=project_id,
            system_prompt=config.system_prompt
        )
        print(f"🔍 Lakera result: {result}")
        
        if result is None:
            # If Lakera is not available, assume safe
            return True, None
        
        # Check if the content is flagged as unsafe
        flagged = result.get("flagged", False)
        if flagged:
            # Get the first detected threat type as the reason
            breakdown = result.get("breakdown", [])
            for detector in breakdown:
                if detector.get("detected", False):
                    reason = detector.get("detector_type", "malicious content")
                    return False, reason
            return False, "malicious content"
        
        return True, None
        
    except Exception as e:
        print(f"Error scanning chunk content: {e}")
        # If scanning fails, assume safe to avoid blocking legitimate content
        return True, None

async def ingest_file(path: str, mimetype: str, meta: Dict[str, Any], db=None) -> Dict[str, Any]:
    """
    Ingest a file into the RAG system using file-type-specific chunking
    Returns dict with source_id, chunks count, and metadata
    """
    try:
        # Read file content based on type
        content = ""
        filename = meta.get("name", "unknown")
        
        if mimetype in ["text/markdown", "text/plain", "text/csv", "application/json"]:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif mimetype == "application/octet-stream" and filename.endswith('.csv'):
            # Handle CSV files detected as octet-stream
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            mimetype = "text/csv"  # Override mimetype for proper chunking
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
        
        # Use file-type-specific chunking
        return await ingest_with_smart_chunking(content, filename, mimetype, meta, db)
        
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

async def ingest_with_smart_chunking(content: str, filename: str, mimetype: str, source_meta: Dict[str, Any], db=None) -> Dict[str, Any]:
    """
    Ingest content using file-type-specific chunking strategies
    """
    global _last_rag_scanning_result
    
    try:
        # Get file-type-specific chunks with metadata
        chunk_data = chunk_by_file_type(content, filename, mimetype)
        
        if not chunk_data:
            return {
                "source_id": "error",
                "chunks": 0,
                "metadata": source_meta
            }
        
        # Extract chunks and metadata
        chunks = [chunk_text for chunk_text, _ in chunk_data]
        chunk_metadata = [chunk_meta for _, chunk_meta in chunk_data]
        
        # Get configuration for content scanning
        if db is None:
            temp_db = next(get_db())
            should_close_db = True
        else:
            temp_db = db
            should_close_db = False
            
        config = temp_db.query(AppConfig).first()
        
        # Scan chunks if RAG content scanning is enabled
        safe_chunks = []
        safe_chunk_metadata = []
        blocked_chunks = 0
        scanning_results = []
        
        print(f"🔍 Config check: rag_content_scanning={config.rag_content_scanning if config else 'None'}, lakera_enabled={config.lakera_enabled if config else 'None'}")
        if config and config.rag_content_scanning and config.lakera_enabled:
            print(f"🔍 Scanning {len(chunks)} chunks for malicious content...")
            
            # Initialize progress tracking
            global _rag_scanning_progress
            _rag_scanning_progress = {
                "isScanning": True,
                "current": 0,
                "total": len(chunks),
                "filename": filename
            }
            
            for i, (chunk_text, chunk_meta) in enumerate(zip(chunks, chunk_metadata)):
                try:
                    # Update progress
                    _rag_scanning_progress["current"] = i + 1
                    
                    is_safe, reason = await scan_chunk_content(chunk_text, config)
                    
                    # Store detailed scanning result
                    scanning_results.append({
                        "chunk_index": i + 1,
                        "chunk_text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                        "is_safe": is_safe,
                        "reason": reason,
                        "chunk_type": chunk_meta.get("chunk_type", "unknown")
                    })
                    
                    if is_safe:
                        safe_chunks.append(chunk_text)
                        safe_chunk_metadata.append(chunk_meta)
                    else:
                        blocked_chunks += 1
                        print(f"🚫 Blocked chunk {i+1}: {reason}")
                        
                except Exception as e:
                    print(f"⚠️ Error scanning chunk {i+1}: {e}")
                    # Include chunk anyway if scanning fails
                    safe_chunks.append(chunk_text)
                    safe_chunk_metadata.append(chunk_meta)
                    scanning_results.append({
                        "chunk_index": i + 1,
                        "chunk_text": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                        "is_safe": True,  # Assume safe if scanning fails
                        "reason": f"Scanning error: {str(e)}",
                        "chunk_type": chunk_meta.get("chunk_type", "unknown")
                    })
            
            # Store the scanning result globally for the frontend to access
            _last_rag_scanning_result = {
                "total_chunks": len(chunks),
                "safe_chunks": len(safe_chunks),
                "blocked_chunks": blocked_chunks,
                "scanning_enabled": True,
                "results": scanning_results,
                "filename": source_meta.get("name", "Unknown"),
                "scan_timestamp": str(uuid.uuid4())  # Simple timestamp replacement
            }
            
            print(f"✅ RAG scanning complete: {len(safe_chunks)} safe chunks, {blocked_chunks} blocked")
            
            # Mark scanning as complete but keep progress for a bit longer
            _rag_scanning_progress = {
                "isScanning": False,
                "current": len(chunks),
                "total": len(chunks),
                "filename": filename
            }
            
            # Clear progress after 5 seconds to allow frontend to detect completion
            import asyncio
            async def clear_progress_later():
                await asyncio.sleep(5)
                global _rag_scanning_progress
                _rag_scanning_progress = None
            
            # Schedule the cleanup (don't await to avoid blocking)
            asyncio.create_task(clear_progress_later())
            
            chunks = safe_chunks
            chunk_metadata = safe_chunk_metadata
        else:
            # Store a result indicating scanning was not performed
            _last_rag_scanning_result = {
                "total_chunks": len(chunks),
                "safe_chunks": len(chunks),
                "blocked_chunks": 0,
                "scanning_enabled": False,
                "results": [],
                "filename": source_meta.get("name", "Unknown"),
                "scan_timestamp": str(uuid.uuid4())
            }
        
        if should_close_db:
            temp_db.close()
        
        # Get embeddings for chunks
        try:
            # Filter out empty or invalid chunks
            valid_chunks = []
            for i, chunk in enumerate(chunks):
                if chunk and isinstance(chunk, str) and chunk.strip():
                    valid_chunks.append(chunk.strip())
                else:
                    print(f"⚠️ Skipping invalid chunk {i}: {repr(chunk)}")
            
            if not valid_chunks:
                print("❌ No valid chunks to embed")
                return {
                    "source_id": "error",
                    "chunks": 0,
                    "metadata": source_meta
                }
            
            print(f"🔍 Getting embeddings for {len(valid_chunks)} valid chunks (filtered from {len(chunks)} total)")
            embeddings = openai_client.get_embeddings(valid_chunks)
            
            # Update chunks and metadata to match valid chunks
            if len(valid_chunks) != len(chunks):
                print(f"⚠️ Filtered chunks: {len(chunks)} -> {len(valid_chunks)}")
                # Re-filter metadata to match valid chunks
                filtered_metadata = []
                valid_chunk_metadata = []
                for i, (chunk, meta) in enumerate(zip(chunks, chunk_metadata)):
                    if chunk and isinstance(chunk, str) and chunk.strip():
                        filtered_metadata.append(meta)
                        valid_chunk_metadata.append(meta)
                chunk_metadata = valid_chunk_metadata
                chunks = valid_chunks
                
        except Exception as e:
            print(f"Embeddings error: {e}")
            raise Exception(f"Failed to get embeddings: {str(e)}. Please configure OpenAI API key.")
        
        # Generate IDs for chunks
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        
        # Combine source metadata with chunk-specific metadata
        combined_metadata = []
        for i, (chunk_meta, source_meta_copy) in enumerate(zip(chunk_metadata, [source_meta.copy()] * len(chunk_metadata))):
            combined_meta = {
                **source_meta_copy,
                **chunk_meta,
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            combined_metadata.append(combined_meta)
        
        # Add to ChromaDB
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=chunk_ids,
            metadatas=combined_metadata
        )
        
        # Save to database
        if db is None:
            db = next(get_db())
            should_close = True
        else:
            should_close = False
            
        rag_source = RagSource(
            name=source_meta.get("name", "Uploaded Content"),
            content=content[:1000] + "..." if len(content) > 1000 else content,  # Store first 1000 chars as preview
            source_type=source_meta.get("source_type", "uploaded"),
            chunks_count=len(chunks)
        )
        db.add(rag_source)
        db.commit()
        
        # Get the ID before closing the session
        source_id = str(rag_source.id)
        
        if should_close:
            db.close()
        
        return {
            "source_id": source_id,
            "chunks": len(chunks),
            "metadata": source_meta
        }
        
    except Exception as e:
        print(f"Smart chunking ingestion error: {e}")
        return {
            "source_id": "error",
            "chunks": 0,
            "metadata": source_meta
        }

async def ingest_markdown(markdown: str, source_meta: Dict[str, Any], db=None) -> Dict[str, Any]:
    """
    Ingest markdown content into RAG system (legacy function for backward compatibility)
    """
    try:
        # Use smart chunking for markdown
        return await ingest_with_smart_chunking(markdown, "generated.md", "text/markdown", source_meta, db)
        
    except Exception as e:
        print(f"Markdown ingestion error: {e}")
        return {
            "source_id": "error",
            "chunks": 0,
            "metadata": source_meta
        }
