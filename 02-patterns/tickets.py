"""Sample data: a support inbox for a fictional product, plus the policy the replies must follow."""

POLICY = """\
Larkspur support policy (fictional product)
- Plans: Starter $12/month, Team $49/month. Billing is monthly, in advance.
- Duplicate charges are refunded in full within 5 business days; ask for the invoice number if it is missing.
- Refunds for unused time are not offered, but customers can cancel any time and keep access until the period ends.
- Known issue LRK-212: CSV export times out for workspaces with more than 50,000 rows. Workaround: export by date range. Fix scheduled for the next release.
- Never promise dates for fixes beyond "the next release". Never ask for passwords or full card numbers.
- Tone: warm, direct, no more than 150 words. Sign off as "The Larkspur team".
"""

TICKETS = {
    "billing": (
        "Hi, I was charged $49 twice this month for the Team plan (invoice INV-20931). "
        "Can you fix this? - Priya"
    ),
    "bug": (
        "Exporting our projects to CSV just spins and then fails. We have a big workspace, maybe 80k rows. "
        "This is blocking our quarterly report. - Marco"
    ),
    "mixed": (
        "Three things: (1) the CSV export keeps failing on our large workspace, (2) how do I add a teammate "
        "as an admin, and (3) if we downgrade from Team to Starter mid-month, do we get money back? - Dana"
    ),
}
