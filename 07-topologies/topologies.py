"""One task, three agent topologies: compare correctness, total tokens, the largest single context, and time.

Companion code for https://www.agenticsystems.ai/blog/one-agent-or-many/
Usage:  python topologies.py --topology single|workers|orchestrator
"""

import argparse
import asyncio
import json
import time

import anthropic

from make_workspace import WORKSPACE, build

MODEL = "claude-opus-5-5"
MAX_STEPS = 40
client = anthropic.AsyncAnthropic()

QUESTION = ("Which service had the most total downtime across the incident reports, how many minutes in total, "
            "and what was that service's most common root cause?")
EXTRACT = ("Read each of these incident reports and return one line per report, exactly in the form "
           "'INC-1001 | service | minutes | root cause'. No other text.")


# --------------------------------------------------------------------------- shared agent loop

class Meter:
    def __init__(self):
        self.tokens, self.peak, self.agents = 0, 0, 0

    def add(self, usage) -> None:
        context = usage.input_tokens + (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
        self.tokens += context
        self.peak = max(self.peak, context)


meter = Meter()


def read_file(name: str, allowed: set[str]) -> str:
    if name not in allowed:
        raise ValueError(f"{name!r} is not one of your assigned files: {sorted(allowed)}")
    return (WORKSPACE / name).read_text(encoding="utf-8")


READ_TOOL = {"name": "read_file", "description": "Return the full text of one assigned incident report.",
             "input_schema": {"type": "object", "properties": {"name": {"type": "string"}},
                              "required": ["name"], "additionalProperties": False}}
DELEGATE_TOOL = {
    "name": "delegate",
    "description": "Give a batch of report files to a sub-agent with a fresh context. It reads them and returns one "
                   "line per report: 'INC-1001 | service | minutes | root cause'. Call it several times in one turn "
                   "to run sub-agents in parallel.",
    "input_schema": {"type": "object", "properties": {"files": {"type": "array", "items": {"type": "string"}}},
                     "required": ["files"], "additionalProperties": False}}


async def agent(task: str, tools: list, handlers: dict, label: str) -> str:
    """A plain agent loop. `handlers` maps tool names to async functions."""
    meter.agents += 1
    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_STEPS):
        r = await client.beta.messages.create(
            model=MODEL, max_tokens=16000, tools=tools, messages=messages,
            output_config={"effort": "low"}, cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        meter.add(r.usage)
        messages.append({"role": "assistant", "content": r.content})
        if r.stop_reason in ("refusal", "max_tokens"):
            return f"[{label}: {r.stop_reason}]"
        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in r.content if b.type == "text")

        async def run(call):
            try:
                return {"type": "tool_result", "tool_use_id": call.id, "content": await handlers[call.name](**call.input)}
            except Exception as exc:
                return {"type": "tool_result", "tool_use_id": call.id, "content": str(exc), "is_error": True}

        messages.append({"role": "user", "content": list(await asyncio.gather(*(run(c) for c in calls)))})
    return f"[{label}: step limit]"


def reader(files: list[str], label: str):
    """A sub-agent that may read only `files` and returns one line per report."""
    allowed = set(files)

    async def read(name: str) -> str:
        return read_file(name, allowed)

    return agent(f"{EXTRACT}\n\nYour files: {', '.join(files)}", [READ_TOOL], {"read_file": read}, label)


def all_files() -> list[str]:
    return sorted(p.name for p in WORKSPACE.glob("*.md"))


# --------------------------------------------------------------------------- the three topologies

async def single() -> str:
    """One agent, one context, reads everything."""
    files = all_files()

    async def read(name: str) -> str:
        return read_file(name, set(files))

    return await agent(f"{QUESTION}\n\nThe reports are: {', '.join(files)}", [READ_TOOL], {"read_file": read}, "single")


async def workers(n: int = 4) -> str:
    """Code splits the work, sub-agents read in parallel, code merges. No model coordinates anything."""
    files = all_files()
    batches = [files[i::n] for i in range(n)]
    tables = await asyncio.gather(*(reader(b, f"worker {i + 1}") for i, b in enumerate(batches)))
    return answer_from_table("\n".join(tables))


async def orchestrator() -> str:
    """A lead model decides how to split the work, delegates, and writes the final answer."""
    counter = iter(range(1, 100))

    async def delegate(files: list[str]) -> str:
        return await reader(files, f"sub-agent {next(counter)}")

    task = (f"{QUESTION}\n\nThere are {len(all_files())} reports: {', '.join(all_files())}. You cannot read them "
            "yourself; delegate batches to sub-agents, then compute the answer from their lines.")
    return await agent(task, [DELEGATE_TOOL], {"delegate": delegate}, "lead")


def answer_from_table(table: str) -> str:
    """Plain code does the aggregation in the 'workers' topology."""
    minutes, causes = {}, {}
    for line in table.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 4 and parts[2].isdigit():
            minutes[parts[1]] = minutes.get(parts[1], 0) + int(parts[2])
            causes.setdefault(parts[1], []).append(parts[3].rstrip("."))
    worst = max(minutes, key=minutes.get)
    common = max(set(causes[worst]), key=causes[worst].count)
    return f"{worst}: {minutes[worst]} minutes in total, most often caused by {common} ({len(causes[worst])} incidents)"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topology", choices=["single", "workers", "orchestrator"], default="single")
    topology = parser.parse_args().topology

    truth = build()
    started = time.perf_counter()
    answer = asyncio.run({"single": single, "workers": workers, "orchestrator": orchestrator}[topology]())
    elapsed = time.perf_counter() - started

    print(answer)
    print(f"\n=== {topology}: {meter.agents} agents | {meter.tokens:,} tokens read in total | "
          f"largest single context {meter.peak:,} | {elapsed:.0f}s")
    print(f"ground truth: {truth['service']}, {truth['minutes']} minutes, mostly {truth['root_cause']}")
