"""The agent loop from first principles: a model, three tools, and a while loop.

Companion code for https://www.agenticsystems.ai/blog/the-agent-loop/
Usage:  python agent.py "Which region had the highest Q3 revenue, and by how much?"
"""

import json
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
MAX_STEPS = 10  # hard stop: an agent must always be able to terminate
WORKSPACE = Path(__file__).parent / "workspace"

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# 1. Tools: plain functions plus a schema the model can read.
# ---------------------------------------------------------------------------


def list_files() -> str:
    return "\n".join(sorted(p.name for p in WORKSPACE.iterdir() if p.is_file()))


def read_file(name: str) -> str:
    path = (WORKSPACE / name).resolve()
    if path.parent != WORKSPACE.resolve():  # keep the agent inside its sandbox
        raise ValueError(f"{name!r} is outside the workspace")
    return path.read_text(encoding="utf-8")


def calculate(expression: str) -> str:
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        raise ValueError("only arithmetic is allowed")
    return str(eval(expression, {"__builtins__": {}}))  # safe: digits and operators only


TOOLS = {"list_files": list_files, "read_file": read_file, "calculate": calculate}

TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": "List the files available in the workspace. Call this first to see what data exists.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "read_file",
        "description": "Return the full text of one workspace file, by file name as shown by list_files.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "File name, e.g. 'sales.csv'"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "calculate",
        "description": "Evaluate an arithmetic expression exactly. Use this instead of doing math in your head.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. '(120 + 80) / 2'"}},
            "required": ["expression"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

SYSTEM = (
    "You are a data analyst working in a small file workspace. "
    "Use the tools to find and verify facts; do not guess numbers. "
    "When you have the answer, reply with a short final answer and the figures that support it."
)

# ---------------------------------------------------------------------------
# 2. Acting: run each requested tool, and turn failures into observations.
# ---------------------------------------------------------------------------


def run_tool(block) -> dict:
    try:
        output = TOOLS[block.name](**block.input)
        return {"type": "tool_result", "tool_use_id": block.id, "content": output}
    except Exception as exc:  # the model sees the error and can recover
        return {"type": "tool_result", "tool_use_id": block.id, "content": str(exc), "is_error": True}


# ---------------------------------------------------------------------------
# 3. The loop: reason -> act -> observe, until the model stops asking for tools.
# ---------------------------------------------------------------------------


def run_agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]  # this list *is* the agent's state

    for step in range(1, MAX_STEPS + 1):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOL_SCHEMAS,
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # re-run on a recommended model if this one declines
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return "[the model declined this task]"
        if response.stop_reason == "max_tokens":
            return "[response was cut off - raise max_tokens]"

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:  # no more actions requested: the model is done
            return "".join(b.text for b in response.content if b.type == "text")

        results = [run_tool(call) for call in tool_calls]
        for call, result in zip(tool_calls, results):
            flag = "ERROR " if result.get("is_error") else ""
            print(f"[step {step}] {call.name}({json.dumps(call.input)}) -> {flag}{result['content'][:60]!r}")
        messages.append({"role": "user", "content": results})  # all results in one message

    return f"[stopped after {MAX_STEPS} steps without finishing]"


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which region had the highest Q3 revenue, and by how much did it beat the runner-up?"
    print(run_agent(question))
