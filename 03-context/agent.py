"""Context engineering demo: one research task, three ways of managing the context window.

Companion code for https://www.agenticsystems.ai/blog/context-is-a-budget/
Usage:  python agent.py --strategy naive|clear|compact
"""

import argparse

import anthropic

from make_workspace import WORKSPACE, build

MODEL = "claude-opus-5-5"
MAX_STEPS = 60
CLEAR_AT = 12_000    # "clear": server-side clearing of old tool results starts above this many tokens
COMPACT_AT = 15_000  # "compact": summarize and restart above this many tokens (low on purpose, so it triggers)

# USD per million tokens for Claude Opus 5.5 as of Oct 2026 - check current pricing before relying on it.
PRICE = {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00}

client = anthropic.Anthropic()

TASK = (
    "The workspace holds incident reports. Which service had the most total downtime across all reports, "
    "how many minutes was that in total, and what was that service's most common root cause? "
    "Every report matters, so read all of them."
)
SYSTEM = (
    "You are a reliability analyst working through a folder of incident reports. "
    "Read reports one or two at a time. After reading a report, immediately call save_note with its "
    "service, customer-impact minutes and root cause, so you never need to read it again. "
    "When every report has a note, answer from your notes and show the arithmetic."
)

notes: list[str] = []  # lives outside the context window, so no context strategy can lose it


def list_files() -> str:
    return "\n".join(sorted(p.name for p in WORKSPACE.glob("*.md")))


def read_file(name: str) -> str:
    path = (WORKSPACE / name).resolve()
    if path.parent != WORKSPACE.resolve():
        raise ValueError(f"{name!r} is outside the workspace")
    return path.read_text(encoding="utf-8")


def save_note(note: str) -> str:
    notes.append(note)
    return f"saved ({len(notes)} notes so far)"


TOOLS = {"list_files": list_files, "read_file": read_file, "save_note": save_note}
TOOL_SCHEMAS = [
    {"name": "list_files", "description": "List the incident report files.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"name": "read_file", "description": "Return the full text of one incident report by file name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}},
                      "required": ["name"], "additionalProperties": False}, "strict": True},
    {"name": "save_note",
     "description": "Save a short note to persistent storage, e.g. 'INC-1007: auth, 42 min, bad deploy'. "
                    "Notes survive even if old tool results are cleared from your context.",
     "input_schema": {"type": "object", "properties": {"note": {"type": "string"}},
                      "required": ["note"], "additionalProperties": False}, "strict": True},
]


def call(messages: list, strategy: str, **extra):
    kwargs = dict(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,  # never changes during a run: a stable prefix is what makes caching work
        tools=TOOL_SCHEMAS,
        messages=messages,
        output_config={"effort": "low"},
        cache_control={"type": "ephemeral"},  # cache everything up to the latest message
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        **extra,
    )
    if strategy == "clear":
        # The server drops old tool results before the model sees them. Our `messages` list stays
        # append-only, which keeps the model's earlier reasoning valid (see the post for why that matters).
        kwargs["betas"] = kwargs["betas"] + ["context-management-2025-06-27"]
        kwargs["context_management"] = {"edits": [{
            "type": "clear_tool_uses_20250919",
            "trigger": {"type": "input_tokens", "value": CLEAR_AT},
            "keep": {"type": "tool_uses", "value": 2},
            "exclude_tools": ["save_note"],
        }]}
    return client.beta.messages.create(**kwargs)


def compact(messages: list) -> list:
    """Simple compaction: ask for a progress summary, then restart from task + summary + notes.

    We replace the *whole* history rather than editing the middle of it, and the new history
    replays none of the model's earlier reasoning, so nothing the API checks has been altered.
    """
    request = messages + [{"role": "user", "content":
        "Pause. In under 150 words, summarize progress: which reports are done, and anything not yet in your notes."}]
    response = call(request, "compact", tool_choice={"type": "none"})
    summary = "".join(b.text for b in response.content if b.type == "text")
    meter.add(response, label="summary")
    return [{"role": "user", "content":
        f"{TASK}\n\nYou are resuming earlier work.\nProgress summary:\n{summary}\n\nSaved notes:\n" + "\n".join(notes)}]


class Meter:
    def __init__(self):
        self.totals = dict(input=0, cache_write=0, cache_read=0, output=0)
        self.peak = 0

    def add(self, response, label: str) -> int:
        u = response.usage
        cache_read, cache_write = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
        context = u.input_tokens + cache_read + cache_write  # everything the model read this call
        for key, value in [("input", u.input_tokens), ("cache_write", cache_write),
                           ("cache_read", cache_read), ("output", u.output_tokens)]:
            self.totals[key] += value
        self.peak = max(self.peak, context)
        bar = "#" * min(60, context // 1000)
        print(f"{label:>8}  {context:7,} tok  cached {cache_read:7,}  {bar}")
        return context

    def report(self, strategy: str) -> None:
        t = self.totals
        cost = sum(t[k] * PRICE[k] for k in t) / 1e6
        print(f"\n=== {strategy}: peak context {self.peak:,} tokens | read {t['input'] + t['cache_write'] + t['cache_read']:,} "
              f"(of which cached {t['cache_read']:,}) | wrote {t['output']:,} | est. ${cost:.2f}")


meter = Meter()


def run(strategy: str) -> str:
    messages = [{"role": "user", "content": TASK}]
    context = 0

    for step in range(1, MAX_STEPS + 1):
        if strategy == "compact" and context > COMPACT_AT:
            messages = compact(messages)
            print("          --- compacted: history replaced by summary + notes ---")

        response = call(messages, strategy)
        context = meter.add(response, label=f"step {step}")
        edits = getattr(response, "context_management", None)
        for edit in (edits.applied_edits if edits else None) or []:
            print(f"          --- server cleared {edit.cleared_tool_uses} old tool results "
                  f"({edit.cleared_input_tokens:,} tokens) ---")
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return "[the model declined this task]"
        if response.stop_reason == "max_tokens":
            return "[response was cut off - raise max_tokens]"

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            return "".join(b.text for b in response.content if b.type == "text")

        results = []
        for call_ in tool_calls:
            try:
                results.append({"type": "tool_result", "tool_use_id": call_.id,
                                "content": TOOLS[call_.name](**call_.input)})
            except Exception as exc:
                results.append({"type": "tool_result", "tool_use_id": call_.id, "content": str(exc), "is_error": True})
        messages.append({"role": "user", "content": results})

    return f"[stopped after {MAX_STEPS} steps]"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["naive", "clear", "compact"], default="naive")
    strategy = parser.parse_args().strategy

    truth = build()
    print(run(strategy))
    meter.report(strategy)
    print(f"ground truth: {truth['service']}, {truth['minutes']} minutes, mostly {truth['root_cause']}")
