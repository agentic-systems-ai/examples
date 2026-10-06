"""The CRM from 04-tools (same seed, same data), with one realistic quirk: order amounts come back in cents."""

import json
import random
import uuid
from dataclasses import asdict, dataclass, field

PREFIXES = ["Riverside", "Northwind", "Bluebird", "Copperleaf", "Harbor", "Juniper", "Maple", "Silverline",
            "Granite", "Lakeshore", "Redwood", "Sunrise", "Willow", "Ironbridge", "Cedar", "Brightwater"]
KINDS = ["Bakery", "Dental", "Logistics", "Studio", "Fitness", "Books", "Legal", "Florist", "Cafe", "Robotics",
         "Analytics", "Clinic", "Outfitters", "Garage", "Press"]
CITIES = ["Lisbon", "Austin", "Leeds", "Toronto", "Melbourne", "Denver", "Dublin", "Porto"]
SUBJECTS = ["CSV export fails", "Cannot add teammate", "Invoice question", "Slow dashboard", "SSO login loop",
            "Webhook not firing", "Plan downgrade", "API rate limit"]


@dataclass
class Customer:
    uuid: str
    short_id: str
    name: str
    email: str
    city: str
    plan: str
    orders: list = field(default_factory=list)   # [{"order_uuid", "date", "amount_usd"}]
    tickets: list = field(default_factory=list)  # [{"ticket_uuid", "subject", "status"}]


def build() -> list[Customer]:
    rng = random.Random(42)
    names = rng.sample([f"{p} {k}" for p in PREFIXES for k in KINDS], 240)
    customers = []
    for i, name in enumerate(names):
        c = Customer(
            uuid=str(uuid.UUID(int=rng.getrandbits(128))),
            short_id=f"C-{1001 + i}",
            name=name,
            email=f"ops@{name.lower().replace(' ', '')}.example",
            city=rng.choice(CITIES),
            plan=rng.choice(["Starter", "Team", "Team", "Enterprise"]),
        )
        for _ in range(rng.randint(0, 10)):
            c.orders.append({"order_uuid": str(uuid.UUID(int=rng.getrandbits(128))),
                             "date": f"2026-{rng.randint(1, 8):02d}-{rng.randint(1, 28):02d}",
                             "amount_usd": rng.choice([12, 49, 49, 199, 588])})
        for _ in range(rng.randint(0, 4)):
            c.tickets.append({"ticket_uuid": str(uuid.UUID(int=rng.getrandbits(128))),
                              "subject": rng.choice(SUBJECTS), "status": rng.choice(["open", "closed", "closed"])})
        customers.append(c)
    return customers


CUSTOMERS = build()
BY_NAME = {c.name.lower(): c for c in CUSTOMERS}
BY_ID = {c.short_id: c for c in CUSTOMERS}


def find_customer(name: str) -> str:
    c = BY_NAME.get(name.strip().lower())
    return json.dumps({"customer_id": c.short_id, "name": c.name} if c else {"error": f"no customer named {name!r}"})


def get_orders(customer_id: str) -> str:
    # The quirk: like many payment APIs, amounts are integer minor units (cents), and the field name doesn't say so.
    return json.dumps([{"order_id": o["order_uuid"][:8], "date": o["date"], "amount": o["amount_usd"] * 100}
                       for o in BY_ID[customer_id].orders])


def get_open_tickets(customer_id: str) -> str:
    return json.dumps([t["subject"] for t in BY_ID[customer_id].tickets if t["status"] == "open"])


TOOLS = {"find_customer": find_customer, "get_orders": get_orders, "get_open_tickets": get_open_tickets}
SCHEMAS = [
    {"name": "find_customer", "description": "Look up a customer's ID by exact name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"],
                      "additionalProperties": False}},
    {"name": "get_orders", "description": "List a customer's orders: order_id, date, amount.",
     "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"],
                      "additionalProperties": False}},
    {"name": "get_open_tickets", "description": "List the subjects of a customer's open support tickets.",
     "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"],
                      "additionalProperties": False}},
]
