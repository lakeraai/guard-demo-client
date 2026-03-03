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

# Safer default; servers may reply with their version.
INIT_PARAMS = {
    "protocolVersion": "2025-03-26",
    "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
    "clientInfo": {"name": "OpenAI-MCP-Client", "version": "0.5.0"},
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
    - Some servers require Accept: 'application/json, text/event-stream' on POST
    """
    def __init__(self, base_url: str, timeout: float = 30.0):
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
            raise RuntimeError(
                "SSE_BODY_ON_HTTP: POST returned an SSE block; use SSE transport."
            )
        try:
            return r.json()
        except Exception:
            raise RuntimeError(f"Invalid JSON response from {self.base_url}: {body[:300]}")

    def initialize(self) -> Dict[str, Any]:
        req = {"jsonrpc": "2.0", "id": self._next_id(), "method": "initialize", "params": INIT_PARAMS}
        r, body = self._post_raw(req)
        res = self._parse_json(r, body)
        # Best-effort notification
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
    Streamable HTTP/SSE transport:
      - GET <base_url> with Accept: text/event-stream for events
      - Legacy negotiation: read 'event: endpoint' → POST to that URL (not /sse)
      - POST with Accept: application/json, text/event-stream
      - Echo 'Mcp-Session-Id' on every POST; read it from endpoint query or response headers
      - Responses may arrive on SSE OR embedded as an SSE block in POST body
    """
    def __init__(self, sse_url: str, timeout: float = 30.0):
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
                for chunk in r.iter_content(chunk_size=1024):
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

                        # Legacy endpoint negotiation
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
                            # Derive session id from endpoint query if present
                            try:
                                q = parse_qs(urlparse(self.post_url).query)
                                sid = q.get("session_id", [None])[0]
                                if sid:
                                    self.session_id = sid
                            except Exception:
                                pass
                            continue

                        # Normal JSON-RPC payloads
                        try:
                            payload = json.loads(data_str)
                        except Exception:
                            continue

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

def try_list(transport: MCPTransport, method: str) -> Dict[str, Any]:
    """
    Some servers validate empty params differently. Try:
    1) no params key
    2) params: null
    3) params: {}
    """
    for variant in (None, None, {}):  # first call with params=None (no key), second with null (by passing None again but flag), third {}
        try:
            if variant is None:
                # Distinguish the two Nones: first as "no key", second as explicit null
                # We send explicit null by passing {"__SEND_NULL__": True} sentinel handled below.
                # Simpler: try two sequential calls; first no key, second explicit null:
                res = mcp_call(transport, method, None)
            else:
                res = mcp_call(transport, method, variant)
            # If call returns without raising, it's a result dict.
            return res
        except RuntimeError as e:
            msg = str(e)
            if "code" in msg and "-32602" in msg:
                # try next variant
                if variant is None:
                    # do explicit null
                    try:
                        res = transport.send_request(method, None)  # already did; simulate explicit null:
                        # If server can't distinguish, fall through to next
                    except Exception:
                        pass
                continue
            raise
    # Final explicit null try (some transports don't accept above logic)
    try:
        res = mcp_call(transport, method, None)  # if server treats missing params == null
        return res
    except Exception as e:
        raise

# =========================================================
#         OPENAI ROUTER (tool selection + execution)
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

ALLOWLIST = None  # e.g., {"fetch", "arxiv_search"}

def allowed_tool(name: str) -> bool:
    return (ALLOWLIST is None) or (name in ALLOWLIST)

def choose_and_run_tool(user_text: str, transport: MCPTransport) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("Set OPENAI_API_KEY in your environment.")
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Init & discover capabilities
    init_res = mcp_initialize(transport)
    caps = init_res.get("capabilities", {}) if isinstance(init_res, dict) else {}
    have_tools = "tools" in caps
    have_prompts = "prompts" in caps
    have_resources = "resources" in caps

    tools_list = []
    if have_tools:
        # Try list variants robustly
        try:
            tl = try_list(transport, "tools/list")
            tools_list = tl.get("tools", tl.get("result", tl)) if isinstance(tl, dict) else tl
            if not isinstance(tools_list, list):
                tools_list = []
        except Exception:
            tools_list = []

    # If no tools found but prompts exist, prefer prompts surface
    use_prompts = (not tools_list) and have_prompts

    if use_prompts:
        # Prompt-based flow: list prompts, pick one, call it with the question
        plist = {}
        try:
            pr = try_list(transport, "prompts/list")
            arr = pr.get("prompts", pr.get("result", pr)) if isinstance(pr, dict) else pr
            if isinstance(arr, list):
                plist = {p.get("name"): p for p in arr if isinstance(p, dict) and "name" in p}
        except Exception:
            plist = {}

        # Heuristic: choose first prompt whose name/desc mentions 'search' or 'arxiv' or 'doc'
        chosen = None
        for name, p in plist.items():
            text = (name + " " + p.get("description", "")).lower()
            if any(k in text for k in ("search", "arxiv", "doc", "aws", "time", "query")):
                chosen = name
                break
        if not chosen and plist:
            chosen = next(iter(plist.keys()))

        if not chosen:
            return "This server exposes no tools and no usable prompts/resources; cannot route the question."

        # Call the prompt (standard MCP: prompts/get -> prompts/call)
        try:
            g = mcp_call(transport, "prompts/get", {"name": chosen})
        except Exception as e:
            return f"Failed to get prompt '{chosen}': {e}"

        # Many servers accept free-form args; pass the user's query as 'input' or 'query'
        args = {"input": user_text}
        try:
            out = mcp_call(transport, "prompts/call", {"name": chosen, "arguments": args})
            return json.dumps(out, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Failed to call prompt '{chosen}': {e}"

    # Otherwise, we have tools (or at least tools/list succeeded)
    tools_map = {t["name"]: t for t in tools_list if isinstance(t, dict) and "name" in t}
    openai_tools = [mcp_tool_to_openai_tool(t) for t in tools_map.values()]

    # If the server didn't list tools but declared the capability, don't block; ask the model anyway
    if not openai_tools and have_tools:
        # fall back to asking model without tools
        first = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": user_text}],
        )
        return first.choices[0].message.content or "(no answer)"

    # Ask the model to pick a tool (or answer directly)
    first = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": user_text}],
        tools=openai_tools,
        tool_choice="auto",
    )

    first_msg = first.choices[0].message
    t_calls = first_msg.tool_calls or []
    if not t_calls:
        return first_msg.content or "(no tool use)"

    # Execute only the first tool (extend to multi-step if needed)
    call = t_calls[0]
    name = call.function.name
    if not allowed_tool(name):
        return f"Blocked tool '{name}' by policy."
    args_json = call.function.arguments or "{}"
    try:
        args = json.loads(args_json)
    except Exception as e:
        return f"Model produced invalid JSON for tool '{name}': {e}"

    schema = tools_map.get(name, {}).get("inputSchema", {"type": "object"})
    try:
        validate(instance=args, schema=schema)
    except ValidationError as e:
        return f"Tool argument validation failed for '{name}': {e.message}"

    try:
        tool_result = mcp_call(transport, "tools/call", {"name": name, "arguments": args})
    except Exception as e:
        return f"MCP tool '{name}' call failed: {e}"

    # Formatting turn (must include assistant message w/ tool_calls, then tool result)
    messages = [
        {"role": "system", "content": "Format the following tool result clearly for the user."},
        {"role": "user", "content": user_text},
        {
            "role": "assistant",
            "content": first_msg.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": name, "arguments": args_json},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps({"name": name, "result": tool_result}, ensure_ascii=False),
        },
    ]
    final = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
    return final.choices[0].message.content or json.dumps(tool_result, indent=2)

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

    parser = argparse.ArgumentParser(description="Self-correcting MCP client (HTTP + SSE + ToolHive legacy).")
    parser.add_argument("--url", required=True, help="MCP endpoint (HTTP or .../sse[#label])")
    parser.add_argument("--ask", required=True, help="User prompt to route to MCP tool/prompt.")
    parser.add_argument("--allow", nargs="*", help="Optional allow-list of tool names.")
    args = parser.parse_args()

    if args.allow:
        ALLOWLIST = set(args.allow)

    answer = run_with_autofix(args.url, args.ask)
    print("\n=== ANSWER ===\n")
    print(answer)