"""An agent that learns across tasks: act, get feedback, distil a lesson, and read the lessons next time.

Companion code for https://www.agenticsystems.ai/blog/memory-that-learns/
Usage:  python learn.py --memory off      (every task starts from scratch)
        python learn.py --memory on       (lessons persist in memory.json between tasks)
        python learn.py --memory on --reset
"""

import argparse
import json
import re
from pathlib import Path

import anthropic
from pydantic import BaseModel

import crm

MODEL = "claude-opus-5-5"
MAX_STEPS = 12
MEMORY = Path(__file__).parent / "memory.json"
client = anthropic.Anthropic()

SYSTEM = "You answer questions about Larkspur's customers using the CRM tools. End with a short, specific answer."

# A stream of different tasks. Several share a hidden pitfall; none share an answer.
TASKS = [
    ("How much has Riverside Legal spent in total, in dollars?", "1972"),
    ("How many orders has Willow Robotics placed?", "4"),
    ("What is Bluebird Dental's total spend, in dollars?", "1120"),
    ("What was Harbor Analytics' largest single order, in dollars?", "588"),
    ("How many open support tickets does Northwind Garage have?", "2"),
    ("What is the combined spend of Bluebird Books and Bluebird Dental, in dollars?", "2023"),
]


# --------------------------------------------------------------------------- memory: write, manage, read

class Lessons(BaseModel):
    lessons: list[str]


def read_memory() -> list[str]:
    return json.loads(MEMORY.read_text()) if MEMORY.exists() else []


def write_memory(new: list[str]) -> None:
    lessons = read_memory()
    for lesson in new:
        if lesson not in lessons:      # manage: skip exact duplicates
            lessons.append(lesson)
    MEMORY.write_text(json.dumps(lessons[-20:], indent=1))  # manage: keep the store small


def reflect(task: str, transcript: str, answer: str, feedback: str) -> list[str]:
    """Turn one episode into reusable lessons: causal, general, and never the answer itself."""
    out = client.beta.messages.parse(
        model=MODEL, max_tokens=16000, output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content":
            f"Task: {task}\nWhat you did:\n{transcript}\nYour answer: {answer}\nFeedback: {feedback}\n\n"
            "Write at most 2 lessons that would help on FUTURE, DIFFERENT tasks with these tools. Phrase each as a "
            "cause and an action, e.g. 'Tool X returns Y, so do Z'. Never record this task's answer. If nothing "
            "generalizable was learned, return an empty list."}],
        output_format=Lessons,
    )
    return out.parsed_output.lessons


# --------------------------------------------------------------------------- one episode

def run(task: str, lessons: list[str]) -> tuple[str, str, int]:
    system = SYSTEM
    if lessons:  # read: lessons go into the (stable) system prompt for this task
        system += "\n\nLessons from earlier tasks:\n" + "\n".join(f"- {l}" for l in lessons)
    messages, log = [{"role": "user", "content": task}], []
    for step in range(1, MAX_STEPS + 1):
        r = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=system, tools=crm.SCHEMAS, messages=messages,
            output_config={"effort": "low"}, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        messages.append({"role": "assistant", "content": r.content})
        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls or r.stop_reason in ("refusal", "max_tokens"):
            return "".join(b.text for b in r.content if b.type == "text"), "\n".join(log), step
        results = []
        for c in calls:
            out = crm.TOOLS[c.name](**c.input)
            log.append(f"{c.name}({json.dumps(c.input)}) -> {out[:160]}")
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
        messages.append({"role": "user", "content": results})
    return "[step limit]", "\n".join(log), MAX_STEPS


def correct(answer: str, expected: str) -> bool:
    numbers = re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d)", "", answer))
    return any(float(n) == float(expected) for n in numbers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", choices=["on", "off"], default="on")
    parser.add_argument("--reset", action="store_true", help="delete memory.json first")
    args = parser.parse_args()
    if args.reset and MEMORY.exists():
        MEMORY.unlink()

    passed = 0
    for i, (task, expected) in enumerate(TASKS, 1):
        lessons = read_memory() if args.memory == "on" else []
        answer, transcript, steps = run(task, lessons)
        ok = correct(answer, expected)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] task {i} ({steps} steps, {len(lessons)} lessons in memory): {task}"
              f"\n       answer: {answer.strip()[:110]!r}")
        if args.memory == "on":
            feedback = "Correct." if ok else f"Incorrect: the expected answer was {expected}."
            new = reflect(task, transcript, answer, feedback)
            write_memory(new)
            for lesson in new:
                print(f"       + lesson: {lesson}")

    print(f"\n=== memory {args.memory}: {passed}/{len(TASKS)} correct")
