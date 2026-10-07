"""Historical refund tickets, with what the human team actually decided. Today is 2026-11-02.

The human decisions are realistic, not perfect: two are goodwill exceptions to the written policy, and one is a
mistake. Shadow mode measures agreement with what people did; reading the disagreements is how you find out who
was right.
"""

TODAY = "2026-11-02"

POLICY = """Refund policy (support team, v4):
1. Damaged or defective on arrival, reported within 30 days of delivery: full refund.
2. Never arrived, and no delivery scan 10+ days after the promised date: full refund.
3. Changed mind, item unopened, within 30 days of delivery: refund minus a 10% restocking fee.
4. Changed mind, item opened: no refund (offer an exchange).
5. Escalate to a person, without deciding, if the order total is over $500 or the customer has had 3 or more refunds in the last 90 days.
6. Requests more than 30 days after delivery: deny, unless the item never arrived (rule 2)."""

ORDERS = {
    "A100": {"customer": "c1", "item": "Desk lamp", "total": 49.00, "delivered": "2026-10-20", "promised": "2026-10-18"},
    "A101": {"customer": "c2", "item": "Office chair", "total": 289.00, "delivered": "2026-10-25", "promised": "2026-10-24"},
    "A102": {"customer": "c3", "item": "Standing desk", "total": 640.00, "delivered": "2026-10-28", "promised": "2026-10-27"},
    "A103": {"customer": "c4", "item": "Headphones", "total": 120.00, "delivered": None, "promised": "2026-10-15"},
    "A104": {"customer": "c5", "item": "Keyboard", "total": 85.00, "delivered": "2026-10-30", "promised": "2026-10-30"},
    "A105": {"customer": "c6", "item": "Monitor arm", "total": 70.00, "delivered": "2026-10-12", "promised": "2026-10-10"},
    "A106": {"customer": "c7", "item": "Webcam", "total": 60.00, "delivered": "2026-09-14", "promised": "2026-09-12"},
    "A107": {"customer": "c8", "item": "Bookshelf", "total": 150.00, "delivered": "2026-10-26", "promised": "2026-10-26"},
    "A108": {"customer": "c9", "item": "Phone stand", "total": 25.00, "delivered": "2026-10-29", "promised": "2026-10-29"},
    "A109": {"customer": "c10", "item": "Ergonomic mouse", "total": 45.00, "delivered": "2026-10-01", "promised": "2026-09-30"},
    "A110": {"customer": "c11", "item": "Laptop", "total": 1299.00, "delivered": "2026-10-27", "promised": "2026-10-27"},
    "A111": {"customer": "c12", "item": "Desk mat", "total": 30.00, "delivered": None, "promised": "2026-10-20"},
    "A112": {"customer": "c13", "item": "USB hub", "total": 40.00, "delivered": "2026-10-22", "promised": "2026-10-21"},
    "A113": {"customer": "c14", "item": "Speakers", "total": 180.00, "delivered": "2026-10-24", "promised": "2026-10-24"},
    "A114": {"customer": "c15", "item": "Filing cabinet", "total": 210.00, "delivered": "2026-09-20", "promised": "2026-09-18"},
    "A115": {"customer": "c16", "item": "Lamp bulbs (4)", "total": 18.00, "delivered": "2026-10-31", "promised": "2026-10-31"},
    "A116": {"customer": "c17", "item": "Whiteboard", "total": 95.00, "delivered": "2026-10-19", "promised": "2026-10-19"},
    "A117": {"customer": "c18", "item": "Printer", "total": 230.00, "delivered": "2026-10-16", "promised": "2026-10-15"},
    "A118": {"customer": "c19", "item": "Cable kit", "total": 22.00, "delivered": "2026-10-23", "promised": "2026-10-23"},
    "A119": {"customer": "c20", "item": "Footrest", "total": 55.00, "delivered": "2026-10-21", "promised": "2026-10-20"},
}
REFUNDS_LAST_90_DAYS = {"c8": 3, "c14": 1, "c18": 4}

# (ticket id, order, customer message, what the human did: action, amount, note)
TICKETS = [
    ("T1", "A100", "The lamp arrived with a cracked base. Photos attached.", ("refund", 49.00, "rule 1")),
    ("T2", "A101", "Chair's gas lift is broken, it sinks immediately.", ("refund", 289.00, "rule 1")),
    ("T3", "A102", "Desk motor makes a grinding noise and stops. Want my money back.", ("escalate", 0, "rule 5, over $500")),
    ("T4", "A103", "My headphones never showed up. Tracking hasn't moved in weeks.", ("refund", 120.00, "rule 2")),
    ("T5", "A104", "Changed my mind about the keyboard, it's still sealed.", ("refund", 76.50, "rule 3")),
    ("T6", "A105", "Decided I don't need the arm. I opened it to check but never used it.", ("deny", 0, "rule 4")),
    ("T7", "A106", "Webcam stopped working last week.", ("deny", 0, "rule 6, 49 days")),
    ("T8", "A107", "Shelf arrived with a split panel.", ("escalate", 0, "rule 5, 3 refunds in 90 days")),
    ("T9", "A108", "I wish I'd picked the white one instead of black. Could I get a small discount?", ("refund", 5.00, "goodwill exception")),
    ("T10", "A109", "Mouse scroll wheel is broken.", ("refund", 45.00, "rule 1, but reported on day 32: a mistake")),
    ("T11", "A110", "Laptop screen has dead pixels.", ("escalate", 0, "rule 5, over $500")),
    ("T12", "A111", "Desk mat hasn't arrived.", ("refund", 30.00, "rule 2")),
    ("T13", "A112", "USB hub doesn't work on any port.", ("refund", 40.00, "rule 1")),
    ("T14", "A113", "Speakers are fine, I just don't like the sound. Opened them.", ("deny", 0, "rule 4")),
    ("T15", "A114", "Cabinet drawer is off its rails. Just noticed.", ("deny", 0, "rule 6, 43 days")),
    ("T16", "A115", "Bulbs are the wrong fitting, unopened, can I return?", ("refund", 16.20, "rule 3")),
    ("T17", "A116", "Whiteboard has a scratch down the middle.", ("refund", 95.00, "rule 1")),
    ("T18", "A117", "Printer jams on every page.", ("escalate", 0, "rule 5, 4 refunds in 90 days")),
    ("T19", "A118", "Cables arrived fine but I ordered the wrong length. Opened.", ("refund", 22.00, "goodwill exception")),
    ("T20", "A119", "Footrest wobbles, one leg shorter than the others.", ("refund", 55.00, "rule 1")),
]

# What the written policy says, for reading disagreements. Humans deviated on T9 and T19 (goodwill) and T10 (mistake).
POLICY_ANSWER = {
    "T1": ("refund", 49.00), "T2": ("refund", 289.00), "T3": ("escalate", 0), "T4": ("refund", 120.00),
    "T5": ("refund", 76.50), "T6": ("deny", 0), "T7": ("deny", 0), "T8": ("escalate", 0), "T9": ("deny", 0),
    "T10": ("deny", 0), "T11": ("escalate", 0), "T12": ("refund", 30.00), "T13": ("refund", 40.00), "T14": ("deny", 0),
    "T15": ("deny", 0), "T16": ("refund", 16.20), "T17": ("refund", 95.00), "T18": ("escalate", 0), "T19": ("deny", 0),
    "T20": ("refund", 55.00),
}
