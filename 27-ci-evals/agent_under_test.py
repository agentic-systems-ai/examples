"""The agent CI protects: an order-support assistant with five tools. Its prompt lives in prompts/, so prompt changes
go through review and through the eval gate like any other code change."""

import json
from pathlib import Path

from provider import make_client, model_id, request_options

MODEL = model_id("claude-opus-5-5")
PROMPTS = Path(__file__).parent / "prompts"

ORDERS = {
    "1042": {"email": "jo@example.com", "item": "Rain jacket", "status": "shipped", "tracking": "1Z999AA10123456784",
             "delivered": None},
    "1043": {"email": "jo@example.com", "item": "Running shoes", "status": "delivered", "tracking": "1Z999AA10123456785",
             "delivered": "2026-11-02"},
    "1044": {"email": "sam@example.com", "item": "Backpack", "status": "processing", "tracking": None, "delivered": None},
    "1045": {"email": "jo@example.com", "item": "Water bottle", "status": "delivered", "tracking": "1Z999AA10123456786",
             "delivered": "2026-09-20"},
    "1046": {"email": "ana@example.com", "item": "Tent", "status": "processing", "tracking": None, "delivered": None},
}

TOOLS = [
    {"name": "get_order", "description": "Look up one order by number.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["order_id"],
                      "properties": {"order_id": {"type": "string"}}}},
    {"name": "list_orders", "description": "List a customer's orders by email.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["email"],
                      "properties": {"email": {"type": "string"}}}},
    {"name": "update_address", "description": "Change an order's shipping address.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["order_id", "address"],
                      "properties": {"order_id": {"type": "string"}, "address": {"type": "string"}}}},
    {"name": "create_return", "description": "Open a return for an order.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["order_id", "reason"],
                      "properties": {"order_id": {"type": "string"}, "reason": {"type": "string"}}}},
    {"name": "escalate_to_human", "description": "Hand the conversation to a person, with a short reason.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["reason"],
                      "properties": {"reason": {"type": "string"}}}},
]


def run(user_message: str, prompt_file: str = "system.md") -> dict:
    """Run the agent on one message. Returns its final text, every tool call, and token usage, for graders."""
    client = make_client()
    system = (PROMPTS / prompt_file).read_text(encoding="utf-8")
    messages, calls, usage = [{"role": "user", "content": user_message}], [], {"input": 0, "output": 0}
    for _ in range(8):
        r = client.beta.messages.create(model=MODEL, max_tokens=2000, system=system, tools=TOOLS, messages=messages,
                                        output_config={"effort": "low"}, cache_control={"type": "ephemeral"},
                                        **request_options())
        u = r.usage
        usage["input"] += u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        usage["output"] += u.output_tokens
        messages.append({"role": "assistant", "content": r.content})
        tool_uses = [b for b in r.content if b.type == "tool_use"]
        if not tool_uses:
            return {"text": "".join(b.text for b in r.content if b.type == "text"), "calls": calls, "usage": usage}
        results = []
        for c in tool_uses:
            calls.append({"name": c.name, "input": dict(c.input)})
            if c.name == "get_order":
                o = ORDERS.get(c.input["order_id"])
                out = json.dumps({"order_id": c.input["order_id"], **o}) if o else "No such order."
            elif c.name == "list_orders":
                out = json.dumps([{"order_id": k, "item": v["item"], "status": v["status"]}
                                  for k, v in ORDERS.items() if v["email"] == c.input["email"].lower()])
            else:  # writes succeed: the policy lives in the prompt, which is exactly what this suite checks
                out = "OK."
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
        messages.append({"role": "user", "content": results})
    return {"text": "[step limit]", "calls": calls, "usage": usage}
