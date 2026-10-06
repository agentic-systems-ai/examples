"""Pattern 5 - Evaluator-optimizer: one call writes, another grades against explicit criteria, repeat until it passes.

draft  ->  evaluate  ->  (fail) revise with feedback  ->  evaluate ...  ->  (pass) done
"""

import asyncio
import sys

from pydantic import BaseModel

from common import ask, meter
from tickets import POLICY, TICKETS

MAX_ROUNDS = 3  # the loop must end even if the evaluator is never satisfied

RUBRIC = """\
1. Follows every rule in the policy (no fix dates beyond "the next release", no refunds for unused time).
2. Answers every question the customer asked.
3. At most 150 words, signed "The Larkspur team".
"""


class Verdict(BaseModel):
    passed: bool
    feedback: str


async def handle(ticket: str) -> str:
    writer = f"You write customer support replies. Policy:\n{POLICY}"
    reply = await ask(f"Write the reply to this ticket:\n\n{ticket}", system=writer)

    for round_ in range(1, MAX_ROUNDS + 1):
        verdict = await ask(
            f"Policy:\n{POLICY}\n\nRubric:\n{RUBRIC}\nTicket:\n{ticket}\n\nReply:\n{reply}\n\n"
            "Grade the reply strictly against the rubric. If it fails, say exactly what to change.",
            schema=Verdict,
            effort="medium",  # judging needs more care than drafting
        )
        print(f"[round {round_}] {'PASS' if verdict.passed else 'FAIL'}: {verdict.feedback}")
        if verdict.passed:
            return reply
        if round_ == MAX_ROUNDS:
            break  # don't spend a rewrite nobody will grade
        reply = await ask(
            f"Ticket:\n{ticket}\n\nYour previous reply:\n{reply}\n\nReviewer feedback:\n{verdict.feedback}\n\n"
            "Rewrite the reply to address the feedback.",
            system=writer,
        )

    return reply  # still failing after MAX_ROUNDS; in production, flag it for a human


async def main() -> None:
    ticket = TICKETS[sys.argv[1] if len(sys.argv) > 1 else "mixed"]
    print(await handle(ticket))
    meter.report("evaluator-optimizer")


if __name__ == "__main__":
    asyncio.run(main())
