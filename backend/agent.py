from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .openai_client import openai_client
from .models import AppConfig
from . import rag, toolhive, lakera

class AgentRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class AgentResult(BaseModel):
    response: str
    citations: List[Dict[str, Any]] = []
    tool_traces: List[Dict[str, Any]] = []
    lakera_status: Optional[Dict[str, Any]] = None

async def run_agent(req: AgentRequest, cfg: AppConfig, db: Session) -> AgentResult:
    """
    Main orchestrator function that coordinates RAG, tools, and OpenAI
    """
    # Step 0: Check user input with Lakera if enabled (pre-response check)
    lakera_api_key = cfg.lakera_api_key if cfg.lakera_enabled else None
    lakera_project_id = cfg.lakera_project_id if cfg.lakera_enabled else None
    lakera_blocking_mode = cfg.lakera_blocking_mode if cfg.lakera_enabled else False
    
    if cfg.lakera_enabled and lakera_api_key:
        print(f"🛡️ Checking user input with Lakera...")
        # Prepare messages for Lakera (user only for pre-check, no system prompt)
        lakera_messages = []
        lakera_messages.append({"role": "user", "content": req.message})
        
        lakera_result = await lakera.check_interaction(
            messages=lakera_messages,
            meta={"session_id": req.session_id} if req.session_id else None,
            api_key=lakera_api_key,
            project_id=lakera_project_id
        )
        
        if lakera_result and lakera_result.get("flagged"):
            print(f"⚠️ User input flagged by Lakera: {lakera_result.get('breakdown', [])}")
            if lakera_blocking_mode:
                print(f"🚫 User input blocked due to Lakera moderation (blocking mode enabled)")
                return AgentResult(
                    response="This content has been moderated by Lakera and found to be in breach of our security policies. Please contact support if you believe this is an error.",
                    citations=[],
                    tool_traces=[],
                    lakera_status=lakera_result
                )
            else:
                print(f"📝 User input flagged but allowed through (blocking mode disabled)")
        else:
            print(f"✅ User input passed Lakera moderation")
    
    # Step 1: Get context from RAG
    context = await rag.retrieve(req.message)
    citations = []
    if context:
        citations = [{"source": doc.get("metadata", {}).get("source")} for doc in context if doc.get("metadata", {}).get("source") and doc.get("metadata", {}).get("source") != "unknown"]
    
    # Step 2: Get tools manifest for OpenAI
    tools_manifest = toolhive.openai_tools_manifest(db)
    # Step 3: Prepare messages for OpenAI
    messages = []
    
    # Add system prompt
    if cfg.system_prompt:
        messages.append({
            "role": "system",
            "content": cfg.system_prompt
        })
    
    # Add context if available
    if context:
        context_text = "\n\n".join([doc["text"] for doc in context])
        messages.append({
            "role": "system",
            "content": f"Context information:\n{context_text}"
        })
     
    
      # Add user message
    messages.append({
        "role": "user",
        "content": req.message
    })     # Step 4: Call OpenAI with tools
    try:
        # Reload config to get latest API key
        openai_client._load_config()
        
        # First call to OpenAI with tools manifest
        response = openai_client.chat_completion(
            messages=messages,
            model=cfg.openai_model,
            temperature=cfg.temperature,
            tools=tools_manifest if tools_manifest else None
        )
        
        # Extract the response
        assistant_message = response["choices"][0]["message"]
        messages.append(assistant_message)  # Add assistant message to conversation
        
        # Initialize tool traces
        tool_traces = []
        
        # Handle tool calls if any
        if assistant_message.get("tool_calls"):
            print(f"🔧 OpenAI requested {len(assistant_message['tool_calls'])} tool calls")
            
            # Execute each tool call
            for tool_call in assistant_message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                tool_call_id = tool_call["id"]
                
                print(f"🔧 Executing tool: {tool_name} with args: {tool_args}")
                
                # Parse arguments
                import json
                try:
                    parsed_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    parsed_args = {}
                
                # Find the tool metadata from the manifest
                tool_metadata = None
                for tool_def in tools_manifest:
                    if tool_def["function"]["name"] == tool_name:
                        tool_metadata = tool_def.get("_tool_metadata")
                        break
                
                if not tool_metadata:
                    tool_result = {
                        "status": "error",
                        "content_string": f"Tool metadata not found for: {tool_name}",
                        "raw_result": None
                    }
                else:
                    # Execute the tool with metadata
                    tool_result = await toolhive.execute(
                        tool_name=tool_name,
                        args=parsed_args,
                        tool_metadata=tool_metadata,
                        db=db,
                        lakera_api_key=lakera_api_key,
                        lakera_project_id=lakera_project_id,
                        lakera_blocking_mode=lakera_blocking_mode
                    )
                
                # Add tool result as role: "tool" message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": tool_result["content_string"]
                })
                
                # Add to tool traces
                tool_traces.append({
                    "id": tool_call_id,
                    "name": tool_name,
                    "args": parsed_args,
                    "result": tool_result
                })
            
            # Make second call to OpenAI with tool results
            print(f"🔧 Making follow-up call to OpenAI with tool results")
            final_response = openai_client.chat_completion(
                messages=messages,
                model=cfg.openai_model,
                temperature=cfg.temperature
            )
            
            # Get final response
            final_assistant_message = final_response["choices"][0]["message"]
            response_text = final_assistant_message["content"]
        else:
            # No tool calls, use the original response
            response_text = assistant_message["content"]
        
        # Step 5: Check assistant response with Lakera if enabled (post-response check)
        lakera_status = None
        if cfg.lakera_enabled and cfg.lakera_api_key:
            print(f"🛡️ Checking assistant response with Lakera...")
            # Prepare messages for Lakera (user + assistant only, no system prompt)
            lakera_messages = []
            lakera_messages.append({"role": "user", "content": req.message})
            lakera_messages.append({"role": "assistant", "content": response_text})
            
            lakera_status = await lakera.check_interaction(
                messages=lakera_messages,
                meta={"session_id": req.session_id} if req.session_id else None,
                api_key=cfg.lakera_api_key,
                project_id=cfg.lakera_project_id
            )
            
            if lakera_status and lakera_status.get("flagged"):
                print(f"⚠️ Assistant response flagged by Lakera: {lakera_status.get('breakdown', [])}")
                if lakera_blocking_mode:
                    print(f"🚫 Assistant response blocked due to Lakera moderation (blocking mode enabled)")
                    response_text = "This content has been moderated by Lakera and found to be in breach of our security policies. Please contact support if you believe this is an error."
                else:
                    print(f"📝 Assistant response flagged but allowed through (blocking mode disabled)")
            else:
                print(f"✅ Assistant response passed Lakera moderation")
        
        return AgentResult(
            response=response_text,
            citations=citations,
            tool_traces=tool_traces,
            lakera_status=lakera_status
        )
        
    except Exception as e:
        return AgentResult(
            response=f"I apologize, but I encountered an error: {str(e)}",
            citations=citations,
            tool_traces=tool_traces if 'tool_traces' in locals() else [],
            lakera_status=None
        )
