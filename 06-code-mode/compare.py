"""The same data task two ways: the model calls tools one by one, or writes code that calls them.

Companion code for https://www.agenticsystems.ai/blog/stop-calling-tools-start-writing-code/
Usage:  python compare.py --mode direct
        python compare.py --mode code
"""

import argparse
import json

import anthropic

import crm

MODEL = "claude-opus-5-5"
MAX_REQUESTS = 80
client = anthropic.Anthropic()

TASK = ("For every customer in Lisbon that has at least one open support ticket, list their name and total spend, "
        "highest spend first. Then give the number of such customers and their combined total spend.")


def tools_for(mode: str) -> list:
    if mode == "direct":
        return crm.SCHEMAS
    # Code mode: add the sandbox, and let code running in it call our tools as async Python functions.
    return [{"type": "code_execution_20260120", "name": "code_execution"}] + [
        {**schema, "allowed_callers": ["code_execution_20260120"]} for schema in crm.SCHEMAS
    ]


def run(mode: str) -> tuple[str, dict]:
    stats = {"api_requests": 0, "tool_calls": 0, "tokens_read": 0}
    messages, container, tools = [{"role": "user", "content": TASK}], None, tools_for(mode)

    for _ in range(MAX_REQUESTS):
        kwargs = dict(model=MODEL, max_tokens=16000, tools=tools, messages=messages,
                      output_config={"effort": "medium"}, cache_control={"type": "ephemeral"},
                      betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if container:
            kwargs["container"] = container  # required while code is paused waiting for our tool results
        r = client.beta.messages.create(**kwargs)

        u = r.usage
        stats["api_requests"] += 1
        stats["tokens_read"] += u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        if getattr(r, "container", None):
            container = r.container.id
        messages.append({"role": "assistant", "content": r.content})

        if r.stop_reason == "pause_turn":  # a long server-side step paused; send it back to continue
            continue
        if r.stop_reason in ("refusal", "max_tokens"):
            return f"[{r.stop_reason}]", stats

        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in r.content if b.type == "text"), stats

        # Direct calls: the result goes into the model's context.
        # Calls from code: the result goes to the paused code, and never enters the context.
        results = []
        for call in calls:
            stats["tool_calls"] += 1
            results.append({"type": "tool_result", "tool_use_id": call.id,
                            "content": crm.TOOLS[call.name](**call.input)})
        messages.append({"role": "user", "content": results})  # tool_result blocks only

    return "[request limit]", stats


def truth() -> tuple[int, int, str]:
    rows = [json.loads(crm.get_customer(c["customer_id"])) for c in json.loads(crm.list_customers("Lisbon"))]
    hits = sorted((r for r in rows if r["open_tickets"]), key=lambda r: -r["total_spend_usd"])
    return len(hits), sum(r["total_spend_usd"] for r in hits), hits[0]["name"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["direct", "code"], default="code")
    mode = parser.parse_args().mode

    answer, stats = run(mode)
    count, total, top = truth()
    print(answer)
    print(f"\n=== {mode}: {stats['api_requests']} API requests, {stats['tool_calls']} tool calls, "
          f"{stats['tokens_read']:,} tokens read")
    print(f"ground truth: {count} customers, ${total:,} combined, highest spend: {top}")
