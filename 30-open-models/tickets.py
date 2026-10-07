"""Twelve support tickets for a triage worker, with the answers a careful person would give."""

RULES = """Triage rules:
Categories: outage, billing, account, bug, feature_request, security, question.
Base priority:
- P1: a service is down for the customer, data was lost, or there is a possible security breach.
- P2: a billing error of $500 or more, or a bug that blocks work with no workaround.
- P3: a billing error under $500, an account problem, or a bug that has a workaround.
- P4: feature requests and general questions (category question).
Enterprise plan: raise the priority one level (P4->P3, P3->P2, P2->P1). P1 stays P1.
Always look the customer up by email first, then file exactly one ticket with file_ticket."""

CUSTOMERS = {
    "ops@larkspur.io": {"customer_id": "C-201", "plan": "enterprise"},
    "maria@bluebirddental.com": {"customer_id": "C-202", "plan": "team"},
    "it@copperleaf.org": {"customer_id": "C-203", "plan": "enterprise"},
    "sam@juniperstudio.co": {"customer_id": "C-204", "plan": "starter"},
    "finance@harborlogistics.com": {"customer_id": "C-205", "plan": "team"},
    "dev@silverline.ai": {"customer_id": "C-206", "plan": "enterprise"},
}

# (email, message, expected category, expected priority)
TICKETS = [
    ("ops@larkspur.io", "Our whole team gets a 503 on the dashboard since 9am. Nothing loads.", "outage", "P1"),
    ("maria@bluebirddental.com", "We were charged twice for October, $49 each time.", "billing", "P3"),
    ("finance@harborlogistics.com", "Our invoice shows $1,200 instead of $120 for the Team plan.", "billing", "P2"),
    ("sam@juniperstudio.co", "It would be great to export reports as PDF.", "feature_request", "P4"),
    ("it@copperleaf.org", "Could you add SSO with Okta? We'd use it company-wide.", "feature_request", "P3"),
    ("dev@silverline.ai", "CSV export fails with a timeout, but exporting smaller date ranges works.", "bug", "P2"),
    ("maria@bluebirddental.com", "The calendar sync stopped working and there's no way to add appointments now.", "bug", "P2"),
    ("sam@juniperstudio.co", "I can't change the email address on my account.", "account", "P3"),
    ("it@copperleaf.org", "We saw logins to our admin account from a country we don't operate in.", "security", "P1"),
    ("finance@harborlogistics.com", "The mobile app has been down for all of our drivers since this morning.", "outage", "P1"),
    ("ops@larkspur.io", "Do you have an Android app?", "question", "P3"),
    ("dev@silverline.ai", "Search returns no results unless I reload the page first.", "bug", "P2"),
]
