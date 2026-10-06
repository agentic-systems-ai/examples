"""Print the most recent trace in traces.jsonl as a tree: who did what, in what order, at what cost.

Usage:  python show_trace.py
"""

import json
from collections import defaultdict

spans = [json.loads(line) for line in open("traces.jsonl", encoding="utf-8")]
latest = max(spans, key=lambda s: s["end"])["trace_id"]
spans = [s for s in spans if s["trace_id"] == latest]
children = defaultdict(list)
for s in spans:
    children[s["parent_id"]].append(s)


def show(span: dict, depth: int = 0) -> None:
    a = span["attributes"]
    ms = (span["end"] - span["start"]) / 1e6
    detail = []
    if "gen_ai.agent.id" in a:
        detail.append(f"id={a['gen_ai.agent.id']}@{a.get('gen_ai.agent.version', '?')} for {a.get('app.on_behalf_of', '?')}")
    if "gen_ai.usage.input_tokens" in a:
        detail.append(f"in={a['gen_ai.usage.input_tokens']} out={a['gen_ai.usage.output_tokens']}")
    if span["status"] == "ERROR":
        detail.append(f"ERROR {a.get('error.type', '')}")
    print(f"{'  ' * depth}{span['name']:<34} {ms:8.0f} ms  {' '.join(detail)}")
    for child in sorted(children[span["span_id"]], key=lambda s: s["start"]):
        show(child, depth + 1)


print(f"trace {latest}\n")
for root in children[None]:
    show(root)

tokens = sum(s["attributes"].get("gen_ai.usage.input_tokens", 0) for s in spans)
print(f"\n{len(spans)} spans | {sum('chat ' in s['name'] for s in spans)} model calls | "
      f"{sum(s['name'].startswith('execute_tool') for s in spans)} tool calls | {tokens:,} input tokens")
