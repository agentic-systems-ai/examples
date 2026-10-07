"""Prompt caching, measured: one agent transcript replayed under five prompt-assembly variants.

Companion code for https://www.agenticsystems.ai/blog/prompt-caching-properly/
Usage:  python agent.py record      # run the agent once for real and save transcript.json
        python agent.py replay      # replay that transcript under each variant and compare cache behaviour
        python agent.py all         # both

Why replay? Agents are stochastic: two runs take different paths and use different tokens, which would swamp the
effect we want to see. So we record one real run, then send exactly the same sequence of requests again under each
variant, changing only how the prompt is assembled. Replays use max_tokens=0, which runs the prompt (and writes or
reads the cache) but generates nothing, so each replay costs only its input tokens.
"""

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from provider import BEDROCK, make_client, model_id, request_options

MODEL = model_id("claude-opus-5-5")
HERE = Path(__file__).parent
TRANSCRIPT = HERE / "transcript.json"
PRICE = {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00}  # $/M tokens, Claude Opus 5.5
client = make_client()

# --------------------------------------------------------------------------- the agent's world

WAREHOUSES = ["Reno", "Columbus", "Atlanta", "Newark"]
SHIPMENTS = {  # (shipped, late) per warehouse and month
    ("Reno", "2026-08"): (4120, 98), ("Reno", "2026-09"): (4310, 104),
    ("Columbus", "2026-08"): (3880, 85), ("Columbus", "2026-09"): (3925, 291),
    ("Atlanta", "2026-08"): (5010, 140), ("Atlanta", "2026-09"): (5240, 151),
    ("Newark", "2026-08"): (2970, 77), ("Newark", "2026-09"): (3015, 69),
}
INCIDENTS = {
    ("Columbus", "2026-09"): ["Sep 8: conveyor 3 down for 26 hours", "Sep 9-12: backlog cleared with overtime",
                              "Sep 15: carrier pickup window moved from 18:00 to 15:00"],
    ("Atlanta", "2026-09"): ["Sep 22: power outage, 2 hours"],
}

TOOLS = [
    {"name": "list_warehouses", "description": "List the company's warehouses.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_shipments", "description": "Shipments and late shipments for one warehouse in one month (YYYY-MM).",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["warehouse", "month"],
                      "properties": {"warehouse": {"type": "string"}, "month": {"type": "string"}}}},
    {"name": "get_incidents", "description": "Operational incidents logged at a warehouse in a month (YYYY-MM).",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["warehouse", "month"],
                      "properties": {"warehouse": {"type": "string"}, "month": {"type": "string"}}}},
]


def run_tool(name: str, args: dict) -> str:
    if name == "list_warehouses":
        return json.dumps(WAREHOUSES)
    key = (args.get("warehouse"), args.get("month"))
    if name == "get_shipments":
        if key not in SHIPMENTS:
            return "No data for that warehouse and month."
        shipped, late = SHIPMENTS[key]
        return json.dumps({"shipped": shipped, "late": late, "late_rate": round(late / shipped, 4)}, sort_keys=True)
    return json.dumps(INCIDENTS.get(key, []))


# A long, stable system prompt: the kind of handbook real agents carry. It's what makes caching worth it.
HANDBOOK = "\n".join(
    [f"Rule {i}: " + text for i, text in enumerate([
        "Compare like with like: the same metric, the same period length, the same definition of late.",
        "A shipment is late when it is delivered after the promised date shown at checkout.",
        "Report rates as well as counts; volumes differ by warehouse.",
        "Prefer month-over-month change in the late rate when asked which site got worse.",
        "Always check the incident log before naming a cause; never guess a cause the data doesn't show.",
        "Distinguish one-off events (outages) from lasting changes (schedules, staffing, carriers).",
        "Quote the numbers you used so the reader can check them.",
        "If two causes are plausible, say which the timing supports and why.",
        "Keep the final answer under 120 words, with a one-line recommendation.",
    ] * 6, 1)]  # repeated sections stand in for a real handbook's length
)
SYSTEM = ("You are an operations analyst for a retail company's logistics team. Use the tools to answer with data. "
          "Follow the team handbook.\n\n<handbook>\n" + HANDBOOK + "\n</handbook>")
TASK = "Which warehouse got worse at on-time shipping from August to September 2026, and what's the most likely cause?"


# --------------------------------------------------------------------------- 1. record one real run

def record() -> list:
    messages = [{"role": "user", "content": TASK}]
    for step in range(1, 16):
        r = client.beta.messages.create(model=MODEL, max_tokens=4000, tools=TOOLS, messages=messages,
                                        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                                        output_config={"effort": "low"}, cache_control={"type": "ephemeral"},
                                        **request_options())
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]})
        calls = [b for b in r.content if b.type == "tool_use"]
        print(f"[record {step}] " + (", ".join(f"{c.name}({json.dumps(c.input)})" for c in calls) or "final answer"))
        if not calls:
            print("\n" + "".join(b.text for b in r.content if b.type == "text"))
            break
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c.id,
                                                      "content": run_tool(c.name, c.input)} for c in calls]})
    TRANSCRIPT.write_text(json.dumps(messages, indent=1), encoding="utf-8")
    print(f"\nsaved {TRANSCRIPT.name}: {len(messages)} messages")
    return messages


# --------------------------------------------------------------------------- 2. replay under each variant

REMINDER = "<reminder>Check the incident log before naming a cause.</reminder>"


def without_thinking(transcript: list) -> list:
    """Drop recorded thinking blocks. On Claude Opus 5.5 a thinking block is bound to the exact prompt that produced
    it, so replaying it under a variant that changes the prompt is rejected on accounts where that check is enforced.
    Stripping every thinking block is the documented recovery; we do it for all variants so they stay comparable."""
    out = []
    for m in transcript:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            m = {**m, "content": [b for b in m["content"] if b.get("type") not in ("thinking", "redacted_thinking")]}
        out.append(m)
    return out


def requests_for(variant: str, transcript: list):
    """Yield (system, tools, messages, cache) for each request the agent made, assembled the variant's way."""
    transcript = without_thinking(transcript)
    user_turns = [i for i, m in enumerate(transcript) if m["role"] == "user"]
    for k, i in enumerate(user_turns):  # each request ends at a user turn: the task, then each batch of tool results
        messages = [dict(m) for m in transcript[: i + 1]]
        system, tools, cache = SYSTEM, TOOLS, {"type": "ephemeral"}
        if variant == "timestamp":
            # Silent breaker 1: "helpful" context at the top of the system prompt, different on every request.
            system = f"Current time: {datetime.now(timezone.utc).isoformat(timespec='microseconds')}\n\n" + SYSTEM
        elif variant == "tool_order":
            # Silent breaker 2: the same tools in a different order on each request, as when they're collected from a
            # set or from plugins that register in a nondeterministic order.
            tools = TOOLS[k % len(TOOLS):] + TOOLS[:k % len(TOOLS)]
        elif variant == "history_edit":
            # Silent breaker 3: a reminder injected into the newest turn and removed from older ones. Every request
            # rewrites the previous request's last message, so the prefix it cached never matches again.
            last = messages[-1]
            content = last["content"] if isinstance(last["content"], list) else [{"type": "text", "text": last["content"]}]
            messages[-1] = {"role": "user", "content": content + [{"type": "text", "text": REMINDER}]}
        elif variant == "no_cache":
            cache = None
        yield system, tools, messages, cache


def replay(transcript: list) -> list:
    rows = []
    run_id = f"{random.getrandbits(32):08x}"
    for variant in ["stable", "timestamp", "tool_order", "history_edit", "no_cache"]:
        # Every variant replays the same conversation within a few minutes, so without this tag a later variant could
        # read cache entries an earlier one wrote. A per-variant tag at the start of the system prompt keeps each
        # variant's cache separate (and keeps a second run of this script from reading the first run's entries).
        tag = f"[replay {run_id} {variant}]\n"
        tot = {"variant": variant, "requests": 0, "uncached": 0, "write": 0, "read": 0, "reasons": []}
        prev_id = None
        for system, tools, messages, cache in requests_for(variant, transcript):
            # The robust setup for agent loops: an explicit breakpoint at the end of the stable system prompt, plus
            # automatic caching (top-level cache_control) for the growing conversation.
            system_blocks = [{"type": "text", "text": tag + system, **({"cache_control": cache} if cache else {})}]
            extra = {"cache_control": cache} if cache else {}
            if not BEDROCK:  # cache diagnostics: the API reports where this request diverged from the previous one
                extra["diagnostics"] = {"previous_message_id": prev_id}
            r = client.beta.messages.create(model=MODEL, max_tokens=0, system=system_blocks, tools=tools, messages=messages,
                                            output_config={"effort": "low"}, **extra, **request_options())
            prev_id = r.id
            u = r.usage
            tot["requests"] += 1
            tot["uncached"] += u.input_tokens
            tot["write"] += u.cache_creation_input_tokens or 0
            tot["read"] += u.cache_read_input_tokens or 0
            reason = getattr(getattr(r, "diagnostics", None), "cache_miss_reason", None)
            if reason is not None and getattr(reason, "type", None):
                tot["reasons"].append(reason.type)
            print(f"  [{variant:<12} {tot['requests']:>2}] uncached {u.input_tokens:>6,}  write "
                  f"{u.cache_creation_input_tokens or 0:>6,}  read {u.cache_read_input_tokens or 0:>6,}"
                  + (f"  diagnostics: {reason.type}" if reason is not None and getattr(reason, 'type', None) else ""))
        total = tot["uncached"] + tot["write"] + tot["read"]
        tot["hit_rate"] = tot["read"] / total if total else 0.0
        tot["cost"] = (tot["uncached"] * PRICE["input"] + tot["write"] * PRICE["cache_write"]
                       + tot["read"] * PRICE["cache_read"]) / 1e6
        rows.append(tot)
    base = next(r["cost"] for r in rows if r["variant"] == "no_cache")
    print(f"\n{'variant':<14}{'requests':>9}{'uncached':>10}{'written':>10}{'read':>10}{'hit rate':>10}"
          f"{'input $':>10}{'vs none':>9}  diagnostics")
    for r in rows:
        reasons = ", ".join(sorted(set(r["reasons"]))) or "-"
        print(f"{r['variant']:<14}{r['requests']:>9}{r['uncached']:>10,}{r['write']:>10,}{r['read']:>10,}"
              f"{r['hit_rate']:>10.0%}{r['cost']:>10.4f}{r['cost'] / base:>9.0%}  {reasons}")
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("record", "all"):
        record()
    if cmd in ("replay", "all"):
        replay(json.loads(TRANSCRIPT.read_text(encoding="utf-8")))
