"""Run a small eval suite with repeated, isolated trials and report pass@k and pass^k.

Companion code for https://www.agenticsystems.ai/blog/evals-for-agents/
Usage:  python suite.py --trials 5                  # runs 6 tasks x 5 trials, saves results.json
        python suite.py --from results.json         # recompute the metrics without calling the API

The agent and tasks are the "agent-shaped" CRM tools and questions from 04-tools. Each trial starts from a
fresh conversation (isolation), and a code-based grader checks the final answer (outcome, not path).
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic

import crm
from metrics import report

MODEL = "claude-opus-5-5"
MAX_STEPS = 12
client = anthropic.Anthropic()
SYSTEM = "You answer questions about Larkspur's customers using the CRM tools. Give a short, specific final answer."

C = crm.BY_SHORT


def spend(c):
    return sum(o["amount_usd"] for o in c.orders)


TASKS = {
    "spend":   (f"How much has {C['C-1003'].name} spent with us in total?", [str(spend(C["C-1003"]))]),
    "plan":    (f"Which plan is {C['C-1058'].name} on, and which city are they in?", [C["C-1058"].plan, C["C-1058"].city]),
    "tickets": (f"How many open support tickets does {C['C-1005'].name} have?",
                [str(sum(t["status"] == "open" for t in C["C-1005"].tickets))]),
    "compare": (f"Who has spent more: {C['C-1058'].name} or {C['C-1008'].name}? By how much?",
                [max((C["C-1058"], C["C-1008"]), key=spend).name, str(abs(spend(C["C-1058"]) - spend(C["C-1008"])))]),
    "email":   (f"The customer with email {C['C-1002'].email} wrote in. How many open tickets do they have?",
                [str(sum(t["status"] == "open" for t in C["C-1002"].tickets))]),
    "orders":  (f"How many orders has {C['C-1004'].name} placed?", [str(len(C["C-1004"].orders))]),
}


def grade(answer: str, expected: list[str]) -> bool:
    flat = re.sub(r"(?<=\d),(?=\d)|\$", "", answer).lower()
    return all(re.search(rf"(?<![\w-]){re.escape(e.lower())}(?![\w-])", flat) for e in expected)


def trial(question: str) -> str:
    """One isolated trial: a brand-new conversation, nothing shared with other trials."""
    tools, schemas = crm.TOOLSETS["v2"]
    messages = [{"role": "user", "content": question}]
    for _ in range(MAX_STEPS):
        r = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=schemas, messages=messages,
            output_config={"effort": "low"}, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        messages.append({"role": "assistant", "content": r.content})
        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls or r.stop_reason in ("refusal", "max_tokens"):
            return "".join(b.text for b in r.content if b.type == "text")
        results = []
        for c in calls:
            try:
                out, err = tools[c.name](**c.input), False
            except Exception as exc:
                out, err = f"{type(exc).__name__}: {exc}", True
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": err})
        messages.append({"role": "user", "content": results})
    return "[step limit]"


def run_suite(trials: int) -> dict:
    jobs = [(name, i) for name in TASKS for i in range(trials)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        answers = list(pool.map(lambda job: trial(TASKS[job[0]][0]), jobs))
    results: dict = {name: {"outcomes": [], "answers": []} for name in TASKS}
    for (name, _), answer in zip(jobs, answers):
        results[name]["outcomes"].append(grade(answer, TASKS[name][1]))
        results[name]["answers"].append(answer.strip()[:200])
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--from", dest="from_file")
    args = parser.parse_args()

    if args.from_file:
        results = json.loads(open(args.from_file).read())
    else:
        results = run_suite(args.trials)
        with open("results.json", "w") as f:
            json.dump(results, f, indent=1)
        print("saved results.json (read the answers in it - especially the failures)\n")

    for name, r in results.items():
        print(f"{name:>8}: {''.join('✓' if o else '✗' for o in r['outcomes'])}")
    print()
    report({name: r["outcomes"] for name, r in results.items()})
