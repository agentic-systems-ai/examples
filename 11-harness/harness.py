"""A small long-running harness: durable state outside the model, one fresh context per work item,
a verification gate, and resume-after-crash.

Companion code for https://www.agenticsystems.ai/blog/harness-engineering/
Usage:  python harness.py --limit 8                       # summarize the first 8 incident reports
        python harness.py --limit 8 --crash-after 3       # simulate a crash after 3 verified items
        python harness.py --limit 8                       # run again: resumes where it stopped

Everything the harness knows lives in run/: progress.json (the work list and each item's status) and
events.jsonl (an append-only log of every model call and tool call). The model's context is disposable.
"""

import argparse
import json
import re
import time
from pathlib import Path

import anthropic

from make_workspace import WORKSPACE, build

MODEL = "claude-opus-5-5"
MAX_STEPS_PER_ITEM = 8
MAX_ATTEMPTS = 3
RUN = Path(__file__).parent / "run"
PROGRESS, EVENTS, OUT = RUN / "progress.json", RUN / "events.jsonl", RUN / "summaries"
client = anthropic.Anthropic()


# --------------------------------------------------------------------------- durable state

def log(kind: str, **data) -> None:
    """Append-only event log: never rewritten, so it survives crashes and can be replayed or inspected."""
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": round(time.time(), 3), "kind": kind, **data}) + "\n")


def load_progress(limit: int) -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    # "Initializer" step: turn the job into an explicit work list before any agent runs.
    items = sorted(p.stem for p in WORKSPACE.glob("*.md"))[:limit]
    progress = {"items": {i: {"status": "todo", "attempts": 0} for i in items}}
    save_progress(progress)
    log("initialized", items=items)
    return progress


def save_progress(progress: dict) -> None:
    tmp = PROGRESS.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, indent=1))
    tmp.replace(PROGRESS)  # atomic: a crash never leaves a half-written progress file


# --------------------------------------------------------------------------- the "hands": tools behind one interface

def execute(name: str, args: dict) -> str:
    """Every tool call goes through here. Swap this for a sandbox or a remote service without touching the loop."""
    if name == "read_report":
        return (WORKSPACE / f"{args['report_id']}.md").read_text(encoding="utf-8")
    if name == "write_summary":
        (OUT / f"{args['report_id']}.md").write_text(args["summary"].strip() + "\n", encoding="utf-8")
        return "saved"
    raise ValueError(f"unknown tool {name}")


TOOLS = [
    {"name": "read_report", "description": "Return the full text of one incident report.",
     "input_schema": {"type": "object", "properties": {"report_id": {"type": "string"}},
                      "required": ["report_id"], "additionalProperties": False}},
    {"name": "write_summary", "description": "Save the one-sentence summary for a report (overwrites).",
     "input_schema": {"type": "object", "properties": {"report_id": {"type": "string"}, "summary": {"type": "string"}},
                      "required": ["report_id", "summary"], "additionalProperties": False}},
]


# --------------------------------------------------------------------------- the verification gate (plain code)

def verify(report_id: str) -> tuple[bool, str]:
    path = OUT / f"{report_id}.md"
    if not path.exists():
        return False, "no summary was written"
    summary, report = path.read_text(encoding="utf-8"), (WORKSPACE / f"{report_id}.md").read_text(encoding="utf-8")
    service = re.search(r"Service: (\w+)", report)[1]
    minutes = re.search(r"impact: (\d+) minutes", report)[1]
    cause = re.search(r"Root cause: ([^.]+)", report)[1]
    problems = [p for p, ok in [
        (f"must name the service '{service}'", service in summary.lower()),
        (f"must give the impact ({minutes} minutes)", minutes in summary),
        (f"must give the root cause '{cause}'", cause in summary.lower()),
        ("must be one sentence of at most 35 words", len(summary.split()) <= 35),
    ] if not ok]
    return not problems, "; ".join(problems) or "ok"


# --------------------------------------------------------------------------- one work item = one fresh context

def work_on(report_id: str, feedback: str) -> None:
    task = (f"Summarize incident report {report_id} in one sentence (max 35 words) that names the service, the "
            f"customer-impact minutes and the root cause. Read it with read_report, save with write_summary.")
    if feedback:
        task += f"\nA previous attempt failed verification: {feedback}"
    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_STEPS_PER_ITEM):
        r = client.beta.messages.create(
            model=MODEL, max_tokens=16000, tools=TOOLS, messages=messages, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        log("model_call", item=report_id, stop=r.stop_reason, input_tokens=r.usage.input_tokens,
            output_tokens=r.usage.output_tokens)
        messages.append({"role": "assistant", "content": r.content})
        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls:
            return
        results = []
        for c in calls:
            try:
                out, err = execute(c.name, c.input), False
            except Exception as exc:
                out, err = f"{type(exc).__name__}: {exc}", True
            log("tool_call", item=report_id, tool=c.name, error=err)
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": err})
        messages.append({"role": "user", "content": results})


def main(limit: int, crash_after: int | None) -> None:
    RUN.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    build()
    progress = load_progress(limit)
    log("session_start", pending=[i for i, s in progress["items"].items() if s["status"] != "done"])

    verified_this_run = 0
    for report_id, state in progress["items"].items():
        if state["status"] in ("done", "failed"):
            continue  # resume: verified work is never redone
        while state["attempts"] < MAX_ATTEMPTS:
            state["attempts"] += 1
            state["status"] = "in_progress"
            save_progress(progress)
            work_on(report_id, state.get("feedback", ""))
            ok, reason = verify(report_id)
            log("verified", item=report_id, ok=ok, reason=reason)
            state["status"], state["feedback"] = ("done", "") if ok else ("todo", reason)
            save_progress(progress)
            print(f"  {report_id}: {'verified' if ok else 'FAILED verification - ' + reason} (attempt {state['attempts']})")
            if ok:
                break
        if state["status"] != "done":
            state["status"] = "failed"  # give up after MAX_ATTEMPTS and flag it for a human
            save_progress(progress)
            continue
        verified_this_run += 1
        if crash_after and verified_this_run >= crash_after:
            log("crash_simulated")
            raise SystemExit(f"\n!!! simulated crash after {verified_this_run} items - run the same command again to resume")

    counts = {s: sum(v["status"] == s for v in progress["items"].values()) for s in ("done", "failed", "todo")}
    log("session_end", **counts)
    print(f"\n=== {counts['done']} done, {counts['failed']} need a human, {counts['todo']} remaining | "
          f"state in {RUN.name}/ (delete it to start over)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--crash-after", type=int)
    args = parser.parse_args()
    main(args.limit, args.crash_after)
