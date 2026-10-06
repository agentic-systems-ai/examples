"""Talk to a remote A2A agent the way another agent would: discover, delegate, poll, answer follow-ups.

Usage:  python remote_agent.py --port 9001      (in another terminal)
        python client.py
"""

import json
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:9001"


def http(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None,
                                 {"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


class A2AClient:
    def __init__(self, base: str):
        self.card = http("GET", f"{base}/.well-known/agent-card.json")
        iface = next(i for i in self.card["supportedInterfaces"] if i["protocolBinding"] == "JSONRPC")
        self.url, self.version = iface["url"], iface["protocolVersion"]

    def call(self, method: str, params: dict, version: str | None = None) -> dict:
        reply = http("POST", self.url, {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params},
                     {"A2A-Version": version or self.version})
        if "error" in reply:
            raise RuntimeError(f"{reply['error']['code']}: {reply['error']['message']}")
        return reply["result"]

    def send(self, text: str, task: dict | None = None, wait: bool = True) -> dict:
        message = {"role": "ROLE_USER", "parts": [{"text": text}], "messageId": str(uuid.uuid4())}
        if task:  # continue an existing task (e.g. answer its question)
            message |= {"taskId": task["id"], "contextId": task["contextId"]}
        params = {"message": message} | ({} if wait else {"configuration": {"returnImmediately": True}})
        return self.call("SendMessage", params)["task"]

    def wait(self, task: dict, every: float = 1.0) -> dict:
        while task["status"]["state"] in ("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"):
            time.sleep(every)
            task = self.call("GetTask", {"id": task["id"]})
            print(f"     polled: {task['status']['state']}")
        return task


def show(task: dict) -> None:
    status = task["status"]
    print(f"     state: {status['state']}")
    if "message" in status:
        verb = "asks" if status["state"] == "TASK_STATE_INPUT_REQUIRED" else "says"
        print(f"     agent {verb}: {status['message']['parts'][0]['text']}")
    for artifact in task.get("artifacts", []):
        print(f"     artifact: {artifact['parts'][0]['text']}")


if __name__ == "__main__":
    print("1. Discover: read the Agent Card")
    agent = A2AClient(BASE)
    print(f"     {agent.card['name']} - skills: {[s['id'] for s in agent.card['skills']]}")
    print(f"     endpoint {agent.url} ({agent.version})")

    print("2. Delegate a task and wait for the answer (blocking SendMessage)")
    show(agent.send("How much has Riverside Legal spent with us, and are any tickets open?"))

    print("3. Delegate without waiting, then poll (returnImmediately + GetTask)")
    task = agent.send("What plan is Willow Robotics on?", wait=False)
    show(agent.wait(task))

    print("4. An ambiguous request: the agent asks a question instead of guessing")
    task = agent.send("How much has Bluebird spent?")
    show(task)
    if task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED":
        print("     -> answering in the same task")
        show(agent.send("I mean Bluebird Dental.", task=task))

    print("5. Errors are part of the protocol")
    for label, fn in [("unknown task", lambda: agent.call("GetTask", {"id": "no-such-task"})),
                      ("old protocol version", lambda: agent.call("GetTask", {"id": "x"}, version="0.3"))]:
        try:
            fn()
        except RuntimeError as e:
            print(f"     {label}: {e}")
