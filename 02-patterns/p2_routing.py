"""Pattern 2 - Routing: classify first, then hand off to a specialist prompt.

classify  ->  billing specialist | technical specialist | general specialist
"""

import asyncio
import sys
from typing import Literal

from pydantic import BaseModel

from common import ask, meter
from tickets import POLICY, TICKETS


class Route(BaseModel):
    category: Literal["billing", "technical", "general"]
    reason: str


# Each specialist gets a narrow prompt. Narrow prompts are easier to write, test and improve.
SPECIALISTS = {
    "billing": "You are a billing specialist. Confirm amounts and invoice numbers back to the customer.",
    "technical": "You are a support engineer. Check the known issues first; give the workaround as numbered steps.",
    "general": "You are a friendly product guide. Answer in plain language with one concrete next step.",
}


async def handle(ticket: str) -> str:
    # The classifier is a small, cheap call: low effort, structured output, no policy needed.
    route = await ask(f"Classify this support ticket.\n\n{ticket}", schema=Route)
    print(f"[router] -> {route.category} ({route.reason})")

    return await ask(
        ticket,
        system=f"{SPECIALISTS[route.category]}\n\nPolicy:\n{POLICY}",
        effort="medium",
    )


async def main() -> None:
    ticket = TICKETS[sys.argv[1] if len(sys.argv) > 1 else "bug"]
    print(await handle(ticket))
    meter.report("routing")


if __name__ == "__main__":
    asyncio.run(main())
