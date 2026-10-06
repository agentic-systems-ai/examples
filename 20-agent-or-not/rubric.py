"""Should this be an agent? A six-question rubric that recommends the simplest approach that will work.

Companion code for https://www.agenticsystems.ai/blog/should-this-be-an-agent/
Usage:  python rubric.py                 # worked examples
        python rubric.py --interactive   # answer the questions for your own use case

No API calls. The same logic powers the interactive version in the post.
"""

import argparse
from dataclasses import dataclass

QUESTIONS = {
    "path":    ("Can you write down the steps in advance?",
                {"yes": "Yes, the steps are known", "mostly": "Mostly, with a few branches", "no": "No, they depend on what's found along the way"}),
    "check":   ("Can the result be checked automatically?",
                {"yes": "Yes: tests, validation rules, a known answer", "partly": "Partly, or by a quick human look", "no": "No, only an expert can judge it"}),
    "harm":    ("What does a mistake cost, and can it be undone?",
                {"low": "Low and easily undone", "medium": "Noticeable, but recoverable", "high": "Serious or irreversible"}),
    "volume":  ("How many tasks, and how fast must each one finish?",
                {"low": "Tens to hundreds a day; minutes are fine", "medium": "Thousands a day; seconds matter", "high": "Huge volume; sub-second latency"}),
    "value":   ("How much is one completed task worth?",
                {"high": "A lot: hours of skilled work", "medium": "Some: minutes of work", "low": "Very little per task"}),
    "exposure": ("How many of these apply: reads untrusted content, touches private data, can send or act externally?",
                 {"0-1": "At most one", "2": "Two of the three", "3": "All three (the lethal trifecta)"}),
}


@dataclass
class Recommendation:
    level: str
    why: list[str]
    conditions: list[str]


def recommend(a: dict[str, str]) -> Recommendation:
    why, cond = [], []
    if a["exposure"] == "3":
        cond.append("All three trifecta conditions apply: use a secure design pattern and code-level egress controls (post #10).")
    elif a["exposure"] == "2":
        cond.append("Two of the trifecta conditions apply: make sure the third can never be added by accident.")

    if a["path"] == "yes":
        level = "Single call or workflow"
        why.append("The steps are known, so code should control the sequence (post #2). Agents add cost and variance here.")
        if a["volume"] == "high":
            why.append("At high volume and low latency, prefer a single call or rules where possible, and a small model (post #16).")
        return Recommendation(level, why, cond)

    if a["check"] == "no" and a["harm"] == "high":
        return Recommendation(
            "Not yet: keep a person doing it, with an assistant",
            ["Nobody can check the result automatically and mistakes are serious, so autonomy would be a bet you can't monitor.",
             "Use an assistant that drafts and explains, with a person deciding."],
            cond)

    if a["volume"] == "high" or a["value"] == "low":
        why.append("The path varies, but per-task value or latency can't support an agent's cost (post #18). "
                   "Try a workflow with one agentic step in the middle, where the variation really is.")
        return Recommendation("Workflow with a small agentic step", why, cond)

    level = "Agent"
    if a["path"] == "mostly":
        why.append("The path is mostly known: route the common cases through a workflow and hand only the cases that "
                   "branch unpredictably to the agent (post #2).")
    else:
        why.append("The path depends on what's found along the way, which is what agents are for (post #1).")
    if a["check"] == "yes":
        why.append("The result can be checked automatically, so let the harness decide when it's done (post #11).")
    else:
        cond.append("Results can't be fully checked automatically: add a human review step before anything goes out (post #22).")
    if a["harm"] != "low":
        cond.append("Mistakes cost something: require approval for consequential actions and keep everything reversible where possible.")
    if a["path"] == "no" and a["value"] == "high":
        why.append("High value per task justifies the extra model calls; consider sub-agents if the work splits cleanly (post #7).")
    return Recommendation(level + (" with human approval" if a["harm"] == "high" or a["check"] == "no" else " with guardrails"),
                          why, cond)


EXAMPLES = {
    "Extract fields from invoices into the ERP": {"path": "yes", "check": "yes", "harm": "medium", "volume": "medium", "value": "low", "exposure": "2"},
    "Answer customer support tickets": {"path": "mostly", "check": "partly", "harm": "medium", "volume": "medium", "value": "medium", "exposure": "3"},
    "Fix failing tests in our codebase": {"path": "no", "check": "yes", "harm": "medium", "volume": "low", "value": "high", "exposure": "2"},
    "Market research brief for a new product": {"path": "no", "check": "partly", "harm": "low", "volume": "low", "value": "high", "exposure": "2"},
    "Approve or deny insurance claims": {"path": "mostly", "check": "no", "harm": "high", "volume": "medium", "value": "medium", "exposure": "2"},
    "Classify app-store reviews in real time": {"path": "yes", "check": "partly", "harm": "low", "volume": "high", "value": "low", "exposure": "0-1"},
}


def show(name: str, answers: dict[str, str]) -> None:
    r = recommend(answers)
    print(f"\n## {name}\n   -> {r.level}")
    for line in r.why:
        print(f"      why: {line}")
    for line in r.conditions:
        print(f"      condition: {line}")


def interactive() -> None:
    answers = {}
    for key, (question, options) in QUESTIONS.items():
        print(f"\n{question}")
        keys = list(options)
        for i, k in enumerate(keys, 1):
            print(f"  {i}. {options[k]}")
        answers[key] = keys[int(input("> ")) - 1]
    show("Your use case", answers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    if parser.parse_args().interactive:
        interactive()
    else:
        for name, answers in EXAMPLES.items():
            show(name, answers)
