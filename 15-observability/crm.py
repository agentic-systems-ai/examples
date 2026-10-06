"""A small fictional CRM, plus two tool sets over the same data.

v1 "API wrapper": mirrors a typical REST API - list everything, look up by UUID, raw JSON, raw errors.
v2 "agent-shaped": search instead of list, readable IDs, concise-by-default responses, errors that say what to do.
"""

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


class ToolError(Exception):
    """Raised by v2 tools with a message written for the model: what went wrong and what to do next."""


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
BY_UUID = {c.uuid: c for c in CUSTOMERS}
BY_SHORT = {c.short_id: c for c in CUSTOMERS}


# --------------------------------------------------------------------------- v1: API wrapper

def v1_list_customers() -> str:
    return json.dumps([{"uuid": c.uuid, "name": c.name, "email": c.email, "city": c.city, "plan": c.plan}
                       for c in CUSTOMERS])


def v1_get_orders(customer_uuid: str) -> str:
    return json.dumps(BY_UUID[customer_uuid].orders)  # a bad ID surfaces as a bare KeyError


def v1_get_tickets(customer_uuid: str) -> str:
    return json.dumps(BY_UUID[customer_uuid].tickets)


V1_TOOLS = {"list_customers": v1_list_customers, "get_orders": v1_get_orders, "get_tickets": v1_get_tickets}
V1_SCHEMAS = [
    {"name": "list_customers", "description": "List customers.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_orders", "description": "Get orders.",
     "input_schema": {"type": "object", "properties": {"customer_uuid": {"type": "string"}},
                      "required": ["customer_uuid"], "additionalProperties": False}},
    {"name": "get_tickets", "description": "Get tickets.",
     "input_schema": {"type": "object", "properties": {"customer_uuid": {"type": "string"}},
                      "required": ["customer_uuid"], "additionalProperties": False}},
]


# --------------------------------------------------------------------------- v2: agent-shaped

def v2_search_customers(query: str, city: str | None = None, limit: int = 5) -> str:
    words = query.lower().split()
    hits = [c for c in CUSTOMERS
            if all(w in f"{c.name} {c.email}".lower() for w in words) and (not city or c.city.lower() == city.lower())]
    if not hits:
        raise ToolError(f"No customers match {query!r}" + (f" in {city}" if city else "") +
                        ". Try fewer words (e.g. one distinctive word of the name), or drop the city filter.")
    lines = [f"{c.short_id} | {c.name} | {c.city} | {c.plan}" for c in hits[:limit]]
    more = f"\n({len(hits) - limit} more matches - refine the query or raise limit)" if len(hits) > limit else ""
    return "\n".join(lines) + more


def v2_get_customer_context(customer_id: str, response_format: str = "concise") -> str:
    c = BY_SHORT.get(customer_id.strip().upper())
    if c is None:
        raise ToolError(f"Unknown customer_id {customer_id!r}. IDs look like 'C-1042'; "
                        "use search_customers to find one by name.")
    open_tickets = [t["subject"] for t in c.tickets if t["status"] == "open"]
    summary = (f"{c.short_id} {c.name} ({c.city}, {c.plan} plan, {c.email})\n"
               f"Orders: {len(c.orders)}, total ${sum(o['amount_usd'] for o in c.orders):,}\n"
               f"Open tickets: {len(open_tickets)}" + (f" - {'; '.join(open_tickets)}" if open_tickets else ""))
    if response_format == "detailed":
        summary += "\n\n" + json.dumps(asdict(c), indent=1)
    return summary


V2_TOOLS = {"search_customers": v2_search_customers, "get_customer_context": v2_get_customer_context}
V2_SCHEMAS = [
    {"name": "search_customers",
     "description": "Find customers by words in their name or email, optionally within one city. Returns up to "
                    "`limit` lines of 'customer_id | name | city | plan'. Use the customer_id with get_customer_context.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Words from the customer's name or email, e.g. 'bluebird dental'"},
         "city": {"type": "string", "description": "Optional exact city filter, e.g. 'Lisbon'"},
         "limit": {"type": "integer", "description": "Max results, default 5"}},
         "required": ["query"], "additionalProperties": False}},
    {"name": "get_customer_context",
     "description": "Everything about one customer in a few lines: contact, plan, order count and total spend, "
                    "open tickets. Use response_format='detailed' only if you need individual orders or tickets.",
     "input_schema": {"type": "object", "properties": {
         "customer_id": {"type": "string", "description": "ID from search_customers, e.g. 'C-1042'"},
         "response_format": {"type": "string", "enum": ["concise", "detailed"]}},
         "required": ["customer_id"], "additionalProperties": False}},
]

TOOLSETS = {"v1": (V1_TOOLS, V1_SCHEMAS), "v2": (V2_TOOLS, V2_SCHEMAS)}
