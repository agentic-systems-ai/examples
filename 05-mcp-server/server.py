"""A minimal, stateless MCP server (protocol revision 2026-07-28), standard library only.

Companion code for https://www.agenticsystems.ai/blog/mcp-explained/
Usage:  python server.py --port 8001      (start as many instances as you like)

What it shows:
- No handshake and no sessions: every request carries its own protocol version and capabilities in `_meta`.
- HTTP headers (MCP-Protocol-Version, Mcp-Method, Mcp-Name) mirror the body, so proxies can route without parsing it;
  the server rejects requests where they disagree.
- State that must span requests (a shopping list) lives behind an explicit handle in a shared store,
  so ANY instance can serve ANY request. Here the "shared store" is a JSON file; in production, a database.

This is a teaching server: it implements the core request/response path, not the whole specification.
"""

import argparse
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "2026-07-28"
SERVER_INFO = {"name": "shopping-lists", "version": "0.1.0"}
STORE = Path(__file__).parent / "store.json"  # shared by every instance
_lock = threading.Lock()

TOOLS = [
    {"name": "create_list",
     "description": "Create an empty shopping list and return its list_id. Lists expire after 24 hours. "
                    "Pass the list_id to add_item and get_list.",
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string", "description": "e.g. 'Weekend trip'"}},
                     "required": ["title"], "additionalProperties": False}},
    {"name": "add_item",
     "description": "Add one item to an existing list.",
     "inputSchema": {"type": "object", "properties": {
         "list_id": {"type": "string", "description": "Handle returned by create_list, e.g. 'lst_3f9a1c'"},
         "item": {"type": "string"}}, "required": ["list_id", "item"], "additionalProperties": False}},
    {"name": "get_list",
     "description": "Return a list's title and items.",
     "inputSchema": {"type": "object", "properties": {"list_id": {"type": "string"}},
                     "required": ["list_id"], "additionalProperties": False}},
]


# --------------------------------------------------------------------------- tool implementations

def _load() -> dict:
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def _save(data: dict) -> None:
    STORE.write_text(json.dumps(data, indent=1))


def call_tool(name: str, args: dict) -> dict:
    """Run a tool. Problems the model can fix become tool *execution* errors (isError: true)."""
    with _lock:
        lists = _load()
        if name == "create_list":
            list_id = "lst_" + secrets.token_hex(3)
            lists[list_id] = {"title": args["title"], "items": []}
            _save(lists)
            return _text(f"Created list {list_id} ({args['title']!r})", {"list_id": list_id})
        if args.get("list_id") not in lists:
            return _text(f"Unknown list_id {args.get('list_id')!r}. It may have expired; create a new list "
                         "with create_list.", is_error=True)
        lst = lists[args["list_id"]]
        if name == "add_item":
            lst["items"].append(args["item"])
            _save(lists)
            return _text(f"Added {args['item']!r} ({len(lst['items'])} items)")
        return _text(f"{lst['title']}: " + (", ".join(lst["items"]) or "(empty)"), lst)


def _text(text: str, structured=None, is_error: bool = False) -> dict:
    result = {"resultType": "complete", "content": [{"type": "text", "text": text}], "isError": is_error}
    if structured is not None:
        result["structuredContent"] = structured
    return result


# --------------------------------------------------------------------------- JSON-RPC over Streamable HTTP

class RpcError(Exception):
    def __init__(self, http_status: int, code: int, message: str, data=None):
        super().__init__(message)
        self.http_status, self.code, self.message, self.data = http_status, code, message, data


def handle(body: dict, headers) -> dict:
    """Validate one request and return its result. Every request stands alone: no session state is read."""
    params = body.get("params") or {}
    meta = params.get("_meta") or {}
    version = meta.get("io.modelcontextprotocol/protocolVersion")

    if version is None or "io.modelcontextprotocol/clientCapabilities" not in meta:
        raise RpcError(400, -32602, "Missing required _meta fields (protocolVersion, clientCapabilities)")
    if headers.get("MCP-Protocol-Version") != version:
        raise RpcError(400, -32020, "Header mismatch: MCP-Protocol-Version does not match _meta protocolVersion")
    if version != VERSION:
        raise RpcError(400, -32022, "Unsupported protocol version", {"supported": [VERSION], "requested": version})
    if headers.get("Mcp-Method") != body.get("method"):
        raise RpcError(400, -32020, "Header mismatch: Mcp-Method does not match body method")

    method = body["method"]
    if method == "server/discover":
        return {"resultType": "complete", "supportedVersions": [VERSION], "capabilities": {"tools": {}},
                "instructions": "Shopping lists. Create a list, then add items using its list_id.",
                "ttlMs": 3_600_000, "cacheScope": "public"}
    if method == "tools/list":
        # Same for every caller, so any client or gateway may cache it for 5 minutes.
        return {"resultType": "complete", "tools": TOOLS, "ttlMs": 300_000, "cacheScope": "public"}
    if method == "tools/call":
        if headers.get("Mcp-Name") != params.get("name"):
            raise RpcError(400, -32020, "Header mismatch: Mcp-Name does not match params.name")
        if params.get("name") not in {t["name"] for t in TOOLS}:
            raise RpcError(400, -32602, f"Unknown tool: {params.get('name')}")
        return call_tool(params["name"], params.get("arguments") or {})
    raise RpcError(404, -32601, f"Method not found: {method}")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and not origin.startswith(("http://localhost", "http://127.0.0.1")):
            return self._send(403, {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Forbidden origin"}})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            result = handle(body, self.headers)
            result.setdefault("_meta", {})["io.modelcontextprotocol/serverInfo"] = SERVER_INFO
            self._send(200, {"jsonrpc": "2.0", "id": body.get("id"), "result": result})
        except RpcError as e:
            error = {"code": e.code, "message": e.message, **({"data": e.data} if e.data else {})}
            self._send(e.http_status, {"jsonrpc": "2.0", "id": body.get("id"), "error": error})

    def do_GET(self):     # the 2025 standalone SSE stream no longer exists
        self._send(405, None)

    do_DELETE = do_GET    # ...and neither do sessions to delete

    def _send(self, status: int, payload):
        data = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"[:{self.server.server_port}] {self.headers.get('Mcp-Method')} {self.headers.get('Mcp-Name') or ''}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    port = parser.parse_args().port
    print(f"MCP server on http://127.0.0.1:{port}/mcp")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()  # bind to localhost only
