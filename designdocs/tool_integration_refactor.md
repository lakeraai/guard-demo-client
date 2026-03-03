# 🔧 Refactor Brief: Tool Integration for agent.py & toolhive.py

## Problem
- **agent.py** is pushing tool results into `system` messages. This breaks OpenAI’s tool contract and causes the model to ignore them.
- **toolhive.py**:
  1. Uses a **static regex** to pick an “overarching” MCP tool, which is brittle.
  2. Calls OpenAI to decide tool function calls, but **does not return transaction details** (`id`, `name`, `args`) so that `agent.py` can construct `role:"tool"` messages.

## Correct OpenAI Tool Flow
1. **assistant** replies with `tool_calls` (includes `id`, `name`, `args`).
2. Runtime executes each call.
3. Runtime appends a `tool` role message:
   ```json
   {"role":"tool","tool_call_id":"<id>","name":"<tool name>","content":"<string result>"}
   ```
4. Send updated conversation back to OpenAI; model continues.

**Rules:**
- `tool` message must follow the `assistant` that requested it.
- `tool_call_id` must match.
- `content` must be a string (JSON must be stringified).

Example openai flow:
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "system", "content": "RAG results are...."},  
  {"role": "user", "content": "What’s 2+2?"},
  // 1) model decides to call a tool
  {"role": "assistant",
   "tool_calls": [
     {
       "id": "call_abc123",                // <-- you'll get this from the model
       "type": "function",
       "function": {"name": "math", "arguments": "{\"op\":\"add\",\"a\":2,\"b\":2}"}
     }
   ]
  },
  // 2) you run the tool and RETURN with role=tool, referencing tool_call_id
  {"role": "tool",
   "tool_call_id": "call_abc123",          // <-- must match exactly
   "name": "math",
   "content": "4"                          // string; serialize JSON if needed
  }

---

## Required Changes

### agent.py
- ❌ Don’t append tool results as `system`.
- ✅ After first assistant response:
  - Detect `assistant.tool_calls`.
  - For each call, execute tool via `toolhive.execute`.
  - Append proper `role:"tool"` messages with matching `tool_call_id`.
  - Call OpenAI again with updated messages to get the final `assistant` reply.

**Example snippet:**
```python
resp = openai.chat.completions.create(
  model=cfg.model,
  messages=messages,
  tools=toolhive.openai_tools_manifest(db)
)
assistant_msg = resp.choices[0].message
messages.append(assistant_msg)

if assistant_msg.get("tool_calls"):
    for call in assistant_msg["tool_calls"]:
        result = await toolhive.execute(call["function"]["name"], call["function"]["arguments"], db)
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "name": call["function"]["name"],
            "content": result["content_string"]
        })
    # Continue with updated conversation
    final = openai.chat.completions.create(model=cfg.model, messages=messages)
    return final.choices[0].message.content
```

---

### toolhive.py
- ❌ Remove regex routing.
- ❌ Don’t call OpenAI here to pick tools.
- ✅ Expose two clean functions:

#### 1. Build tools manifest
```python
def openai_tools_manifest(db):
    return [
      {
        "type": "function",
        "function": {
          "name": tool["name"],
          "description": tool["description"],
          "parameters": tool["json_schema"]
        }
      }
      for tool in enabled_tools(db)
    ]
```

#### 2. Execute a tool by name
```python
async def execute(name: str, args: dict, db):
    tool = find_tool_by_name(db, name)
    if not tool:
        return {"status":"error","content_string":f"Unknown tool {name}"}
    if tool["type"] == "mcp":
        raw = await execute_mcp(tool, args, db)
    elif tool["type"] == "http":
        raw = await execute_http(tool, args)
    return {
      "status":"success",
      "content_string": json.dumps(raw) if not isinstance(raw, str) else raw,
      "raw_result": raw
    }
```

---

## Test Cases
- ✅ Single tool call → correct final assistant response.
- ✅ Multiple tool calls handled in sequence.
- ✅ Tool error → error message in `content`.
- ✅ No regex; dynamic tool discovery.
- ✅ Large JSON results are stringified.

---

**Instruction for Cursor:**  
👉 Update `agent.py` and `toolhive.py` to follow this spec. Remove regex routing, implement `openai_tools_manifest` + `execute`, and make sure `agent.py` appends tool results as `role:"tool"` messages, never `system`.  
