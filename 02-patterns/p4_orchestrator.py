"""Pattern 4 - Orchestrator-workers: a model decides the subtasks at run time, workers do them, then it combines.

plan subtasks  ->  worker, worker, worker (in parallel)  ->  synthesize one reply
"""

import asyncio
import sys

from pydantic import BaseModel

from common import ask, meter
from tickets import POLICY, TICKETS


class Subtask(BaseModel):
    question: str
    focus: str


class Plan(BaseModel):
    subtasks: list[Subtask]


async def handle(ticket: str) -> str:
    # The orchestrator decides how many pieces of work there are. Code could not know this in advance.
    plan = await ask(
        f"Split this ticket into independent questions, one per issue the customer raised.\n\n{ticket}",
        schema=Plan,
        effort="medium",
    )
    print(f"[orchestrator] {len(plan.subtasks)} subtasks: {[s.focus for s in plan.subtasks]}")

    async def work(subtask: Subtask) -> str:
        return await ask(
            f"Answer only this question, in at most 60 words:\n{subtask.question}",
            system=f"You are a support specialist for {subtask.focus}. Policy:\n{POLICY}",
        )

    answers = await asyncio.gather(*(work(s) for s in plan.subtasks))

    notes = "\n\n".join(f"Q: {s.question}\nA: {a}" for s, a in zip(plan.subtasks, answers))
    return await ask(
        f"Original ticket:\n{ticket}\n\nSpecialist notes:\n{notes}\n\nCombine these into one reply.",
        system=f"You write customer support replies. Follow this policy exactly:\n\n{POLICY}",
        effort="medium",
    )


async def main() -> None:
    ticket = TICKETS[sys.argv[1] if len(sys.argv) > 1 else "mixed"]
    print(await handle(ticket))
    meter.report("orchestrator-workers")


if __name__ == "__main__":
    asyncio.run(main())
