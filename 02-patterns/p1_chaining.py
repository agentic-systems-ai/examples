"""Pattern 1 - Prompt chaining: fixed steps, each feeding the next, with a code gate in between.

extract facts  ->  [gate: is anything missing?]  ->  draft reply
"""

import asyncio
import sys

from pydantic import BaseModel

from common import ask, meter
from tickets import POLICY, TICKETS


class Facts(BaseModel):
    category: str
    customer_name: str
    invoice_number: str | None
    amount_usd: float | None
    request: str


async def handle(ticket: str) -> str:
    # Step 1: turn free text into structured facts.
    facts = await ask(f"Extract the key facts from this support ticket.\n\n{ticket}", schema=Facts)
    print(f"[step 1] facts: {facts.model_dump()}")

    # Gate: plain code, no model. Chains are easy to test because you can check between steps.
    if facts.category.lower() == "billing" and not facts.invoice_number:
        return f"Hi {facts.customer_name}, could you send the invoice number so we can look into this?"

    # Step 2: draft the reply from the facts and the policy, not from the raw ticket.
    return await ask(
        f"Facts: {facts.model_dump_json()}\n\nWrite the reply to the customer.",
        system=f"You write customer support replies. Follow this policy exactly:\n\n{POLICY}",
        effort="medium",
    )


async def main() -> None:
    ticket = TICKETS[sys.argv[1] if len(sys.argv) > 1 else "billing"]
    print(await handle(ticket))
    meter.report("prompt chaining")


if __name__ == "__main__":
    asyncio.run(main())
