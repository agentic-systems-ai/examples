"""Pattern 3 - Parallelization, in its two forms.

Sectioning: independent checks run at the same time, then code combines them.
Voting:     the same question asked several times; the majority answer wins.
"""

import asyncio
import sys
from collections import Counter
from typing import Literal

from pydantic import BaseModel

from common import ask, meter
from tickets import POLICY, TICKETS

DRAFT = (
    "Hi Marco, sorry about the export trouble! This is a known issue with large workspaces and our engineers "
    "will have it fixed by Friday. In the meantime, try exporting by date range. - The Larkspur team"
)


class Check(BaseModel):
    passed: bool
    issue: str


class Urgency(BaseModel):
    level: Literal["low", "normal", "urgent"]


REVIEWERS = {
    "policy": "Does the reply break any rule in the policy? Quote the rule if so.",
    "tone": "Is the reply warm, direct and under 150 words?",
    "privacy": "Does the reply ask for or reveal passwords, card numbers or other sensitive data?",
}


async def review_in_sections(reply: str) -> dict[str, Check]:
    async def review(focus: str) -> Check:
        return await ask(f"Policy:\n{POLICY}\n\nReply to review:\n{reply}\n\n{focus}", schema=Check)

    results = await asyncio.gather(*(review(focus) for focus in REVIEWERS.values()))
    return dict(zip(REVIEWERS, results))


async def vote_on_urgency(ticket: str, voters: int = 3) -> str:
    prompt = f"How urgent is this ticket for the support team?\n\n{ticket}"
    votes = await asyncio.gather(*(ask(prompt, schema=Urgency) for _ in range(voters)))
    tally = Counter(vote.level for vote in votes)
    print(f"[voting] {dict(tally)}")
    return tally.most_common(1)[0][0]


async def main() -> None:
    ticket = TICKETS[sys.argv[1] if len(sys.argv) > 1 else "bug"]

    checks, urgency = await asyncio.gather(review_in_sections(DRAFT), vote_on_urgency(ticket))
    for name, check in checks.items():
        print(f"[{name}] {'PASS' if check.passed else 'FAIL'} {check.issue}")
    print(f"urgency: {urgency}")
    meter.report("parallelization")


if __name__ == "__main__":
    asyncio.run(main())
