#!/usr/bin/env python3
import os
import re
import json
import time
import queue
import threading
from typing import Dict, Any, Optional, List, Tuple

import requests
from jsonschema import validate, ValidationError
from urllib.parse import urljoin, urlparse, parse_qs

# ---------------- OpenAI (Chat Completions) --------------
try:
    from openai import OpenAI
except Exception:
    raise RuntimeError("OpenAI SDK not found. Install: pip install openai")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

INIT_PARAMS = {
    "protocolVersion": "2025-03-26",
    "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
    "clientInfo": {"name": "OpenAI-MCP-Client", "version": "0.6.0"},
}

# =========================================================
#                        TRANSPORTS
# =========================================================

class MCPTransport:
    def initialize(self) -> Dict[str, Any]: ...
    def send_request(self, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]: ...
    def send_notification(self, method: str, params: Optional[Dict[str, Any]]) -> None: ...
    def close(self) -> None: ...

# ----------------------- HTTP ----------------------------

class HTTPTransport(MCPTransport):
    """
    Plain HTTP JSON-RPC transport.
    - POST all messages to base_url
    - Echo 'Mcp-Session-Id' after the server provides it (if any)
    - Accepts servers that demand Accept: 'application/json, text/event-stream' on POST
    """
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id: Optional[str] = None
        self._rpc_id = 0

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post_raw(self, payload: Dict[str, Any]) -> Tuple[requests.Response, str]:
        r = self.session.post(self.base_url, json=payload, timeout=self.timeout, headers=self._headers())
        sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        return r, (r.text or "")

    def _parse_json(self, r: requests.Response, body: str) -> Dict[str, Any]:
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} from {self.base_url}: {body}")
        if body.lstrip().startswith("event:"):
            # POST returned SSE block → indicates SSE transport endpoint
            raise RuntimeError("SSE_BODY_ON_HTTP")
        try:
            return r.json()
        except Exception:
            raise RuntimeError(f"Invalid JSON response from {self.base_url}: {body[:300]}")

    def initialize(self) -> Dict[str, Any]:
        req = {"jsonrpc": "2.0", "id": self._next_id(), "method": "initialize", "params": INIT_PARAMS}
        r, body = self._post_raw(req)
        res = self._parse_json(r, body)
        # Required notification (best-effort)
        self.session.post(self.base_url, json={"jsonrpc": "2.0", "method": "initialized", "params": {}},
                          timeout=self.timeout, headers=self._headers())
        if "error" in res:
            raise RuntimeError(f"MCP error {res['error']}")
        return res.get("result", res)

    def send_request(self, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        req = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            req["params"] = params
        r, body = self._post_raw(req)
        res = self._parse_json(r, body)
        if "error" in res:
            raise RuntimeError(f"MCP error {res['error']}")
        return res.get("result", res)

    def send_notification(self, method: str, params: Optional[Dict[str, Any]]) -> None:
        note = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            note["params"] = params
        self.session.post(self.base_url, json=note, timeout=self.timeout, headers=self._headers())

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

# ------------------------ SSE ----------------------------

class SSETransport(MCPTransport):
    """
    HTTP + SSE transport (2024-11-05 style + legacy endpoint negotiation):
      - GET <base_url>/sse with Accept: text/event-stream (events)
      - Server emits 'event: endpoint' → POST target (often /messages?session_id=...)
      - Always echo the latest 'Mcp-Session-Id' seen (header or endpoint query)
      - Responses may arrive on stream OR embedded as an SSE block in POST body
    """
    def __init__(self, sse_url: str, timeout: float = 60.0):
        self.base_url = re.sub(r"#.*$", "", sse_url.rstrip("/"))
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id: Optional[str] = None
        self.post_url: Optional[str] = None
        self._rpc_id = 0

        self._stop = threading.Event()
        self._resp_map: Dict[str, queue.Queue] = {}
        self._stream_thread: Optional[threading.Thread] = None

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post_target(self) -> str:
        return self.post_url or self.base_url

    def _next_id(self) -> str:
        self._rpc_id += 1
        return str(self._rpc_id)

    def _parse_post_body_as_jsonrpc(self, text: str) -> Optional[dict]:
        if not text:
            return None
        s = text.lstrip()
        if s.startswith("{"):
            try:
                return json.loads(s)
            except Exception:
                pass
        # Allow SSE-style POST body
        data_lines = []
        for line in s.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            try:
                return json.loads("\n".join(data_lines))
            except Exception:
                return None
        return None

    def _start_stream(self):
        def reader():
            with self.session.get(self.base_url, stream=True, timeout=None,
                                  headers={"Accept": "text/event-stream"}) as r:
                sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
                if sid:
                    self.session_id = sid

                buf = ""
                for chunk in r.iter_content(chunk_size=2048):
                    if self._stop.is_set():
                        break
                    if not chunk:
                        continue
                    buf += chunk.decode("utf-8", errors="replace")
                    while "\n\n" in buf:
                        event_raw, buf = buf.split("\n\n", 1)
                        event_name = "message"
                        data_lines = []
                        for line in event_raw.splitlines():
                            if line.startswith("event:"):
                                event_name = line[6:].strip() or event_name
                            elif line.startswith("data:"):
                                data_lines.append(line[5:].lstrip())
                        if not data_lines:
                            continue
                        data_str = "\n".join(data_lines)

                        # Legacy 'endpoint' → discover POST target + session id
                        if event_name == "endpoint":
                            ep = None
                            try:
                                obj = json.loads(data_str)
                                if isinstance(obj, dict) and "endpoint" in obj:
                                    ep = obj["endpoint"]
                            except Exception:
                                pass
                            if ep is None:
                                ep = data_str.strip()
                            try:
                                self.post_url = urljoin(self.base_url + "/", ep)
                            except Exception:
                                self.post_url = self.base_url
                            try:
                                q = parse_qs(urlparse(self.post_url).query)
                                sid = q.get("session_id", [None])[0]
                                if sid:
                                    self.session_id = sid
                            except Exception:
                                pass
                            continue

                        # Normal JSON-RPC envelope
                        try:
                            payload = json.loads(data_str)
                        except Exception:
                            continue

                        # Route responses by id
                        if isinstance(payload, dict) and "id" in payload:
                            req_id = str(payload["id"])
                            q = self._resp_map.get(req_id)
                            if q:
                                q.put(payload)

        self._stream_thread = threading.Thread(target=reader, daemon=True)
        self._stream_thread.start()

    def initialize(self) -> Dict[str, Any]:
        self._start_stream()
        # Give legacy servers a moment to emit 'endpoint'
        t_end = time.time() + 0.5
        while self.post_url is None and time.time() < t_end:
            time.sleep(0.01)

        req_id = self._next_id()
        payload = {"jsonrpc": "2.0", "id": req_id, "method": "initialize", "params": INIT_PARAMS}
        self._resp_map[req_id] = queue.Queue()

        r = self.session.post(self._post_target(), json=payload, timeout=self.timeout, headers=self._headers())
        sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} during initialize POST: {r.text}")

        env = self._parse_post_body_as_jsonrpc(r.text)
        if not env:
            try:
                env = self._resp_map[req_id].get(timeout=self.timeout)
            except queue.Empty:
                raise TimeoutError("Timed out waiting for initialize response on SSE stream")
        self._resp_map.pop(req_id, None)

        if "error" in env:
            raise RuntimeError(f"MCP initialize error {env['error']}")

        # Required notification
        note = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        nr = self.session.post(self._post_target(), json=note, timeout=self.timeout, headers=self._headers())
        sid = nr.headers.get("Mcp-Session-Id") or nr.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        if nr.status_code >= 400:
            raise RuntimeError(f"HTTP {nr.status_code} posting 'initialized': {nr.text}")

        return env.get("result", env)

    def send_request(self, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        req_id = self._next_id()
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._resp_map[req_id] = queue.Queue()

        r = self.session.post(self._post_target(), json=payload, timeout=self.timeout, headers=self._headers())
        sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} posting '{method}': {r.text}")

        env = self._parse_post_body_as_jsonrpc(r.text)
        if not env:
            try:
                env = self._resp_map[req_id].get(timeout=self.timeout)
            except queue.Empty:
                raise TimeoutError(f"Timed out waiting for response to '{method}' on SSE stream")
        self._resp_map.pop(req_id, None)

        if "error" in env:
            raise RuntimeError(f"MCP error {env['error']}")
        return env.get("result", env)

    def send_notification(self, method: str, params: Optional[Dict[str, Any]]) -> None:
        note = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            note["params"] = params
        r = self.session.post(self._post_target(), json=note, timeout=self.timeout, headers=self._headers())
        sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} posting notification '{method}': {r.text}")

    def close(self) -> None:
        self._stop.set()
        if self._stream_thread and self._stream_thread.is_alive():
            try:
                self._stream_thread.join(timeout=1.0)
            except Exception:
                pass
        try:
            self.session.close()
        except Exception:
            pass

# =========================================================
#                    TRANSPORT CHOICE
# =========================================================

def probe_transport(url: str) -> str:
    cleaned = re.sub(r"#.*$", "", url)
    if cleaned.endswith("/sse"):
        return "sse"
    try:
        r = requests.get(cleaned, headers={"Accept": "text/event-stream"}, timeout=2)
        ctype = r.headers.get("Content-Type", "")
        text = (r.text or "").lower()
        if r.status_code == 200 and ctype.startswith("text/event-stream"):
            return "sse"
        if "text/event-stream" in text or "accept must contain" in text or "event: endpoint" in text:
            return "sse"
    except Exception:
        pass
    return "http"

def build_transport(url: str) -> MCPTransport:
    kind = probe_transport(url)
    return SSETransport(url) if kind == "sse" else HTTPTransport(url)

# =========================================================
#               MCP HELPERS (transport-agnostic)
# =========================================================

def mcp_initialize(transport: MCPTransport) -> Dict[str, Any]:
    return transport.initialize()

def mcp_call(transport: MCPTransport, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return transport.send_request(method, params)

def mcp_notify(transport: MCPTransport, method: str, params: Optional[Dict[str, Any]]) -> None:
    return transport.send_notification(method, params)

def try_list(transport: MCPTransport, method: str) -> Optional[List[Dict[str, Any]]]:
    """
    Try */list with variants:
      1) no params
      2) params: null
      3) params: {}
    Return a list or None.
    """
    variants = [None, None, {}]
    for params in variants:
        try:
            res = mcp_call(transport, method, params)
            if isinstance(res, dict):
                for k in ("tools", "prompts", "resources", "items", "result"):
                    if k in res and isinstance(res[k], list):
                        return res[k]
                if "result" in res and isinstance(res["result"], dict) and "items" in res["result"]:
                    if isinstance(res["result"]["items"], list):
                        return res["result"]["items"]
            elif isinstance(res, list):
                return res
        except RuntimeError as e:
            if "-32602" in str(e):
                continue
            else:
                break
    return None

# Optional helpers for quirky servers that document tool names in 'instructions'
TOOL_NAME_RE = re.compile(r"`([a-zA-Z0-9_]{2,64})`")
def tools_from_instructions(instructions: str) -> List[Dict[str, Any]]:
    if not instructions:
        return []
    names = []
    for m in TOOL_NAME_RE.finditer(instructions):
        n = m.group(1)
        if any(ch.isalpha() for ch in n):
            names.append(n)
    uniq = []
    seen = set()
    for n in names:
        if n not in seen:
            uniq.append(n); seen.add(n)
    return [{"name": n, "description": f"Discovered from instructions: `{n}`", "inputSchema": {"type": "object"}} for n in uniq]

def normalize_tool_args(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(args or {})
    # Known aliases for some community servers (e.g., AWS docs)
    if name == "search_documentation":
        if "search_phrase" not in a and "query" in a:
            a["search_phrase"] = a.pop("query")
        if "limit" not in a and "max_results" in a:
            a["limit"] = a.pop("max_results")
        if "limit" not in a:
            a["limit"] = 5
    elif name in ("read_documentation", "recommend"):
        if "url" not in a:
            for k in ("link", "href", "page_url"):
                if k in a:
                    a["url"] = a.pop(k); break
    return a

# =========================================================
#         OPENAI ROUTER (multi-step tool orchestration)
# =========================================================

def mcp_tool_to_openai_tool(t: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t.get("description", "")[:512],
            "parameters": t.get("inputSchema", {}) or {"type": "object", "properties": {}},
        },
    }

ALLOWLIST = None  # e.g., {"fetch", "list_directory"}

def allowed_tool(name: str) -> bool:
    return (ALLOWLIST is None) or (name in ALLOWLIST)

def choose_and_run_tool(user_text: str, transport: MCPTransport) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("Set OPENAI_API_KEY in your environment.")
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Initialize + gather capabilities & instructions
    init_res = mcp_initialize(transport)
    instructions = (init_res.get("instructions") or "") if isinstance(init_res, dict) else ""

    # Discover tools (robustly). If list fails, scrape from instructions.
    tools_list = try_list(transport, "tools/list") or []
    if not tools_list and instructions:
        tools_list = tools_from_instructions(instructions)

    tools_map = {t["name"]: t for t in tools_list if isinstance(t, dict) and "name" in t}
    openai_tools = [mcp_tool_to_openai_tool(t) for t in tools_map.values()]

    # If no tools discovered, try prompts surface as a fallback
    prompts_list = None
    if not openai_tools:
        prompts_list = try_list(transport, "prompts/list")

    # Build the initial message set (optionally hint if we see known tool names)
    sys_hint = None
    if any(n in tools_map for n in ("list_directory", "read_file", "read_text")):
        sys_hint = ("You can use filesystem tools to list and read files. "
                    "Plan steps and use multiple tools until you can answer.")
    elif any(n in tools_map for n in ("search_documentation", "read_documentation")):
        sys_hint = ("Prefer 'search_documentation' then 'read_documentation' to cite sources. "
                    "Use multiple calls if needed and stop when sufficient information is gathered.")

    messages = []
    if sys_hint:
        messages.append({"role": "system", "content": sys_hint})
    messages.append({"role": "user", "content": user_text})

    # If no tools but prompts exist, do a simple prompt call and return
    if not openai_tools and prompts_list:
        # choose the first prompt heuristically
        by_name = {p.get("name"): p for p in prompts_list if isinstance(p, dict) and "name" in p}
        chosen = None
        for name, p in by_name.items():
            txt = (name + " " + p.get("description", "")).lower()
            if any(k in txt for k in ("search", "doc", "aws", "arxiv", "query", "time", "files")):
                chosen = name; break
        if not chosen and by_name:
            chosen = next(iter(by_name))
        if not chosen:
            return "This server exposes neither usable tools nor prompts."
        try:
            _ = mcp_call(transport, "prompts/get", {"name": chosen})
            out = mcp_call(transport, "prompts/call", {"name": chosen, "arguments": {"input": user_text}})
            return json.dumps(out, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Prompt flow failed: {e}"

    # -------- Multi-step tool loop (the key fix) --------
    # Keep asking the model until it returns an assistant message with no tool_calls.
    max_loops = 12  # prevent infinite loops
    while max_loops > 0:
        max_loops -= 1
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else "none",
        )
        msg = resp.choices[0].message
        messages.append({"role": "assistant",
                         "content": msg.content,
                         "tool_calls": msg.tool_calls} if msg.tool_calls else
                        {"role": "assistant", "content": msg.content})

        # If the model answered directly, we’re done
        if not msg.tool_calls:
            return msg.content or "(no answer)"

        # Execute each tool call, append tool results, then loop again
        for call in msg.tool_calls:
            name = call.function.name
            if not allowed_tool(name):
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps({"error": f"Blocked tool '{name}' by policy."})
                })
                continue

            args_json = call.function.arguments or "{}"
            try:
                args = json.loads(args_json)
            except Exception as e:
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps({"error": f"Invalid JSON args for '{name}': {e}"})
                })
                continue

            # Schema validate when available
            schema = tools_map.get(name, {}).get("inputSchema", {"type": "object"})
            try:
                validate(instance=args, schema=schema)
            except ValidationError:
                # Try normalization (handles common alias mismatches)
                args = normalize_tool_args(name, args)
                try:
                    validate(instance=args, schema=schema)
                except ValidationError as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps({"error": f"Tool arg validation failed for '{name}': {e.message}"})
                    })
                    continue

            # Call MCP tool
            try:
                result = mcp_call(transport, "tools/call", {"name": name, "arguments": args})
            except Exception as e:
                result = {"error": f"MCP tool '{name}' call failed: {e}"}

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "Stopped after too many tool-call iterations (safety cap)."

# =========================================================
#                       RUNNER
# =========================================================

def run_with_autofix(url: str, ask: str) -> str:
    transport = build_transport(url)
    try:
        return choose_and_run_tool(ask, transport)
    except RuntimeError as e:
        msg = str(e)
        sse_hint = ("SSE_BODY_ON_HTTP" in msg) or ("text/event-stream" in msg) or ("event:" in msg)
        if isinstance(transport, HTTPTransport) and sse_hint:
            try:
                transport.close()
            except Exception:
                pass
            transport = SSETransport(url)
            return choose_and_run_tool(ask, transport)
        raise
    finally:
        try:
            transport.close()
        except Exception:
            pass

# =========================================================
#                           CLI
# =========================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Self-correcting MCP client (HTTP + SSE + multi-step tools).")
    parser.add_argument("--url", required=True, help="MCP endpoint (HTTP or .../sse[#label])")
    parser.add_argument("--ask", required=True, help="User prompt to route to MCP tool/prompt.")
    parser.add_argument("--allow", nargs="*", help="Optional allow-list of tool names.")
    args = parser.parse_args()

    if args.allow:
        ALLOWLIST = set(args.allow)

    answer = run_with_autofix(args.url, args.ask)
    print("\n=== ANSWER ===\n")
    print(answer)
