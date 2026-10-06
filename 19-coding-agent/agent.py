"""A small coding agent: explore a repo, find the bug, make a minimal edit, run the tests, stop when they pass.

Companion code for https://www.agenticsystems.ai/blog/inside-a-coding-agent/
Usage:  python agent.py
        LLM_PROVIDER=bedrock python agent.py

Each run copies toyrepo/ to work/ and the agent edits only that copy. Two rules are enforced in code, not in the
prompt: the agent cannot write to tests/, and the task only counts as done if the tests pass AND are unchanged.
"""

import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from provider import make_client, model_id, request_options

HERE = Path(__file__).parent
SOURCE, WORK = HERE / "toyrepo", HERE / "work"
MODEL = model_id("claude-opus-5-5")
MAX_STEPS = 25
client = make_client()

TASK = ("The test suite in this repository is failing. Find the cause and fix it with the smallest correct change "
        "to the source code. Do not modify the tests. Run the tests to confirm the fix before you finish.")
SYSTEM = ("You are a careful software engineer working in a small Python repository. Explore before editing: read "
          "the failing test and the code it exercises. Prefer minimal, targeted edits. Always run the tests after a "
          "change. When the tests pass, reply with a two-sentence summary of the root cause and the fix.")


# --------------------------------------------------------------------------- tools (the agent-computer interface)

def safe_path(path: str) -> Path:
    p = (WORK / path).resolve()
    if WORK.resolve() not in p.parents and p != WORK.resolve():
        raise ValueError(f"{path!r} is outside the repository")
    return p


def list_files(path: str = ".") -> str:
    root = safe_path(path)
    files = [str(p.relative_to(WORK)).replace("\\", "/") for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts]
    return "\n".join(files) or "(no Python files)"


def read_file(path: str) -> str:
    lines = safe_path(path).read_text(encoding="utf-8").splitlines()
    return "\n".join(f"{i:>4}  {line}" for i, line in enumerate(lines, 1))  # numbered, like a code viewer


def search(pattern: str) -> str:
    hits = []
    for p in sorted(WORK.rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(pattern, line):
                hits.append(f"{p.relative_to(WORK).as_posix()}:{i}: {line.strip()}")
    return "\n".join(hits[:50]) or "no matches"


def edit_file(path: str, old: str, new: str) -> str:
    """Replace one exact occurrence of `old` with `new`. Exact matching keeps edits small and reviewable."""
    if path.replace("\\", "/").startswith("tests/"):
        raise PermissionError("Editing tests is not allowed in this task. Fix the source code instead.")
    p = safe_path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise ValueError(f"`old` must match exactly once in {path}; it matched {count} times. Include more context.")
    p.write_text(text.replace(old, new), encoding="utf-8")
    return f"Edited {path}."


def run_tests() -> str:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=WORK,
                       capture_output=True, text=True, timeout=120)
    out = (r.stdout + r.stderr).strip().splitlines()
    return "\n".join(out[-25:])  # the tail holds the summary; long logs would only bloat the context (post #3)


TOOLS = {"list_files": list_files, "read_file": read_file, "search": search, "edit_file": edit_file,
         "run_tests": run_tests}
SCHEMAS = [
    {"name": "list_files", "description": "List Python files under a directory of the repository.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "e.g. '.' or 'invoicing'"}},
                      "additionalProperties": False}},
    {"name": "read_file", "description": "Read a file, with line numbers.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"],
                      "additionalProperties": False}},
    {"name": "search", "description": "Search all Python files for a regular expression; returns file:line: text.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"],
                      "additionalProperties": False}},
    {"name": "edit_file",
     "description": "Replace exactly one occurrence of `old` with `new` in a file. `old` must be copied exactly from "
                    "the file (without line numbers) and match once.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                                       "new": {"type": "string"}},
                      "required": ["path", "old", "new"], "additionalProperties": False}},
    {"name": "run_tests", "description": "Run the test suite and return the last lines of output.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


# --------------------------------------------------------------------------- the loop, and the gate

def tests_digest() -> str:
    return hashlib.sha256(b"".join(p.read_bytes() for p in sorted((WORK / "tests").rglob("*.py")))).hexdigest()


def run() -> dict:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.copytree(SOURCE, WORK)
    before = tests_digest()
    messages, stats = [{"role": "user", "content": TASK}], {"steps": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0}
    summary = "[step limit]"
    for step in range(1, MAX_STEPS + 1):
        r = client.beta.messages.create(model=MODEL, max_tokens=16000, system=SYSTEM, tools=SCHEMAS, messages=messages,
                                        output_config={"effort": "medium"}, cache_control={"type": "ephemeral"},
                                        **request_options())
        u = r.usage
        stats["steps"] = step
        stats["input_tokens"] += u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        stats["output_tokens"] += u.output_tokens
        messages.append({"role": "assistant", "content": r.content})
        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls:
            summary = "".join(b.text for b in r.content if b.type == "text").strip()
            break
        results = []
        for c in calls:
            stats["tool_calls"] += 1
            try:
                out, err = TOOLS[c.name](**c.input), False
            except Exception as exc:
                out, err = f"{type(exc).__name__}: {exc}", True
            short = json.dumps(c.input)[:70]
            print(f"[step {step:>2}] {c.name}({short}) -> {'ERROR ' if err else ''}{out.splitlines()[-1][:60] if out else ''}")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": err})
        messages.append({"role": "user", "content": results})

    final = run_tests()
    passed = "passed" in final and "failed" not in final and "error" not in final.lower()
    unchanged = tests_digest() == before
    return {"summary": summary, "tests_pass": passed, "tests_unchanged": unchanged, **stats}


def diff() -> str:
    out = []
    for p in sorted(SOURCE.rglob("*.py")):
        rel = p.relative_to(SOURCE)
        a, b = p.read_text(encoding="utf-8").splitlines(), (WORK / rel).read_text(encoding="utf-8").splitlines()
        out += difflib.unified_diff(a, b, f"a/{rel.as_posix()}", f"b/{rel.as_posix()}", lineterm="", n=1)
    return "\n".join(out) or "(no changes)"


if __name__ == "__main__":
    result = run()
    print(f"\n{result['summary']}\n\n{diff()}")
    ok = result["tests_pass"] and result["tests_unchanged"]
    print(f"\n=== {'DONE' if ok else 'NOT DONE'}: tests pass={result['tests_pass']}, tests unchanged={result['tests_unchanged']} | "
          f"{result['steps']} steps, {result['tool_calls']} tool calls, {result['input_tokens']:,} input + "
          f"{result['output_tokens']:,} output tokens")
