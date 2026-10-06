"""A from-scratch MCP client that sends each request to a different server instance.

Usage:  python server.py --port 8001 &  python server.py --port 8002 &
        python client.py

If the protocol were stateful, a list created on one instance would be invisible to the other.
Because it is stateless (and state lives behind an explicit handle in a shared store), it just works.
"""

import itertools
import json
import time
import urllib.error
import urllib.request

VERSION = "2026-07-28"
INSTANCES = ["http://127.0.0.1:8001/mcp", "http://127.0.0.1:8002/mcp"]


class McpClient:
    def __init__(self, urls: list[str]):
        self._next_url = itertools.cycle(urls)  # a toy round-robin load balancer
        self._ids = itertools.count(1)
        self._cache: dict[str, tuple[float, dict]] = {}  # cache key -> (expires_at, result)

    def request(self, method: str, params: dict | None = None, version: str = VERSION) -> dict:
        # The spec keys a cached result on the method plus the params that affect it; we add the version too.
        key = json.dumps([method, version, params or {}], sort_keys=True)
        if key in self._cache and time.monotonic() < self._cache[key][0]:
            print(f"  {method:<16} served from client cache (ttlMs still fresh)")
            return self._cache[key][1]

        params = dict(params or {})
        params["_meta"] = {  # everything the server needs, on every request
            "io.modelcontextprotocol/protocolVersion": version,
            "io.modelcontextprotocol/clientInfo": {"name": "agentic-systems-demo", "version": "0.1.0"},
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": version, "Mcp-Method": method}
        if "name" in params:
            headers["Mcp-Name"] = params["name"]

        url = next(self._next_url)
        body = json.dumps({"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, body, headers)) as resp:
                reply = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            reply = json.loads(e.read())
        print(f"  {method:<16} -> {url.split('/')[2]}")

        if "error" in reply:
            raise RuntimeError(f"{reply['error']['code']}: {reply['error']['message']} {reply['error'].get('data', '')}")
        result = reply["result"]
        if result.get("ttlMs"):
            self._cache[key] = (time.monotonic() + result["ttlMs"] / 1000, result)
        return result

    def call(self, name: str, **arguments) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments})


if __name__ == "__main__":
    mcp = McpClient(INSTANCES)

    print("1. Discover and list tools (no handshake first)")
    info = mcp.request("server/discover")
    print("     server supports", info["supportedVersions"])
    tools = mcp.request("tools/list")
    print("     tools:", [t["name"] for t in tools["tools"]])
    mcp.request("tools/list")  # second time: cached

    print("2. A multi-step task, with each step on whichever instance is next")
    list_id = mcp.call("create_list", title="Weekend trip")["structuredContent"]["list_id"]
    for item in ["tent", "headlamp", "trail mix"]:
        mcp.call("add_item", list_id=list_id, item=item)
    print("    ", mcp.call("get_list", list_id=list_id)["content"][0]["text"])

    print("3. Errors the model can fix come back as tool results")
    print("    ", mcp.call("add_item", list_id="lst_nope", item="x")["content"][0]["text"])

    print("4. Version negotiation: ask for a version the server doesn't speak")
    try:
        mcp.request("tools/list", version="2099-01-01")
    except RuntimeError as e:
        print("    ", e)
