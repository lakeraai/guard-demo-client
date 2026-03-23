from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import lakera, llm_client, rag, toolhive
from .models import AppConfig


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

    use_litellm_guardrails = bool(getattr(cfg, "use_litellm", False) and cfg.lakera_enabled and cfg.lakera_api_key)
    # LiteLLM applies on_flagged per named guardrail in config.yaml, not per HTTP request.
    # We pick block vs monitor guardrail names to match Admin lakera_blocking_mode.
    litellm_guardrail_block = (
        (getattr(cfg, "litellm_guardrail_name", None) or "").strip() or "lakera-guard-block"
    )
    litellm_guardrail_monitor = (
        (getattr(cfg, "litellm_guardrail_monitor_name", None) or "").strip() or "lakera-guard-monitor"
    )
    litellm_guardrail = litellm_guardrail_block if lakera_blocking_mode else litellm_guardrail_monitor

    if use_litellm_guardrails:
        print(
            f"🔧 LiteLLM Lakera: request guardrail={litellm_guardrail!r} "
            f"(admin lakera_blocking_mode={lakera_blocking_mode})"
        )

    if cfg.lakera_enabled and lakera_api_key and not use_litellm_guardrails:
        print("🛡️ Checking user input with Lakera...")
        # Prepare messages for Lakera (user only for pre-check, no system prompt)
        lakera_messages = []
        lakera_messages.append({"role": "user", "content": req.message})

        lakera_result = await lakera.check_interaction(
            messages=lakera_messages,
            meta={"session_id": req.session_id} if req.session_id else None,
            api_key=lakera_api_key,
            project_id=lakera_project_id,
            system_prompt=cfg.system_prompt,
        )

        if lakera_result and lakera_result.get("flagged"):
            print(f"⚠️ User input flagged by Lakera: {lakera_result.get('breakdown', [])}")
            if lakera_blocking_mode:
                print("🚫 User input blocked due to Lakera moderation (blocking mode enabled)")
                return AgentResult(
                    response="This content has been moderated by Lakera and found to be in breach of our security policies. Please contact support if you believe this is an error.",
                    citations=[],
                    tool_traces=[],
                    lakera_status=lakera_result,
                )
            else:
                print("📝 User input flagged but allowed through (blocking mode disabled)")
        else:
            print("✅ User input passed Lakera moderation")

    # Step 1: Get context from RAG
    context = await rag.retrieve(req.message)
    citations = []
    if context:
        citations = [
            {"source": doc.get("metadata", {}).get("source")}
            for doc in context
            if doc.get("metadata", {}).get("source") and doc.get("metadata", {}).get("source") != "unknown"
        ]

    # Step 2: Get tools manifest for OpenAI
    tools_manifest = toolhive.openai_tools_manifest(db)
    # Step 3: Prepare messages for OpenAI
    messages = []

    # Add system prompt
    if cfg.system_prompt:
        messages.append({"role": "system", "content": cfg.system_prompt})

    # Add context if available
    if context:
        context_text = "\n\n".join([doc["text"] for doc in context])
        messages.append({"role": "system", "content": f"Context information:\n{context_text}"})

    # Add user message
    messages.append({"role": "user", "content": req.message})

    # Step 4: Call LLM with tools
    try:
        response = llm_client.chat_completion(
            messages=messages,
            model=cfg.openai_model,
            temperature=cfg.temperature,
            tools=tools_manifest if tools_manifest else None,
            config=cfg,
            litellm_guardrail_name=litellm_guardrail if use_litellm_guardrails else None,
            litellm_metadata=(
                {
                    "session_id": req.session_id or "",
                    "guardrail_name": litellm_guardrail,
                    "source": "agentic-demo-chat",
                }
                if use_litellm_guardrails
                else None
            ),
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
                        "raw_result": None,
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
                        lakera_blocking_mode=lakera_blocking_mode,
                    )

                # Add tool result as role: "tool" message
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": tool_result["content_string"],
                    }
                )

                # Add to tool traces
                tool_traces.append({"id": tool_call_id, "name": tool_name, "args": parsed_args, "result": tool_result})

            # Make second call to LLM with tool results
            print("🔧 Making follow-up call to LLM with tool results")
            final_response = llm_client.chat_completion(
                messages=messages,
                model=cfg.openai_model,
                temperature=cfg.temperature,
                config=cfg,
                litellm_guardrail_name=litellm_guardrail if use_litellm_guardrails else None,
                litellm_metadata=(
                    {
                        "session_id": req.session_id or "",
                        "guardrail_name": litellm_guardrail,
                        "source": "agentic-demo-chat",
                    }
                    if use_litellm_guardrails
                    else None
                ),
            )

            # Get final response
            final_assistant_message = final_response["choices"][0]["message"]
            response_text = final_assistant_message["content"]
        else:
            # No tool calls, use the original response
            response_text = assistant_message["content"]

        # Step 5: Post-response Lakera (direct Guard API) for UI / blocking
        lakera_status = None
        if cfg.lakera_enabled and cfg.lakera_api_key and not use_litellm_guardrails:
            print("🛡️ Checking assistant response with Lakera...")
            lakera_messages = [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": response_text or ""},
            ]

            lakera_status = await lakera.check_interaction(
                messages=lakera_messages,
                meta={"session_id": req.session_id} if req.session_id else None,
                api_key=cfg.lakera_api_key,
                project_id=cfg.lakera_project_id,
                system_prompt=cfg.system_prompt,
            )

            if lakera_status and lakera_status.get("flagged"):
                print(f"⚠️ Assistant response flagged by Lakera: {lakera_status.get('breakdown', [])}")
                if lakera_blocking_mode:
                    print("🚫 Assistant response blocked due to Lakera moderation (blocking mode enabled)")
                    response_text = "This content has been moderated by Lakera and found to be in breach of our security policies. Please contact support if you believe this is an error."
                else:
                    print("📝 Assistant response flagged but allowed through (blocking mode disabled)")
            else:
                print("✅ Assistant response passed Lakera moderation")
        elif (
            cfg.lakera_enabled
            and cfg.lakera_api_key
            and use_litellm_guardrails
            and not lakera_blocking_mode
        ):
            # LiteLLM monitor: use /v2/guard/results so we do not log a duplicate /v2/guard screening
            # while still filling the overlay (see https://docs.lakera.ai/docs/api/results).
            print("🛡️ Recording Lakera detector results for UI (LiteLLM monitor mode, /guard/results)...")
            lakera_status = await lakera.get_guard_results_for_ui(
                messages=[
                    {"role": "user", "content": req.message},
                    {"role": "assistant", "content": response_text or ""},
                ],
                meta={"session_id": req.session_id} if req.session_id else None,
                api_key=cfg.lakera_api_key,
                project_id=cfg.lakera_project_id,
                system_prompt=cfg.system_prompt,
            )
            if lakera_status and lakera_status.get("flagged"):
                print("📝 Flagged content shown in Lakera panel; reply left unchanged (monitor mode).")
            else:
                print("✅ Lakera breakdown recorded for UI.")

        return AgentResult(
            response=response_text, citations=citations, tool_traces=tool_traces, lakera_status=lakera_status
        )

    except llm_client.LiteLLMGuardrailError as e:
        lakera_status = e.lakera_status if isinstance(e.lakera_status, dict) else None
        if lakera_status:
            lakera.set_last_result(lakera_status)
        return AgentResult(
            response="This content has been moderated by Lakera and found to be in breach of our security policies. Please contact support if you believe this is an error.",
            citations=citations,
            tool_traces=tool_traces if "tool_traces" in locals() else [],
            lakera_status=lakera_status,
        )
    except Exception as e:
        return AgentResult(
            response=f"I apologize, but I encountered an error: {str(e)}",
            citations=citations,
            tool_traces=tool_traces if "tool_traces" in locals() else [],
            lakera_status=None,
        )
