# 05 · MCP explained, and what changed when it went stateless

Companion code for the post [MCP explained, and what changed when it went stateless](https://www.agenticsystems.ai/blog/mcp-explained/).

A small, from-scratch implementation of the core of **MCP revision 2026-07-28**, the first stateless revision, written with Python's standard library only. Production code should use an official SDK; this one exists so you can see exactly what goes over the wire.

| File | What it does |
|---|---|
| `server.py` | A stateless MCP server with `server/discover`, `tools/list` (with caching hints) and `tools/call`. It validates headers against the body and rejects unknown protocol versions. Its three shopping-list tools keep state behind an explicit `list_id` handle in a shared store, so **any instance can serve any request**. |
| `client.py` | A client that sends each request to the **next server instance** in turn (a toy round-robin load balancer). It also caches `tools/list` for as long as the server's `ttlMs` allows, and shows version negotiation. |
| `agent.py` | Connects Claude to the server: MCP tools become model tools, and the model's tool calls become MCP `tools/call` requests. |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # only agent.py needs it

# terminal 1 and 2: two instances of the same server
python server.py --port 8001
python server.py --port 8002

# terminal 3: the protocol, step by step (no API key needed)
python client.py

# or let Claude use the tools
export ANTHROPIC_API_KEY=...     # Windows PowerShell: $env:ANTHROPIC_API_KEY="..."
python agent.py "Make a packing list for a weekend hiking trip with 5 essentials, then show it to me."
```

`client.py` prints which instance served each request. A single shopping list is created on one instance, extended on the other, and read back from the first. That only works because the protocol has no sessions.

## Poke at the protocol with curl

```bash
curl -s http://127.0.0.1:8001/mcp -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2026-07-28" -H "Mcp-Method: tools/list" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"_meta":{
        "io.modelcontextprotocol/protocolVersion":"2026-07-28",
        "io.modelcontextprotocol/clientCapabilities":{}}}}'
```

Then try changing one thing at a time:
- send `Mcp-Method: tools/call` while the body says `tools/list`: `400`, error `-32020` (header mismatch)
- drop the `_meta` block: `400`, error `-32602`
- send an `HTTP GET`: `405`, because the standalone stream from earlier revisions no longer exists

## What's deliberately left out

The SSE response mode, multi-round-trip requests (`input_required`), `subscriptions/listen`, authorization, resources and prompts. The post explains each of them, and the [specification](https://modelcontextprotocol.io/specification/2026-07-28) has the details.
