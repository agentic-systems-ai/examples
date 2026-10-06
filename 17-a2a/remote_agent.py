"""A remote agent that speaks A2A 1.0 over JSON-RPC, standard library plus the Anthropic SDK.

Companion code for https://www.agenticsystems.ai/blog/a2a-explained/
Usage:  python remote_agent.py --port 9001

It publishes an Agent Card at /.well-known/agent-card.json and accepts SendMessage, GetTask and CancelTask
at /a2a. Behind the protocol is an ordinary tool-using agent (the CRM specialist from post #4). Callers never
see its tools, prompts or memory - only tasks, messages and artifacts. That opacity is the point of A2A.

This is a teaching implementation of the core request path, not the full specification.
"""

import argparse
import json
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import crm
from provider import make_client, model_id, request_options

VERSION = "1.0"
MODEL = model_id("claude-opus-5-5")
client = make_client()

TASKS: dict[str, dict] = {}       # task id -> A2A Task object
HISTORY: dict[str, list] = {}     # task id -> the model conversation behind it (private to this agent)
lock = threading.Lock()


def agent_card(base_url: str) -> dict:
    return {
        "name": "Larkspur CRM specialist",
        "description": "Answers questions about Larkspur customers: plans, spend, orders and open support tickets.",
        "version": "1.0.0",
        "supportedInterfaces": [{"url": f"{base_url}/a2a", "protocolBinding": "JSONRPC", "protocolVersion": VERSION}],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{
            "id": "customer-lookup",
            "name": "Customer lookup",
            "description": "Look up a customer by name or email and report plan, city, spend and open tickets.",
            "tags": ["crm", "customers", "support"],
            "examples": ["How much has Riverside Legal spent?", "Does Harbor Analytics have open tickets?"],
        }],
    }


SYSTEM = ("You are Larkspur's CRM specialist. Use the CRM tools to answer precisely and briefly. If the request "
          "matches more than one customer, or is too vague to answer, do not guess: reply with a line starting "
          "'NEED_INPUT:' followed by one short clarifying question.")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_message(role: str, text: str, task: dict) -> dict:
    return {"role": role, "parts": [{"text": text}], "messageId": str(uuid.uuid4()),
            "taskId": task["id"], "contextId": task["contextId"]}


def run_agent(task_id: str) -> None:
    """Advance one task: run the tool-using agent until it answers or needs input."""
    tools, schemas = crm.TOOLSETS["v2"]
    messages = HISTORY[task_id]
    try:
        for _ in range(10):
            r = client.beta.messages.create(model=MODEL, max_tokens=16000, system=SYSTEM, tools=schemas,
                                            messages=messages, output_config={"effort": "low"}, **request_options())
            messages.append({"role": "assistant", "content": r.content})
            calls = [b for b in r.content if b.type == "tool_use"]
            if not calls:
                break
            results = []
            for c in calls:
                try:
                    results.append({"type": "tool_result", "tool_use_id": c.id, "content": tools[c.name](**c.input)})
                except Exception as exc:
                    results.append({"type": "tool_result", "tool_use_id": c.id, "content": str(exc), "is_error": True})
            messages.append({"role": "user", "content": results})
        answer = "".join(b.text for b in r.content if b.type == "text").strip()
        with lock:
            task = TASKS[task_id]
            if task["status"]["state"] == "TASK_STATE_CANCELED":
                return
            if answer.startswith("NEED_INPUT:"):
                question = answer.removeprefix("NEED_INPUT:").strip()
                task["status"] = {"state": "TASK_STATE_INPUT_REQUIRED", "timestamp": now(),
                                  "message": text_message("ROLE_AGENT", question, task)}
            else:
                task["artifacts"] = [{"artifactId": str(uuid.uuid4()), "name": "answer", "parts": [{"text": answer}]}]
                task["status"] = {"state": "TASK_STATE_COMPLETED", "timestamp": now()}
    except Exception as exc:  # report failure through the protocol, not as a crashed connection
        with lock:
            TASKS[task_id]["status"] = {"state": "TASK_STATE_FAILED", "timestamp": now(),
                                        "message": text_message("ROLE_AGENT", f"Internal error: {exc}", TASKS[task_id])}


# --------------------------------------------------------------------------- JSON-RPC methods

class A2AError(Exception):
    def __init__(self, code: int, message: str, http: int = 400):
        super().__init__(message)
        self.code, self.message, self.http = code, message, http


def send_message(params: dict) -> dict:
    msg = params["message"]
    text = " ".join(p["text"] for p in msg.get("parts", []) if "text" in p)
    with lock:
        if msg.get("taskId"):  # a follow-up to a task that asked for input
            task = TASKS.get(msg["taskId"])
            if task is None:
                raise A2AError(-32001, f"Task {msg['taskId']} not found", 404)
            if task["status"]["state"] != "TASK_STATE_INPUT_REQUIRED":
                raise A2AError(-32004, "This task is not waiting for input")
            HISTORY[task["id"]].append({"role": "user", "content": text})
        else:
            task = {"id": str(uuid.uuid4()), "contextId": msg.get("contextId") or str(uuid.uuid4()), "artifacts": []}
            TASKS[task["id"]], HISTORY[task["id"]] = task, [{"role": "user", "content": text}]
        task["status"] = {"state": "TASK_STATE_WORKING", "timestamp": now()}

    if params.get("configuration", {}).get("returnImmediately"):
        threading.Thread(target=run_agent, args=(task["id"],), daemon=True).start()
    else:
        run_agent(task["id"])  # default: block until the task completes or needs input
    with lock:
        return {"task": json.loads(json.dumps(TASKS[task["id"]]))}


def get_task(params: dict) -> dict:
    with lock:
        task = TASKS.get(params["id"])
        if task is None:
            raise A2AError(-32001, f"Task {params['id']} not found", 404)
        return json.loads(json.dumps(task))


def cancel_task(params: dict) -> dict:
    with lock:
        task = TASKS.get(params["id"])
        if task is None:
            raise A2AError(-32001, f"Task {params['id']} not found", 404)
        if task["status"]["state"] in ("TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_CANCELED"):
            raise A2AError(-32002, "Task is already in a terminal state")
        task["status"] = {"state": "TASK_STATE_CANCELED", "timestamp": now()}
        return json.loads(json.dumps(task))


METHODS = {"SendMessage": send_message, "GetTask": get_task, "CancelTask": cancel_task}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/agent-card.json":
            host = self.headers.get("Host", f"127.0.0.1:{self.server.server_port}")
            return self._send(200, agent_card(f"http://{host}"))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            if self.headers.get("A2A-Version", VERSION) != VERSION:
                raise A2AError(-32009, f"A2A version {self.headers.get('A2A-Version')} not supported; use {VERSION}")
            method = METHODS.get(body.get("method"))
            if method is None:
                raise A2AError(-32601, f"Method not found: {body.get('method')}", 404)
            self._send(200, {"jsonrpc": "2.0", "id": body.get("id"), "result": method(body.get("params") or {})})
        except A2AError as e:
            self._send(e.http, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": e.code, "message": e.message}})

    def _send(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9001)
    port = parser.parse_args().port
    print(f"A2A agent on http://127.0.0.1:{port}  (card: /.well-known/agent-card.json)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
