"""The same fictional CRM as 04-tools (fixed seed, so the data is identical), exposed as two JSON tools."""

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
BY_ID = {c.short_id: c for c in CUSTOMERS}


def list_customers(city: str) -> str:
    """IDs and names of every customer in one city."""
    return json.dumps([{"customer_id": c.short_id, "name": c.name} for c in CUSTOMERS if c.city.lower() == city.lower()])


def get_customer(customer_id: str) -> str:
    """One customer's profile, total spend and open tickets."""
    c = BY_ID.get(customer_id)
    if c is None:
        return json.dumps({"error": f"unknown customer_id {customer_id!r}; ids look like 'C-1042'"})
    return json.dumps({"customer_id": c.short_id, "name": c.name, "city": c.city, "plan": c.plan, "email": c.email,
                       "total_spend_usd": sum(o["amount_usd"] for o in c.orders), "order_count": len(c.orders),
                       "open_tickets": [t["subject"] for t in c.tickets if t["status"] == "open"]})


TOOLS = {"list_customers": list_customers, "get_customer": get_customer}
SCHEMAS = [
    {"name": "list_customers",
     "description": "List every customer in a city. Returns a JSON array of {customer_id, name}.",
     "input_schema": {"type": "object", "properties": {"city": {"type": "string", "description": "e.g. 'Lisbon'"}},
                      "required": ["city"], "additionalProperties": False}},
    {"name": "get_customer",
     "description": "Get one customer's profile as JSON: customer_id, name, city, plan, email, total_spend_usd, "
                    "order_count, open_tickets (list of subjects).",
     "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string", "description": "e.g. 'C-1042'"}},
                      "required": ["customer_id"], "additionalProperties": False}},
]
