from typing import Dict, Any, List, Optional
import json
from sqlalchemy.orm import Session
from .database import get_db
from .models import Tool, MCPToolCapabilities
from . import lakera

async def enabled_tools(db: Session) -> List[Dict[str, Any]]:
    """
    Get all enabled tools from the database
    """
    tools = db.query(Tool).filter(Tool.enabled == True).all()
    return [
        {
            "id": tool.id,
            "name": tool.name,
            "type": tool.type,
            "description": tool.description,
            "endpoint": tool.endpoint,
            "enabled": tool.enabled
        }
        for tool in tools
    ]

async def get_stored_capabilities(tool_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """
    Get stored capabilities for a tool
    """
    capabilities = db.query(MCPToolCapabilities).filter(MCPToolCapabilities.tool_id == tool_id).first()
    if capabilities:
        return {
            "tool_name": capabilities.tool_name,
            "server_name": capabilities.server_name,
            "session_info": capabilities.session_info,
            "discovery_results": capabilities.discovery_results,
            "last_discovered": capabilities.last_discovered.isoformat() if capabilities.last_discovered else None
        }
    return None

async def store_capabilities(tool_id: int, tool_name: str, discovery_result: Dict[str, Any], db: Session) -> None:
    """
    Store discovered capabilities for a tool
    """
    # Check if capabilities already exist
    existing = db.query(MCPToolCapabilities).filter(MCPToolCapabilities.tool_id == tool_id).first()
    
    if existing:
        # Update existing
        existing.tool_name = tool_name
        existing.server_name = discovery_result.get("server_name", "")
        existing.session_info = discovery_result.get("session_info")
        existing.discovery_results = discovery_result.get("discovery_results", {})
        existing.last_discovered = discovery_result.get("last_discovered")
    else:
        # Create new
        capabilities = MCPToolCapabilities(
            tool_id=tool_id,
            tool_name=tool_name,
            server_name=discovery_result.get("server_name", ""),
            session_info=discovery_result.get("session_info"),
            discovery_results=discovery_result.get("discovery_results", {}),
            last_discovered=discovery_result.get("last_discovered")
        )
        db.add(capabilities)
    
    db.commit()

def openai_tools_manifest(db: Session) -> List[Dict[str, Any]]:
    """
    Build OpenAI tools manifest from enabled tools in database
    Include database tool metadata so execute() can use it directly
    """
    tools = db.query(Tool).filter(Tool.enabled == True).all()
    manifest = []
    
    for tool in tools:
        # Get stored capabilities if available
        capabilities = db.query(MCPToolCapabilities).filter(MCPToolCapabilities.tool_id == tool.id).first()
        
        if capabilities and capabilities.discovery_results:
            # Use discovered tools from MCP capabilities
            discovery = capabilities.discovery_results
            tools_list = discovery.get("tools_list_params_0", {}).get("response", {}).get("result", {}).get("tools", [])
            
            for mcp_tool in tools_list:
                manifest.append({
                    "type": "function",
                    "function": {
                        "name": mcp_tool.get("name", "unknown"),
                        "description": mcp_tool.get("description", "")[:512],
                        "parameters": mcp_tool.get("inputSchema", {"type": "object", "properties": {}})
                    },
                    # Include database tool metadata for execution
                    "_tool_metadata": {
                        "db_tool_id": tool.id,
                        "db_tool_name": tool.name,
                        "db_tool_type": tool.type,
                        "db_tool_endpoint": tool.endpoint,
                        "db_tool_description": tool.description
                    }
                })
        else:
            # Fallback to basic tool definition
            manifest.append({
                "type": "function", 
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"Tool: {tool.name}",
                    "parameters": {"type": "object", "properties": {}}
                },
                # Include database tool metadata for execution
                "_tool_metadata": {
                    "db_tool_id": tool.id,
                    "db_tool_name": tool.name,
                    "db_tool_type": tool.type,
                    "db_tool_endpoint": tool.endpoint,
                    "db_tool_description": tool.description
                }
            })
    
    return manifest

async def execute(tool_name: str, args: Dict[str, Any], tool_metadata: Dict[str, Any], db: Session, lakera_api_key: Optional[str] = None, lakera_project_id: Optional[str] = None, lakera_blocking_mode: bool = True, enable_multi_step: bool = False) -> Dict[str, Any]:
    """
    Execute a specific tool using the metadata provided by OpenAI's tool selection
    Returns standardized result with content_string for OpenAI integration
    """
    print(f"🔧 Executing tool: {tool_name} with args: {args}")
    print(f"🔧 Tool metadata: {tool_metadata}")
    
    # Use the tool metadata directly - no database lookup needed
    tool_info = {
        "id": tool_metadata["db_tool_id"],
        "name": tool_metadata["db_tool_name"],
        "type": tool_metadata["db_tool_type"],
        "endpoint": tool_metadata["db_tool_endpoint"],
        "description": tool_metadata["db_tool_description"]
    }
    
    try:
        # Execute the tool based on its type
        if tool_info["type"] == "mcp":
            if enable_multi_step:
                raw_result = await execute_mcp_tool_multi_step(tool_info, args, db, lakera_api_key, lakera_project_id, lakera_blocking_mode, tool_name)
            else:
                raw_result = await execute_mcp_tool(tool_info, args, db, tool_name)
        elif tool_info["type"] == "http":
            if enable_multi_step:
                raw_result = await execute_http_tool_multi_step(tool_info, args, lakera_api_key, lakera_project_id, lakera_blocking_mode, tool_name)
            else:
                raw_result = await execute_http_tool(tool_info, args, tool_name)
        else:
            return {
                "status": "error",
                "content_string": f"Unsupported tool type: {tool_info['type']}",
                "raw_result": None
            }
        
        # Moderate tool response with Lakera if API key is available
        if lakera_api_key and raw_result.get("status") == "success" and raw_result.get("content"):
            print(f"🛡️ Moderating tool response with Lakera...")
            moderated_result = await moderate_tool_response(
                tool_name=tool_name,
                tool_content=raw_result["content"],
                lakera_api_key=lakera_api_key,
                lakera_project_id=lakera_project_id
            )
            
            if moderated_result.get("flagged"):
                print(f"⚠️ Tool response flagged by Lakera: {moderated_result.get('breakdown', [])}")
                raw_result["lakera_moderation"] = moderated_result
                
                if lakera_blocking_mode:
                    # Blocking mode: Replace content with security message
                    raw_result["content"] = "This content has been moderated by Lakera and found to be in breach of our security policies. Please contact support if you believe this is an error."
                    print(f"🚫 Content blocked due to Lakera moderation (blocking mode enabled)")
                else:
                    # Non-blocking mode: Log but allow content through
                    print(f"📝 Content flagged but allowed through (blocking mode disabled)")
            else:
                print(f"✅ Tool response passed Lakera moderation")
                raw_result["lakera_moderation"] = moderated_result
        
        # Convert result to string for OpenAI
        if raw_result.get("status") == "success":
            content = raw_result.get("content", "Tool executed successfully")
            if isinstance(content, (dict, list)):
                import json
                content_string = json.dumps(content, indent=2)
            else:
                content_string = str(content)
        else:
            error_msg = raw_result.get("error", "Unknown error")
            content_string = f"Tool error: {error_msg}"
        
        return {
            "status": raw_result.get("status", "error"),
            "content_string": content_string,
            "raw_result": raw_result
        }
        
    except Exception as e:
        print(f"❌ Error executing tool {tool_name}: {e}")
        return {
            "status": "error",
            "content_string": f"Tool execution failed: {str(e)}",
            "raw_result": {"error": str(e)}
        }


async def execute_mcp_tool(tool: Dict[str, Any], args: Dict[str, Any], db: Session, function_name: str) -> Dict[str, Any]:
    """
    Execute an MCP tool using our existing OpenAI client and MCP transport
    """
    try:
        endpoint = tool["endpoint"]
        print(f"🔧 Executing MCP tool: {tool['name']} at {endpoint}")
        
        # Use our existing OpenAI client
        from .openai_client import openai_client
        from .mcp import build_transport, mcp_initialize, try_list, mcp_call
        
        # Reload config to get latest API key
        openai_client._load_config()
        
        if not openai_client.client:
            return {
                "status": "error",
                "error": "OpenAI client not configured",
                "tool_name": tool["name"],
                "details": "Please configure the OpenAI API key in the admin interface"
            }
        
        # Build the appropriate transport (HTTP or SSE)
        transport = build_transport(endpoint)
        print(f"🔧 Built transport for {endpoint}")
        
        try:
            # Initialize MCP connection
            init_result = mcp_initialize(transport)
            print(f"🔧 MCP initialized: {init_result}")
            
            # Try to discover available tools
            tools_list = []
            try:
                tools_result = try_list(transport, "tools/list")
                tools_list = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
                print(f"🔧 Discovered {len(tools_list)} tools: {[t.get('name', 'unknown') for t in tools_list]}")
            except Exception as e:
                print(f"🔧 Could not discover tools: {e}")
                tools_list = []
            
            # Find the specific tool to call from the tools list
            if tools_list:
                # Look for the tool by name in the discovered tools (case-insensitive)
                target_tool = None
                for t in tools_list:
                    if t.get("name", "").lower() == function_name.lower():
                        target_tool = t
                        break
                
                if target_tool:
                    print(f"🔧 Found target tool: {target_tool['name']} with args: {args}")
                    
                    # Call the MCP tool directly with provided args
                    result = mcp_call(transport, "tools/call", {"name": target_tool["name"], "arguments": args})
                    
                    print(f"🔧 Tool execution successful: {str(result)[:200]}...")
                    
                    # Check if the MCP result indicates an error
                    if isinstance(result, dict) and result.get("isError"):
                        return {
                            "status": "error",
                            "error": f"MCP tool returned error: {result.get('content', 'Unknown error')}",
                            "tool_name": tool["name"],
                            "method_used": "direct_call",
                            "result": result
                        }
                    else:
                        return {
                            "status": "success",
                            "content": f"Tool '{target_tool['name']}' executed successfully. Result: {json.dumps(result, indent=2)}",
                            "tool_name": tool["name"],
                            "method_used": "direct_call",
                            "result": result
                        }
                else:
                    return {
                        "status": "error",
                        "error": f"Tool '{function_name}' not found in MCP server capabilities",
                        "tool_name": tool["name"],
                        "details": f"Available tools: {[t.get('name', 'unknown') for t in tools_list]}"
                    }
            else:
                # No tools discovered, try prompts if available
                try:
                    prompts_result = try_list(transport, "prompts/list")
                    prompts_list = prompts_result.get("prompts", []) if isinstance(prompts_result, dict) else []
                    
                    if prompts_list:
                        # Use the first available prompt
                        prompt = prompts_list[0]
                        prompt_name = prompt.get("name", "default")
                        
                        # Call the prompt
                        result = mcp_call(transport, "prompts/call", {
                            "name": prompt_name,
                            "arguments": {"input": str(args)}
                        })
                        
                        return {
                            "status": "success",
                            "content": f"Prompt '{prompt_name}' executed. Result: {json.dumps(result, indent=2)}",
                            "tool_name": tool["name"],
                            "method_used": "prompt_based",
                            "selected_prompt": prompt_name,
                            "result": result
                        }
                    else:
                        return {
                            "status": "error",
                            "error": "No tools or prompts available",
                            "tool_name": tool["name"],
                            "details": "The MCP server does not expose any tools or prompts"
                        }
                        
                except Exception as e:
                    return {
                        "status": "error",
                        "error": f"No tools available and prompts failed: {str(e)}",
                        "tool_name": tool["name"],
                        "details": "The MCP server may not support standard MCP protocols"
                    }
                
        except Exception as e:
            print(f"❌ Tool execution failed: {e}")
            return {
                "status": "error",
                "error": f"Tool execution failed: {str(e)}",
                "tool_name": tool["name"],
                "details": "The MCP server may not support the requested operation"
            }
        finally:
            # Clean up the transport
            try:
                transport.close()
            except Exception:
                pass
                        
    except Exception as mcp_error:
        print(f"❌ MCP connection/communication error: {mcp_error}")
        import traceback
        traceback.print_exc()
        
        # Return a more informative error
        return {
            "status": "error",
            "error": f"MCP connection failed: {str(mcp_error)}",
            "tool_name": tool["name"],
            "details": "The MCP server may be unreachable or there may be a protocol mismatch"
        }

async def execute_http_tool(tool: Dict[str, Any], args: Dict[str, Any], function_name: str) -> Dict[str, Any]:
    """
    Execute an HTTP tool using MCP transport with autofix for SSE detection
    """
    try:
        endpoint = tool["endpoint"]
        print(f"🔧 Executing HTTP tool: {tool['name']} at {endpoint}")
        
        # Use the mcp_example's transport detection and autofix logic
        from .mcp import build_transport, mcp_initialize, try_list, mcp_call, HTTPTransport, SSETransport
        
        # Build the appropriate transport (HTTP or SSE)
        transport = build_transport(endpoint)
        print(f"🔧 Built transport for {endpoint}")
        
        try:
            # Initialize MCP connection
            init_result = mcp_initialize(transport)
            print(f"🔧 MCP initialized: {init_result}")
            
            # Try to discover available tools
            tools_list = []
            try:
                tools_result = try_list(transport, "tools/list")
                tools_list = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
                print(f"🔧 Discovered {len(tools_list)} tools: {[t.get('name', 'unknown') for t in tools_list]}")
            except Exception as e:
                print(f"🔧 Could not discover tools: {e}")
                tools_list = []
            
            # Find the specific tool to call from the tools list
            if tools_list:
                # Look for the tool by name in the discovered tools (case-insensitive)
                target_tool = None
                for t in tools_list:
                    if t.get("name", "").lower() == function_name.lower():
                        target_tool = t
                        break
                
                if target_tool:
                    print(f"🔧 Found target tool: {target_tool['name']} with args: {args}")
                    
                    # Call the MCP tool directly with provided args
                    result = mcp_call(transport, "tools/call", {"name": target_tool["name"], "arguments": args})
                    
                    print(f"🔧 Tool execution successful: {str(result)[:200]}...")
                    
                    # Check if the MCP result indicates an error
                    if isinstance(result, dict) and result.get("isError"):
                        return {
                            "status": "error",
                            "error": f"MCP tool returned error: {result.get('content', 'Unknown error')}",
                            "tool_name": tool["name"],
                            "method_used": "direct_call",
                            "result": result
                        }
                    else:
                        return {
                            "status": "success",
                            "content": f"Tool '{target_tool['name']}' executed successfully. Result: {json.dumps(result, indent=2)}",
                            "tool_name": tool["name"],
                            "method_used": "direct_call",
                            "result": result
                        }
                else:
                    return {
                        "status": "error",
                        "error": f"Tool '{function_name}' not found in MCP server capabilities",
                        "tool_name": tool["name"],
                        "details": f"Available tools: {[t.get('name', 'unknown') for t in tools_list]}"
                    }
            else:
                return {
                    "status": "error",
                    "error": "No tools found",
                    "tool_name": tool["name"],
                    "details": "The MCP server does not expose any tools"
                }
                
        except RuntimeError as e:
            # Handle the SSE_BODY_ON_HTTP error with autofix
            msg = str(e)
            sse_hint = ("SSE_BODY_ON_HTTP" in msg) or ("text/event-stream" in msg) or ("event:" in msg)
            if isinstance(transport, HTTPTransport) and sse_hint:
                print(f"🔧 Detected SSE endpoint, retrying with SSE transport")
                try:
                    transport.close()
                except Exception:
                    pass
                transport = SSETransport(endpoint)
                
                # Retry with SSE transport
                init_result = mcp_initialize(transport)
                print(f"🔧 SSE MCP initialized: {init_result}")
                
                # Try to discover tools again
                tools_result = try_list(transport, "tools/list")
                tools_list = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
                print(f"🔧 SSE Discovered {len(tools_list)} tools: {[t.get('name', 'unknown') for t in tools_list]}")
                
                # Find the specific tool to call from the tools list
                if tools_list:
                    # Look for the tool by name in the discovered tools (case-insensitive)
                    target_tool = None
                    for t in tools_list:
                        if t.get("name", "").lower() == function_name.lower():
                            target_tool = t
                            break
                    
                    if target_tool:
                        print(f"🔧 SSE Found target tool: {target_tool['name']} with args: {args}")
                        
                        # Call the MCP tool directly with provided args
                        result = mcp_call(transport, "tools/call", {"name": target_tool["name"], "arguments": args})
                        
                        print(f"🔧 SSE Tool execution successful: {str(result)[:200]}...")
                        
                        # Check if the MCP result indicates an error
                        if isinstance(result, dict) and result.get("isError"):
                            return {
                                "status": "error",
                                "error": f"MCP tool returned error: {result.get('content', 'Unknown error')}",
                                "tool_name": tool["name"],
                                "method_used": "mcp_sse_direct_call",
                                "result": result
                            }
                        else:
                            return {
                                "status": "success",
                                "content": f"Tool '{target_tool['name']}' executed successfully. Result: {json.dumps(result, indent=2)}",
                                "tool_name": tool["name"],
                                "method_used": "mcp_sse_direct_call",
                                "result": result
                            }
                    else:
                        return {
                            "status": "error",
                            "error": f"Tool '{function_name}' not found in MCP server capabilities",
                            "tool_name": tool["name"],
                            "details": f"Available tools: {[t.get('name', 'unknown') for t in tools_list]}"
                        }
                else:
                    return {
                        "status": "error",
                        "error": "No tools found after SSE retry",
                        "tool_name": tool["name"],
                        "details": "The MCP server does not expose any tools"
                    }
            else:
                raise e
                
        except Exception as e:
            print(f"❌ Tool execution failed: {e}")
            return {
                "status": "error",
                "error": f"Tool execution failed: {str(e)}",
                "tool_name": tool["name"],
                "details": "The MCP server may not support the requested operation"
            }
        finally:
            # Clean up the transport
            try:
                transport.close()
            except Exception:
                pass
                
    except Exception as mcp_error:
        print(f"❌ MCP connection/communication error: {mcp_error}")
        import traceback
        traceback.print_exc()
        
        # Return a more informative error
        return {
            "status": "error",
            "error": f"MCP connection failed: {str(mcp_error)}",
            "tool_name": tool["name"],
            "details": "The MCP server may be unreachable or there may be a protocol mismatch"
        }

async def moderate_tool_response(tool_name: str, tool_content: str, lakera_api_key: str, lakera_project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Moderate tool response content using Lakera to prevent prompt injection
    Uses "tool" role as specified by the user
    """
    try:
        # Prepare messages for Lakera moderation using "tool" role
        messages = [
            {"role": "tool", "content": tool_content}
        ]
        
        # Check with Lakera
        lakera_status = await lakera.check_interaction(
            messages=messages,
            meta={"tool_name": tool_name, "content_type": "tool_response"},
            api_key=lakera_api_key,
            project_id=lakera_project_id
        )
        
        return lakera_status
        
    except Exception as e:
        print(f"❌ Lakera moderation error: {e}")
        return {
            "flagged": False,
            "error": str(e),
            "note": "Moderation failed, allowing content through"
        }

async def discover_mcp_tool_capabilities_sync(tool: Dict[str, Any], lakera_api_key: Optional[str] = None, lakera_project_id: Optional[str] = None, lakera_blocking_mode: bool = True) -> Dict[str, Any]:
    """
    Discover the capabilities of an MCP tool using the same autofix approach as mcp_example.py
    """
    try:
        from datetime import datetime
        
        endpoint = tool["endpoint"]
        print(f"🔍 Discovering capabilities for {tool['name']} at {endpoint}")
        
        # Use our existing MCP transport functions
        from .mcp import build_transport, mcp_initialize, try_list, HTTPTransport, SSETransport
        
        # Try HTTP first, then autofix to SSE if needed (same as mcp_example.py)
        transport = build_transport(endpoint)
        print(f"🔧 Built transport for {endpoint}")
        
        try:
            # Initialize MCP connection
            init_result = mcp_initialize(transport)
            print(f"🔧 MCP initialized: {init_result}")
            
            # Try to discover available tools
            tools_list = []
            try:
                tools_result = try_list(transport, "tools/list")
                tools_list = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
                print(f"🔧 Discovered {len(tools_list)} tools: {[t.get('name', 'unknown') for t in tools_list]}")
                
                # Moderate tool discovery results with Lakera if API key is available
                if lakera_api_key and tools_result:
                    print(f"🛡️ Moderating tool discovery results with Lakera...")
                    tools_result_str = str(tools_result)
                    moderated_result = await moderate_tool_response(
                        tool_name=f"{tool['name']}_discovery",
                        tool_content=tools_result_str,
                        lakera_api_key=lakera_api_key,
                        lakera_project_id=lakera_project_id
                    )
                    
                    if moderated_result.get("flagged"):
                        print(f"⚠️ Tool discovery results flagged by Lakera: {moderated_result.get('breakdown', [])}")
                        # Store moderation result but don't block discovery
                        tools_result["lakera_moderation"] = moderated_result
                    else:
                        print(f"✅ Tool discovery results passed Lakera moderation")
                        tools_result["lakera_moderation"] = moderated_result
                        
            except Exception as e:
                print(f"🔧 Could not discover tools: {e}")
                tools_list = []
            
            # Try to discover prompts
            prompts_list = []
            try:
                prompts_result = try_list(transport, "prompts/list")
                prompts_list = prompts_result.get("prompts", []) if isinstance(prompts_result, dict) else []
                print(f"🔧 Discovered {len(prompts_list)} prompts: {[p.get('name', 'unknown') for p in prompts_list]}")
            except Exception as e:
                print(f"🔧 Could not discover prompts: {e}")
                prompts_list = []
            
            # Store the discovery results
            discovery_results = {
                "tools_list_params_0": {
                    "params": {},
                    "response": {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": {"tools": tools_list}
                    }
                },
                "prompts_list": {
                    "params": {},
                    "response": {
                        "jsonrpc": "2.0", 
                        "id": 2,
                        "result": {"prompts": prompts_list}
                    }
                }
            }
            
            return {
                "tool_name": tool["name"],
                "server_name": init_result.get("serverInfo", {}).get("name", "unknown"),
                "session_info": init_result,
                "discovery_results": discovery_results,
                "last_discovered": datetime.utcnow(),
                "status": "success"
            }
            
        except RuntimeError as e:
            # Handle the SSE_BODY_ON_HTTP error with autofix (same as mcp_example.py)
            msg = str(e)
            sse_hint = ("SSE_BODY_ON_HTTP" in msg) or ("text/event-stream" in msg) or ("event:" in msg)
            if isinstance(transport, HTTPTransport) and sse_hint:
                print(f"🔧 Detected SSE endpoint, retrying with SSE transport")
                try:
                    transport.close()
                except Exception:
                    pass
                transport = SSETransport(endpoint)
                
                # Retry with SSE transport
                init_result = mcp_initialize(transport)
                print(f"🔧 SSE MCP initialized: {init_result}")
                
                # Try to discover tools again
                tools_list = []
                try:
                    tools_result = try_list(transport, "tools/list")
                    tools_list = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
                    print(f"🔧 SSE Discovered {len(tools_list)} tools: {[t.get('name', 'unknown') for t in tools_list]}")
                    
                    # Moderate tool discovery results with Lakera if API key is available
                    if lakera_api_key and tools_result:
                        print(f"🛡️ Moderating tool discovery results with Lakera...")
                        tools_result_str = str(tools_result)
                        moderated_result = await moderate_tool_response(
                            tool_name=f"{tool['name']}_discovery",
                            tool_content=tools_result_str,
                            lakera_api_key=lakera_api_key,
                            lakera_project_id=lakera_project_id
                        )
                        
                        if moderated_result.get("flagged"):
                            print(f"⚠️ Tool discovery results flagged by Lakera: {moderated_result.get('breakdown', [])}")
                            # Store moderation result but don't block discovery
                            tools_result["lakera_moderation"] = moderated_result
                        else:
                            print(f"✅ Tool discovery results passed Lakera moderation")
                            tools_result["lakera_moderation"] = moderated_result
                            
                except Exception as e:
                    print(f"🔧 SSE Could not discover tools: {e}")
                    tools_list = []
                
                # Try to discover prompts again
                prompts_list = []
                try:
                    prompts_result = try_list(transport, "prompts/list")
                    prompts_list = prompts_result.get("prompts", []) if isinstance(prompts_result, dict) else []
                    print(f"🔧 SSE Discovered {len(prompts_list)} prompts: {[p.get('name', 'unknown') for p in prompts_list]}")
                except Exception as e:
                    print(f"🔧 SSE Could not discover prompts: {e}")
                    prompts_list = []
                
                # Store the discovery results
                discovery_results = {
                    "tools_list_params_0": {
                        "params": {},
                        "response": {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {"tools": tools_list}
                        }
                    },
                    "prompts_list": {
                        "params": {},
                        "response": {
                            "jsonrpc": "2.0", 
                            "id": 2,
                            "result": {"prompts": prompts_list}
                        }
                    }
                }
                
                return {
                    "tool_name": tool["name"],
                    "server_name": init_result.get("serverInfo", {}).get("name", "unknown"),
                    "session_info": init_result,
                    "discovery_results": discovery_results,
                    "last_discovered": datetime.utcnow(),
                    "status": "success"
                }
            else:
                raise e
                
        except Exception as e:
            print(f"❌ Tool discovery failed: {e}")
            return {
                "tool_name": tool["name"],
                "status": "error",
                "error": f"Tool discovery failed: {str(e)}"
            }
        finally:
            # Clean up the transport
            try:
                transport.close()
            except Exception:
                pass
                
    except Exception as e:
        print(f"❌ MCP connection/communication error: {e}")
        return {
            "tool_name": tool["name"],
            "status": "error",
            "error": f"MCP connection failed: {str(e)}"
        }

async def execute_mcp_tool_multi_step(tool: Dict[str, Any], args: Dict[str, Any], db: Session, lakera_api_key: Optional[str] = None, lakera_project_id: Optional[str] = None, lakera_blocking_mode: bool = True, function_name: str = None) -> Dict[str, Any]:
    """
    Execute an MCP tool with multi-step capability (like mcp_example2.py)
    This allows the tool to make multiple calls back-to-back to solve complex problems
    """
    try:
        endpoint = tool["endpoint"]
        print(f"🔧 Executing MCP tool (multi-step): {tool['name']} at {endpoint}")
        
        # Use our existing OpenAI client
        from .openai_client import openai_client
        from .mcp import build_transport, mcp_initialize, try_list, mcp_call, HTTPTransport, SSETransport
        
        # Reload config to get latest API key
        openai_client._load_config()
        
        if not openai_client.client:
            return {
                "status": "error",
                "error": "OpenAI client not configured",
                "tool_name": tool["name"],
                "details": "Please configure the OpenAI API key in the admin interface"
            }
        
        # Build the appropriate transport (HTTP or SSE)
        transport = build_transport(endpoint)
        print(f"🔧 Built transport for {endpoint}")
        
        try:
            # Initialize MCP connection
            init_result = mcp_initialize(transport)
            print(f"🔧 MCP initialized: {init_result}")
            
            # Try to discover available tools
            tools_list = []
            try:
                tools_result = try_list(transport, "tools/list")
                tools_list = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
                print(f"🔧 Discovered {len(tools_list)} tools: {[t.get('name', 'unknown') for t in tools_list]}")
            except Exception as e:
                print(f"🔧 Could not discover tools: {e}")
                tools_list = []
            
            if not tools_list:
                return {
                    "status": "error",
                    "error": "No tools available for multi-step execution",
                    "tool_name": tool["name"],
                    "details": "The MCP server does not expose any tools"
                }
            
            # Convert MCP tools to OpenAI format
            openai_tools = []
            tools_map = {}
            for t in tools_list:
                if isinstance(t, dict) and "name" in t:
                    tools_map[t["name"]] = t
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", "")[:512],
                            "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
                        }
                    })
            
            # Build initial message with user input
            messages = []
            if args:
                # Convert args to a natural language prompt
                user_prompt = f"Please help me with: {json.dumps(args, indent=2)}"
            else:
                user_prompt = f"Please help me with the {tool['name']} tool"
            
            messages.append({"role": "user", "content": user_prompt})
            
            # Multi-step tool loop (like mcp_example2.py)
            max_loops = 12  # prevent infinite loops
            while max_loops > 0:
                max_loops -= 1
                
                # Get OpenAI response
                resp = openai_client.client.chat.completions.create(
                    model=openai_client.model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto"
                )
                
                msg = resp.choices[0].message
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": msg.tool_calls
                } if msg.tool_calls else {
                    "role": "assistant", 
                    "content": msg.content
                })
                
                # If the model answered directly, we're done
                if not msg.tool_calls:
                    final_content = msg.content or "(no answer)"
                    return {
                        "status": "success",
                        "content": f"Multi-step execution completed: {final_content}",
                        "tool_name": tool["name"],
                        "method_used": "multi_step_execution",
                        "result": {"final_response": final_content}
                    }
                
                # Execute each tool call
                for call in msg.tool_calls:
                    name = call.function.name
                    args_json = call.function.arguments or "{}"
                    
                    try:
                        call_args = json.loads(args_json)
                    except Exception as e:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps({"error": f"Invalid JSON args for '{name}': {e}"})
                        })
                        continue
                    
                    # Call MCP tool
                    try:
                        result = mcp_call(transport, "tools/call", {"name": name, "arguments": call_args})
                        
                        # Moderate result if Lakera is available
                        if lakera_api_key:
                            result_str = json.dumps(result, ensure_ascii=False)
                            moderated_result = await moderate_tool_response(
                                tool_name=name,
                                tool_content=result_str,
                                lakera_api_key=lakera_api_key,
                                lakera_project_id=lakera_project_id
                            )
                            
                            if moderated_result.get("flagged") and lakera_blocking_mode:
                                result = {"error": "Content moderated by Lakera"}
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(result, ensure_ascii=False)
                        })
                        
                    except Exception as e:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps({"error": f"MCP tool '{name}' call failed: {e}"})
                        })
            
            return {
                "status": "error",
                "error": "Multi-step execution stopped after too many iterations",
                "tool_name": tool["name"],
                "details": "Safety cap reached (12 iterations)"
            }
                
        except RuntimeError as e:
            # Handle the SSE_BODY_ON_HTTP error with autofix
            msg = str(e)
            sse_hint = ("SSE_BODY_ON_HTTP" in msg) or ("text/event-stream" in msg) or ("event:" in msg)
            if isinstance(transport, HTTPTransport) and sse_hint:
                print(f"🔧 Detected SSE endpoint, retrying with SSE transport")
                try:
                    transport.close()
                except Exception:
                    pass
                transport = SSETransport(endpoint)
                
                # Retry with SSE transport (recursive call)
                return await execute_mcp_tool_multi_step(tool, args, db, lakera_api_key, lakera_project_id, lakera_blocking_mode)
            else:
                raise e
                
        except Exception as e:
            print(f"❌ Multi-step tool execution failed: {e}")
            return {
                "status": "error",
                "error": f"Multi-step tool execution failed: {str(e)}",
                "tool_name": tool["name"],
                "details": "The MCP server may not support the requested operation"
            }
        finally:
            # Clean up the transport
            try:
                transport.close()
            except Exception:
                pass
                        
    except Exception as mcp_error:
        print(f"❌ MCP multi-step connection/communication error: {mcp_error}")
        import traceback
        traceback.print_exc()
        
        return {
            "status": "error",
            "error": f"MCP multi-step connection failed: {str(mcp_error)}",
            "tool_name": tool["name"],
            "details": "The MCP server may be unreachable or there may be a protocol mismatch"
        }

async def execute_http_tool_multi_step(tool: Dict[str, Any], args: Dict[str, Any], lakera_api_key: Optional[str] = None, lakera_project_id: Optional[str] = None, lakera_blocking_mode: bool = True, function_name: str = None) -> Dict[str, Any]:
    """
    Execute an HTTP tool with multi-step capability
    This is essentially the same as MCP multi-step since HTTP tools use MCP transport
    """
    # For HTTP tools, we use the same multi-step logic as MCP tools
    # since they both use the MCP transport layer
    return await execute_mcp_tool_multi_step(tool, args, None, lakera_api_key, lakera_project_id, lakera_blocking_mode)
