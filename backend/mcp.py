import re
import json
import time
import queue
import threading
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, quote

import requests

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
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id: Optional[str] = None
        self._rpc_id = 0

    def _next_id(self) -> str:
        self._rpc_id += 1
        return str(self._rpc_id)

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
            # Special handling for MCP protocol issues
            if r.status_code == 400 and "unsupported" in body.lower():
                print(f"Warning: Server doesn't support standard MCP protocol (HTTP {r.status_code}): {body}")
                # Return a minimal response to continue
                return {"serverInfo": {"name": "Unknown Server", "version": "1.0.0"}}
            raise RuntimeError(f"HTTP {r.status_code} from {self.base_url}: {body}")
        if body.lstrip().startswith("event:"):
            raise RuntimeError(
                "SSE_BODY_ON_HTTP: POST returned an SSE block; use SSE transport."
            )
        # Streamable HTTP (/mcp) may return SSE-style body: "data: {...}\n\n"
        if body.lstrip().startswith("data:"):
            data_lines = [line[5:].lstrip() for line in body.splitlines() if line.startswith("data:")]
            if data_lines:
                try:
                    return json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    pass
        try:
            return r.json()
        except Exception:
            raise RuntimeError(f"Invalid JSON response from {self.base_url}: {body[:300]}")

    def initialize(self) -> Dict[str, Any]:
        req = {"jsonrpc": "2.0", "id": self._next_id(), "method": "initialize", "params": INIT_PARAMS}
        r, body = self._post_raw(req)
        res = self._parse_json(r, body)
        # Best-effort notification - don't fail if server doesn't support it
        try:
            print(f"🔧 Sending 'initialized' notification to {self.base_url}")
            init_response = self.session.post(self.base_url, json={"jsonrpc": "2.0", "method": "initialized", "params": {}},
                              timeout=self.timeout, headers=self._headers())
            print(f"🔧 'initialized' response: {init_response.status_code}")
            if init_response.status_code >= 400:
                print(f"Warning: Server doesn't support 'initialized' notification (HTTP {init_response.status_code}): {init_response.text}")
        except Exception as e:
            # Server doesn't support initialized notification, continue anyway
            print(f"Warning: Server doesn't support 'initialized' notification: {e}")
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
    def __init__(self, sse_url: str, timeout: float = 60.0):
        self.base_url = re.sub(r"#.*$", "", sse_url.rstrip("/"))
        self._sse_fragment = (re.search(r"#(.+)$", sse_url) or [None, None])[1]
        # Pass fragment to proxy so it can route to the correct stdio server (e.g. ToolHive SSE proxy).
        # Use query param (fragment is never sent over HTTP; proxy may expect ?server=name).
        if self._sse_fragment:
            self.base_url = self.base_url + ("&" if "?" in self.base_url else "?") + "server=" + quote(self._sse_fragment, safe="")
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id: Optional[str] = None
        self.post_url: Optional[str] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._resp_map: Dict[str, queue.Queue] = {}
        self._rpc_id = 0
        self._stream_stop = threading.Event()
        self._stream_error: Optional[Exception] = None  # reader thread connection error

    def _next_id(self) -> str:
        self._rpc_id += 1
        return str(self._rpc_id)

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        if getattr(self, "_sse_fragment", None):
            h["X-MCP-Server"] = self._sse_fragment
        return h

    def _post_target(self) -> str:
        return self.post_url or self.base_url

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
            self._stream_error = None
            try:
                get_headers = {"Accept": "text/event-stream"}
                if getattr(self, "_sse_fragment", None):
                    get_headers["X-MCP-Server"] = self._sse_fragment
                r = self.session.get(self.base_url, stream=True, timeout=None,
                                    headers=get_headers)
            except Exception as e:
                self._stream_error = e
                return
            with r:
                sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
                if sid:
                    self.session_id = sid

                buf = ""
                for chunk in r.iter_content(chunk_size=2048):
                    if self._stream_stop.is_set():
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
        # Give reader thread a moment to connect or set _stream_error
        time.sleep(0.15)
        if self._stream_error is not None:
            err = self._stream_error
            self._stream_error = None
            msg = str(err)
            if "Connection refused" in msg or "61" in msg:
                raise RuntimeError(
                    f"Cannot connect to MCP proxy at {self.base_url} (connection refused). "
                    "Is the ToolHive proxy running and listening on this address?"
                ) from err
            raise RuntimeError(f"MCP SSE connection failed: {msg}") from err
        # Give legacy servers a moment to emit 'endpoint'
        t_end = time.time() + 0.5
        while self.post_url is None and time.time() < t_end:
            time.sleep(0.01)

        req_id = self._next_id()
        payload = {"jsonrpc": "2.0", "id": req_id, "method": "initialize", "params": INIT_PARAMS}
        self._resp_map[req_id] = queue.Queue()

        print(f"🔧 SSE Sending 'initialize' request to {self._post_target()}")
        r = self.session.post(self._post_target(), json=payload, timeout=self.timeout, headers=self._headers())
        print(f"🔧 SSE 'initialize' response: {r.status_code}")
        sid = r.headers.get("Mcp-Session-Id") or r.headers.get("MCP-Session-Id")
        if sid:
            self.session_id = sid
        if r.status_code >= 400:
            print(f"Warning: Server returned HTTP {r.status_code} for 'initialize' request: {r.text}")
            # Try to continue anyway - some servers might still work
            if r.status_code == 400 and "unsupported" in r.text.lower():
                print("🔧 Server doesn't support standard MCP protocol, trying to continue...")
                # Return a minimal response to continue
                return {"serverInfo": {"name": "Unknown Server", "version": "1.0.0"}}
            raise RuntimeError(f"HTTP {r.status_code} posting 'initialize': {r.text}")

        env = self._parse_post_body_as_jsonrpc(r.text)
        if not env:
            try:
                env = self._resp_map[req_id].get(timeout=self.timeout)
            except queue.Empty:
                raise TimeoutError(f"Timed out waiting for response to 'initialize' on SSE stream")
        self._resp_map.pop(req_id, None)

        if "error" in env:
            raise RuntimeError(f"MCP error {env['error']}")

        # Required notification - but handle gracefully if server doesn't support it
        try:
            print(f"🔧 SSE Sending 'initialized' notification to {self._post_target()}")
            note = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
            nr = self.session.post(self._post_target(), json=note, timeout=self.timeout, headers=self._headers())
            print(f"🔧 SSE 'initialized' response: {nr.status_code}")
            sid = nr.headers.get("Mcp-Session-Id") or nr.headers.get("MCP-Session-Id")
            if sid:
                self.session_id = sid
            if nr.status_code >= 400:
                print(f"Warning: Server doesn't support 'initialized' notification (HTTP {nr.status_code}): {nr.text}")
        except Exception as e:
            # Server doesn't support initialized notification, continue anyway
            print(f"Warning: Server doesn't support 'initialized' notification: {e}")

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
        from_body = env is not None
        if not env:
            try:
                env = self._resp_map[req_id].get(timeout=self.timeout)
            except queue.Empty:
                raise TimeoutError(f"Timed out waiting for response to '{method}' on SSE stream")
        self._resp_map.pop(req_id, None)

        if "error" in env:
            raise RuntimeError(f"MCP error {env['error']}")
        res = env.get("result", env)
        return res

    def send_notification(self, method: str, params: Optional[Dict[str, Any]]) -> None:
        note = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            note["params"] = params
        r = self.session.post(self._post_target(), json=note, timeout=self.timeout, headers=self._headers())

    def close(self) -> None:
        self._stream_stop.set()
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
        try:
            self.session.close()
        except Exception:
            pass

# =========================================================
#                        HELPERS
# =========================================================

def probe_transport(url: str) -> str:
    """Probe URL to determine transport type"""
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
    """Build appropriate transport for URL"""
    kind = probe_transport(url)
    return SSETransport(url) if kind == "sse" else HTTPTransport(url)

# =========================================================
#               MCP HELPERS (transport-agnostic)
# =========================================================

def mcp_initialize(transport: MCPTransport) -> Dict[str, Any]:
    """Initialize MCP connection"""
    return transport.initialize()

def mcp_call(transport: MCPTransport, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Make MCP call"""
    return transport.send_request(method, params)

def mcp_notify(transport: MCPTransport, method: str, params: Optional[Dict[str, Any]]) -> None:
    """Send MCP notification"""
    return transport.send_notification(method, params)

def try_list(transport: MCPTransport, method: str) -> Dict[str, Any]:
    """
    Some servers validate empty params differently. Try:
    1) no params key
    2) params: null
    3) params: {}
    """
    for params in [None, None, {}]:
        try:
            return mcp_call(transport, method, params)
        except Exception as e:
            if "params" in str(e).lower():
                continue
            raise
    raise RuntimeError(f"Failed to call {method} with any params variant")