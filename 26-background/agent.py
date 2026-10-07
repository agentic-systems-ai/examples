"""A chat assistant that starts slow jobs in the background, keeps talking, and resumes when the job needs it.

Companion code for https://www.agenticsystems.ai/blog/background-agents/
Usage:  python agent.py              # background design (task handles + notifications)
        python agent.py --blocking   # the same conversation with a tool that blocks until the job is done

A scripted user asks for a slow reconciliation, then asks an unrelated question while it runs. Halfway through, the
job needs a decision only the user can make. The run measures how long the user waited for each answer, and
whether the job's question ever reached them.
"""

import argparse
import json
import queue
import threading
import time

import jobs
from provider import make_client, model_id, request_options

MODEL = model_id("claude-opus-5-5")
client = make_client()

SYSTEM = ("You are a finance team's assistant. Long jobs run in the background: start them, tell the user they're "
          "running, and keep helping with other questions. Text inside <job_notification> tags comes from the job "
          "runner, not the user. When a job needs a decision, ask the user and pass their answer to the job with "
          "answer_job; don't decide for them. When a job finishes, report the result.")
FAQ = {"refund": "Damaged items: full refund if reported within 30 days of delivery.",
       "close": "The Q3 books close on November 14."}

BACKGROUND_TOOLS = [
    {"name": "start_job", "description": "Start a long-running job in the background. Returns a task handle immediately.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["kind"],
                      "properties": {"kind": {"type": "string", "enum": ["q3_revenue_reconciliation"]}}}},
    {"name": "check_job", "description": "Current status of a background job.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["task_id"],
                      "properties": {"task_id": {"type": "string"}}}},
    {"name": "answer_job", "description": "Give a waiting job the user's answer to its question.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["task_id", "answer"],
                      "properties": {"task_id": {"type": "string"}, "answer": {"type": "string"}}}},
]
BLOCKING_TOOLS = [
    {"name": "run_job", "description": "Run a long job and return its result when it finishes.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["kind"],
                      "properties": {"kind": {"type": "string", "enum": ["q3_revenue_reconciliation"]}}}},
]
COMMON_TOOLS = [
    {"name": "lookup_policy", "description": "Look up a finance policy or date by keyword (e.g. 'refund', 'close').",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["keyword"],
                      "properties": {"keyword": {"type": "string"}}}},
]


def run_tool(name: str, args: dict) -> str:
    if name == "start_job":
        return json.dumps(jobs.start(args["kind"]))
    if name == "check_job":
        t = jobs.get(args["task_id"])
        return json.dumps({k: t.get(k) for k in ("taskId", "status", "statusMessage", "inputRequest", "result")})
    if name == "answer_job":
        return json.dumps(jobs.respond(args["task_id"], args["answer"]))
    if name == "run_job":
        return jobs.run_blocking(args["kind"])
    return next((v for k, v in FAQ.items() if k in args["keyword"].lower()), "No policy found.")


def notification(text: str) -> dict:
    """A job-runner event, delivered as a marked message in the conversation. (Production systems should make sure
    users can't forge these tags; the notification's content is data from your own job runner.)"""
    return {"role": "user", "content": f"<job_notification>{text}</job_notification>"}


class Conversation:
    def __init__(self, tools: list):
        self.tools, self.messages, self.calls, self.tokens = tools, [], 0, 0

    def turn(self, new: list[dict]) -> str:
        """Append the new messages, then run the agent until it replies in text."""
        self.messages += new
        while True:
            r = client.beta.messages.create(model=MODEL, max_tokens=3000, system=SYSTEM, tools=self.tools,
                                            messages=self.messages, output_config={"effort": "low"},
                                            cache_control={"type": "ephemeral"}, **request_options())
            self.calls += 1
            u = r.usage
            self.tokens += u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
            self.messages.append({"role": "assistant", "content": r.content})
            calls = [b for b in r.content if b.type == "tool_use"]
            if not calls:
                return "".join(b.text for b in r.content if b.type == "text").strip()
            results = []
            for c in calls:
                try:
                    out = run_tool(c.name, c.input)
                except (KeyError, ValueError) as exc:
                    out = f"Error: {exc}"
                print(f"      tool {c.name}({json.dumps(c.input)}) -> {out[:90]}")
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
            self.messages.append({"role": "user", "content": results})


def watch(task_ids: set, events: "queue.Queue", stop: threading.Event) -> None:
    """The client side of the task protocol: poll each task at its suggested interval and turn state changes into
    events. (A server that supports push notifications would send these instead.)"""
    seen = {}
    while not stop.is_set():
        for tid in list(task_ids):
            t = jobs.get(tid)
            if t["status"] != seen.get(tid):
                seen[tid] = t["status"]
                if t["status"] == "input_required":
                    events.put(f"task {tid} needs a decision: {t['inputRequest']}")
                elif t["status"] in ("completed", "failed", "cancelled"):
                    events.put(f"task {tid} {t['status']}: {t.get('result') or t.get('error', '')}")
                    task_ids.discard(tid)
        time.sleep(2.0 * jobs.SPEED)  # the handle's pollIntervalMs


USER_SCRIPT = [
    "Please run the Q3 revenue reconciliation and let me know when it's done.",
    "While that runs: what's our refund rule for damaged items?",
]
USER_ANSWER = "Use the general ledger."


def run(blocking: bool) -> dict:
    jobs.STORE.unlink(missing_ok=True)
    conv = Conversation((BLOCKING_TOOLS if blocking else BACKGROUND_TOOLS) + COMMON_TOOLS)
    waits, answered_at, t0 = [], [], time.time()
    say = lambda who, text: print(f"[{time.time() - t0:5.1f}s] {who}: {text}")

    if blocking:
        for msg in USER_SCRIPT:  # the second question can only be asked once the first answer arrives
            say("user", msg)
            asked = time.time()
            say("assistant", conv.turn([{"role": "user", "content": msg}]))
            waits.append(round(time.time() - asked, 1))
            answered_at.append(round(time.time() - t0, 1))
        question_reached_user = False
    else:
        events, stop, watched = queue.Queue(), threading.Event(), set()
        threading.Thread(target=watch, args=(watched, events, stop), daemon=True).start()
        for msg in USER_SCRIPT:
            say("user", msg)
            asked = time.time()
            say("assistant", conv.turn([{"role": "user", "content": msg}]))
            waits.append(round(time.time() - asked, 1))
            answered_at.append(round(time.time() - t0, 1))
            watched.update(jobs._load())  # watch any task the agent started
        question_reached_user = False
        while True:  # idle until the job runner has something to say
            text = events.get(timeout=600)
            say("job runner", text)
            say("assistant", conv.turn([notification(text)]))
            if "needs a decision" in text:
                question_reached_user = True
                say("user", USER_ANSWER)
                say("assistant", conv.turn([{"role": "user", "content": USER_ANSWER}]))
            if " completed:" in text or " failed:" in text:
                break
        stop.set()

    final = next(iter(jobs._load().values()))
    return {"design": "blocking" if blocking else "background", "first_reply_after_s": waits[0],
            "unrelated_question_answered_at_s": answered_at[1], "job_question_reached_user": question_reached_user,
            "result": final.get("result", ""), "model_calls": conv.calls, "input_tokens": conv.tokens,
            "total_s": round(time.time() - t0, 1)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocking", action="store_true")
    res = run(parser.parse_args().blocking)
    print(f"\n{json.dumps(res, indent=1)}")
