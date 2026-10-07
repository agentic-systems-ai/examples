"""A durable background job runner with MCP-style task handles.

A slow job returns a handle at once instead of blocking: {taskId, status, pollIntervalMs, ttlMs}. Status moves
through working -> (input_required -> working) -> completed | failed | cancelled, the same states as MCP's Tasks
extension. State lives in a JSON file, so a client that restarts can pick the task up again by its id.
"""

import json
import threading
import time
import uuid
from pathlib import Path

STORE = Path(__file__).parent / "tasks.json"
_lock = threading.Lock()
SPEED = 1.0  # multiply all job durations (tests set this small)


def _load() -> dict:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}


def _save(tasks: dict) -> None:
    STORE.write_text(json.dumps(tasks, indent=1), encoding="utf-8")


def _update(task_id: str, **fields) -> dict:
    with _lock:
        tasks = _load()
        tasks[task_id].update(fields, updatedAt=time.time())
        _save(tasks)
        return dict(tasks[task_id])


def get(task_id: str) -> dict:
    with _lock:
        t = _load().get(task_id)
    if t is None:
        raise KeyError(f"no task {task_id}")
    return t


def respond(task_id: str, answer: str) -> dict:
    """The client's answer to an input request (tasks/update in MCP)."""
    t = get(task_id)
    if t["status"] != "input_required":
        raise ValueError(f"task {task_id} is {t['status']}, not waiting for input")
    return _update(task_id, status="working", inputResponse=answer, statusMessage="Resuming with your answer.")


def _reconcile(task_id: str) -> None:
    """The slow job: reconcile Q3 revenue across two systems. Pauses once to ask which ledger is authoritative."""
    steps = ["Loading invoices from billing", "Loading payments from the bank feed", "Matching 4,812 transactions"]
    for i, step in enumerate(steps):
        _update(task_id, statusMessage=f"{step} ({i + 1}/5)")
        time.sleep(3 * SPEED)
    _update(task_id, status="input_required", statusMessage="Waiting for input",
            inputRequest="Billing and the general ledger disagree on 37 invoices ($18,240 net). "
                         "Which is authoritative for Q3: 'billing' or 'general ledger'?")
    while get(task_id)["status"] == "input_required":  # a real runner would release the worker and wake on update
        time.sleep(0.2 * SPEED)
    answer = get(task_id).get("inputResponse", "")
    _update(task_id, statusMessage="Applying the authoritative source (4/5)")
    time.sleep(3 * SPEED)
    _update(task_id, statusMessage="Writing the report (5/5)")
    time.sleep(2 * SPEED)
    source = "general ledger" if "ledger" in answer.lower() else "billing"
    _update(task_id, status="completed", statusMessage="Done",
            result=f"Q3 revenue reconciled using the {source} as authoritative: $2,418,760 recognized; "
                   f"37 invoices adjusted ($18,240 net); 3 payments unmatched ($1,120), listed in the report.")


def start(kind: str) -> dict:
    """Create the task durably, start the work, and return the handle immediately."""
    if kind != "q3_revenue_reconciliation":
        raise ValueError(f"unknown job {kind!r}")
    task = {"taskId": f"task_{uuid.uuid4().hex[:8]}", "kind": kind, "status": "working",
            "statusMessage": "Queued", "pollIntervalMs": 2000, "ttlMs": 24 * 3600 * 1000,
            "createdAt": time.time(), "updatedAt": time.time()}
    with _lock:
        tasks = _load()
        tasks[task["taskId"]] = task
        _save(tasks)
    threading.Thread(target=_reconcile, args=(task["taskId"],), daemon=True).start()
    return {k: task[k] for k in ("taskId", "status", "statusMessage", "pollIntervalMs", "ttlMs")}


def run_blocking(kind: str) -> str:
    """The synchronous alternative: wait for the job to finish. Nobody can answer its question, so it has to guess."""
    handle = start(kind)
    while True:
        t = get(handle["taskId"])
        if t["status"] == "input_required":
            respond(handle["taskId"], "billing")  # no way to reach the user mid-call: fall back to a default
        if t["status"] in ("completed", "failed", "cancelled"):
            return t.get("result") or t.get("error", t["status"])
        time.sleep(0.2 * SPEED)
