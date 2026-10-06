"""Connect Claude to the MCP server: the host turns MCP tools into model tools, and model tool calls into MCP calls.

Usage:  python server.py --port 8001 &  python server.py --port 8002 &
        python agent.py "Make a packing list for a weekend hiking trip with 5 essentials, then show it to me."
"""

import sys

import anthropic

from client import INSTANCES, McpClient

MODEL = "claude-opus-5-5"
MAX_STEPS = 15
client = anthropic.Anthropic()


def main(task: str) -> str:
    mcp = McpClient(INSTANCES)
    server = mcp.request("server/discover")
    # MCP and the Claude API describe tools almost identically; only the key names differ.
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
             for t in mcp.request("tools/list")["tools"]]

    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_STEPS):
        response = client.beta.messages.create(
            model=MODEL, max_tokens=16000, tools=tools, messages=messages,
            system=server.get("instructions", ""),  # the server's own usage guidance
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason in ("refusal", "max_tokens"):
            return f"[{response.stop_reason}]"

        calls = [b for b in response.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in response.content if b.type == "text")

        results = []
        for call in calls:
            result = mcp.call(call.name, **call.input)  # model tool call -> MCP tools/call
            results.append({"type": "tool_result", "tool_use_id": call.id, "is_error": result.get("isError", False),
                            "content": "\n".join(c["text"] for c in result["content"] if c["type"] == "text")})
        messages.append({"role": "user", "content": results})
    return f"[stopped after {MAX_STEPS} steps]"


if __name__ == "__main__":
    print(main(" ".join(sys.argv[1:]) or "Make a packing list for a weekend hiking trip with 5 essentials, then show it to me."))
