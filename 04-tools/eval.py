"""Evaluate two tool designs on the same tasks: accuracy, tool calls, tokens and errors.

Companion code for https://www.agenticsystems.ai/blog/designing-tools-for-agents/
Usage:  python eval.py --tools v1      (API-wrapper tools)
        python eval.py --tools v2      (agent-shaped tools)
"""

import argparse
import re
from dataclasses import dataclass

import anthropic

import crm

MODEL = "claude-opus-5-5"
MAX_STEPS = 12
client = anthropic.Anthropic()
SYSTEM = "You answer questions about Larkspur's customers using the CRM tools. Give a short, specific final answer."


# --------------------------------------------------------------------------- tasks with known answers

def spend(c):
    return sum(o["amount_usd"] for o in c.orders)


def open_tickets(c):
    return [t for t in c.tickets if t["status"] == "open"]


C = crm.BY_SHORT
TASKS = [
    (f"How much has {C['C-1003'].name} spent with us in total?", [str(spend(C["C-1003"]))]),
    (f"Which plan is {C['C-1058'].name} on, and which city are they based in?", [C["C-1058"].plan, C["C-1058"].city]),
    (f"How many open support tickets does {C['C-1005'].name} have?", [str(len(open_tickets(C["C-1005"])))]),
    (f"Who has spent more: {C['C-1058'].name} or {C['C-1008'].name}? By how much?",
     [max((C["C-1058"], C["C-1008"]), key=spend).name, str(abs(spend(C["C-1058"]) - spend(C["C-1008"])))]),
    (f"The customer with email {C['C-1002'].email} wrote in. How many open tickets do they have?",
     [str(len(open_tickets(C["C-1002"])))]),
    (f"How many orders has {C['C-1004'].name} placed?", [str(len(C["C-1004"].orders))]),
]


def grade(answer: str, expected: list[str]) -> bool:
    """Pass if every expected value appears in the answer as a whole word or number ("$1,972" matches "1972")."""
    flat = re.sub(r"(?<=\d),(?=\d)|\$", "", answer).lower()
    return all(re.search(rf"(?<![\w-]){re.escape(e.lower())}(?![\w-])", flat) for e in expected)


# --------------------------------------------------------------------------- a minimal agent loop with a meter

@dataclass
class Stats:
    tool_calls: int = 0
    errors: int = 0
    tokens: int = 0  # everything the model read, summed over steps


def run(task: str, tools: dict, schemas: list) -> tuple[str, Stats]:
    stats, messages = Stats(), [{"role": "user", "content": task}]
    for _ in range(MAX_STEPS):
        r = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=schemas, messages=messages,
            output_config={"effort": "low"}, cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        u = r.usage
        stats.tokens += u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        messages.append({"role": "assistant", "content": r.content})
        if r.stop_reason in ("refusal", "max_tokens"):
            return f"[{r.stop_reason}]", stats

        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in r.content if b.type == "text"), stats

        results = []
        for call in calls:
            stats.tool_calls += 1
            try:
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": tools[call.name](**call.input)})
            except Exception as exc:  # v1 leaks raw exceptions; v2 raises ToolError with guidance
                stats.errors += 1
                results.append({"type": "tool_result", "tool_use_id": call.id, "is_error": True,
                                "content": f"{type(exc).__name__}: {exc}"})
        messages.append({"role": "user", "content": results})
    return "[step limit]", stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", choices=["v1", "v2"], default="v2")
    version = parser.parse_args().tools
    tools, schemas = crm.TOOLSETS[version]

    totals, passed = Stats(), 0
    for i, (task, expected) in enumerate(TASKS, 1):
        answer, s = run(task, tools, schemas)
        ok = grade(answer, expected)
        passed += ok
        totals.tool_calls += s.tool_calls
        totals.errors += s.errors
        totals.tokens += s.tokens
        print(f"[{'PASS' if ok else 'FAIL'}] task {i}: {s.tool_calls} calls, {s.errors} errors, {s.tokens:,} tokens"
              f"\n       expected {expected} | answer: {answer.strip()[:120]!r}")

    n = len(TASKS)
    print(f"\n=== {version}: {passed}/{n} correct | {totals.tool_calls / n:.1f} tool calls, "
          f"{totals.errors / n:.1f} errors, {totals.tokens / n:,.0f} tokens per task")
