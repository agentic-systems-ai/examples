"""Labelled support tickets for a fictional product. The labels follow house rules the seed prompt doesn't state:

- suspicious logins, leaked keys or unknown devices are SECURITY, even if they also mention money
- changing plan, seats or owner is ACCOUNT, not billing
- refunds, charges and invoices are BILLING
- "it would be nice if" / missing capability is FEATURE_REQUEST, even when phrased as a complaint
- something that used to work, or errors, is BUG

Train and test exercise the same rules with different tickets, so a prompt can only score well on test
by learning the rules, not by memorising examples.
"""

LABELS = ["billing", "bug", "account", "feature_request", "security"]

TRAIN = [
    ("I was charged twice for September. Please refund the duplicate.", "billing"),
    ("Can you move us from Team to Starter next month?", "account"),
    ("The CSV export has been failing since yesterday's update.", "bug"),
    ("It would be great if dashboards could be shared with a public link.", "feature_request"),
    ("Someone logged into our account from a country we've never been to, and there's a new invoice I don't recognise.", "security"),
    ("Please transfer ownership of the workspace to my colleague Ana.", "account"),
    ("Our API key showed up in a public GitHub repo. What do we do?", "security"),
    ("Your app doesn't support dark mode, which is really frustrating for my team.", "feature_request"),
    ("Where can I download last quarter's invoices as PDFs?", "billing"),
    ("Clicking 'Save' on the report editor now shows error 500.", "bug"),
    ("We need to add five more seats for the new hires.", "account"),
    ("I got a password reset email I didn't request and then a charge for an upgrade.", "security"),
]

TEST = [
    ("We were billed for 12 seats but only have 10 users. Can we get the difference back?", "billing"),
    ("Please downgrade us to the free tier at the end of the cycle.", "account"),
    ("Since this morning, notifications aren't being sent at all.", "bug"),
    ("Annoying that there's no way to bulk-delete old projects.", "feature_request"),
    ("There's a device signed into my account that isn't mine, and it changed our billing email.", "security"),
    ("Can you make Jordan the account owner instead of me? I'm leaving the company.", "account"),
    ("A contractor accidentally posted our webhook secret in a public Slack. Should we rotate it?", "security"),
    ("Charts would be much more useful if they supported a logarithmic scale.", "feature_request"),
    ("I need an invoice with our VAT number on it for the March payment.", "billing"),
    ("The mobile app crashes as soon as I open a shared folder.", "bug"),
    ("We're merging teams; please remove three seats from our plan.", "account"),
    ("After a login from an unfamiliar IP, our plan was upgraded and we were charged.", "security"),
]
