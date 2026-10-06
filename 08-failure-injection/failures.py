"""Reproduce three multi-agent failure modes from the MAST taxonomy, and fix each one.

Companion code for https://www.agenticsystems.ai/blog/why-multi-agent-systems-fail/
Usage:  python failures.py --scenario termination  --variant broken|fixed
        python failures.py --scenario withholding  --variant broken|fixed
        python failures.py --scenario verification --variant broken|fixed

Every scenario is graded by plain code, so "it worked" means something.
"""

import argparse
import json

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"
client = anthropic.Anthropic()


def ask(prompt: str, system: str = "", schema: type[BaseModel] | None = None, tools: list | None = None,
        messages: list | None = None):
    """One model call. Returns parsed output, text, or the raw response when tools are involved."""
    kwargs = dict(model=MODEL, max_tokens=16000, output_config={"effort": "low"},
                  messages=messages or [{"role": "user", "content": prompt}],
                  betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
        return client.beta.messages.create(**kwargs)
    if schema:
        return client.beta.messages.parse(output_format=schema, **kwargs).parsed_output
    r = client.beta.messages.create(**kwargs)
    return "".join(b.text for b in r.content if b.type == "text")


# --------------------------------------------------------------------------- 1. termination (FM-1.5)

class Review(BaseModel):
    approved: bool
    feedback: str


def termination(variant: str) -> bool:
    """A writer and a reviewer pass a product blurb back and forth.

    broken: the reviewer is asked to improve the text, with no criteria for "done", so it never says done.
    fixed:  the reviewer gets explicit acceptance criteria and must approve once they are met.
    """
    spec = "A product blurb for Larkspur's CSV export feature: at most 40 words, mentions date-range exports."
    criteria = "1) at most 40 words; 2) mentions exporting by date range; 3) no promises about future features."
    text = ask(f"Write this: {spec}")
    max_rounds = 6

    for round_ in range(1, max_rounds + 1):
        if variant == "broken":
            review = ask(f"Review this blurb and suggest improvements:\n\n{text}", schema=Review)
        else:
            review = ask(f"Acceptance criteria:\n{criteria}\n\nBlurb:\n{text}\n\nApprove if and only if every "
                         "criterion is met. Do not ask for stylistic changes beyond the criteria.", schema=Review)
        print(f"  round {round_}: {'APPROVED' if review.approved else 'changes requested'} - {review.feedback[:90]}")
        if review.approved:
            break
        text = ask(f"Revise the blurb.\nSpec: {spec}\nFeedback: {review.feedback}\n\nBlurb:\n{text}")

    words = len(text.split())
    ok = review.approved and words <= 40
    rounds = f"{round_} round{'s' if round_ > 1 else ''}"
    print(f"  -> {rounds}, {words} words, {'terminated with an approved blurb' if ok else 'ran out of rounds or broke the spec'}")
    return ok


# --------------------------------------------------------------------------- 2. information withholding (FM-2.4)

REQUEST = ("Please create an account for Ana Costa, email Ana.Costa@Example.org. Note: our identity system requires "
           "the username to be the email address in all lowercase, or the account will not sync.")

ACCOUNT_TOOL = {"name": "create_account", "description": "Create a user account.",
                "input_schema": {"type": "object", "properties": {
                    "username": {"type": "string"}, "display_name": {"type": "string"}},
                    "required": ["username", "display_name"], "additionalProperties": False}}


class Brief(BaseModel):
    task: str


class FullBrief(BaseModel):
    task: str
    constraints: list[str]
    original_request: str


def withholding(variant: str) -> bool:
    """A lead agent hands a task to a worker agent that owns the create_account tool.

    broken: the hand-off format is a terse one-line task (a common pattern: "keep briefs short").
    fixed:  the hand-off carries explicit constraints and the original request verbatim.
    """
    if variant == "broken":
        brief = ask(f"Write a one-line task (at most 12 words) for a worker agent:\n\n{REQUEST}", schema=Brief)
        handoff = brief.task
    else:
        brief = ask("Write a hand-off for a worker agent. List every constraint stated in the request, and copy the "
                    f"request verbatim.\n\n{REQUEST}", schema=FullBrief)
        handoff = (f"Task: {brief.task}\nConstraints:\n" + "\n".join(f"- {c}" for c in brief.constraints)
                   + f"\nOriginal request: {brief.original_request}")
    print(f"  hand-off: {handoff!r}")

    r = ask("", messages=[{"role": "user", "content": handoff}], tools=[ACCOUNT_TOOL])
    call = next((b for b in r.content if b.type == "tool_use"), None)
    username = call.input["username"] if call else None
    ok = username == "ana.costa@example.org"
    print(f"  -> worker created username {username!r}: {'correct' if ok else 'violates the identity-system rule'}")
    return ok


# --------------------------------------------------------------------------- 3. verification (FM-3.2 / 3.3)

ORDERS = [("INV-301", 49), ("INV-302", 199), ("INV-303", 12), ("INV-304", 588), ("INV-305", 49), ("INV-306", 199),
          ("INV-307", 49), ("INV-308", 12), ("INV-309", 588), ("INV-310", 49), ("INV-311", 199), ("INV-312", 12)]


class Verdict(BaseModel):
    approved: bool
    recomputed_total: int | None
    reason: str


def faulty_worker() -> dict:
    """Injected fault: a worker that silently skips one row. This is how you test a verifier."""
    rows = ORDERS[:7] + ORDERS[8:]
    return {"answer": f"The total of all {len(ORDERS)} invoices is ${sum(a for _, a in rows):,}.",
            "total": sum(a for _, a in rows)}


def verification(variant: str) -> bool:
    """A verifier agent checks a worker's answer before it goes to the user.

    broken: the verifier sees only the answer and checks that it looks reasonable (the superficial check
            the MAST paper found was common, e.g. "the code compiles").
    fixed:  the verifier gets the source data and must recompute the result independently.
    """
    work = faulty_worker()
    true_total = sum(a for _, a in ORDERS)
    print(f"  worker says: {work['answer']}  (true total: ${true_total:,})")

    if variant == "broken":
        v = ask(f"Check this answer before it is sent to the user. Is it clear, well-formatted and plausible?\n\n"
                f"{work['answer']}", schema=Verdict)
    else:
        table = "\n".join(f"{inv},{amt}" for inv, amt in ORDERS)
        v = ask(f"Source data (invoice,amount_usd):\n{table}\n\nClaimed answer: {work['answer']}\n\nRecompute the "
                "total yourself from the source data, row by row. Approve only if the claimed total is exactly right.",
                schema=Verdict)

    caught = not v.approved
    print(f"  -> verifier {'REJECTED' if caught else 'approved'} it (recomputed: {v.recomputed_total}) - {v.reason[:90]}")
    return caught


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["termination", "withholding", "verification"], required=True)
    parser.add_argument("--variant", choices=["broken", "fixed"], required=True)
    args = parser.parse_args()

    print(f"{args.scenario} / {args.variant}")
    ok = {"termination": termination, "withholding": withholding, "verification": verification}[args.scenario](args.variant)
    print(f"\n=== {'PASS' if ok else 'FAIL'}: {args.scenario} ({args.variant})")
