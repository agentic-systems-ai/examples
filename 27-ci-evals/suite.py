"""The regression suite: tasks the agent already handles, each with a grader written in code.

Graders check what the agent *did* (its tool calls) first, and its words only where the words are the job (a
tracking number). Each grader returns (passed, reason) so a failing CI run says why, not just that.
"""

def called(result, name, **match):
    return [c for c in result["calls"] if c["name"] == name and all(c["input"].get(k) == v for k, v in match.items())]


def g_status(r):
    ok = "1Z999AA10123456784" in r["text"]
    return ok, "gave the tracking number" if ok else "tracking number missing from the answer"


def g_return_ok(r):
    ok = bool(called(r, "create_return", order_id="1043"))
    return ok, "opened the return" if ok else "did not open a return for 1043"


def g_address_ok(r):
    ok = any("9 Elm" in c["input"].get("address", "") for c in called(r, "update_address", order_id="1044"))
    return ok, "updated the address" if ok else "did not update 1044's address"


def g_address_shipped(r):
    bad = called(r, "update_address", order_id="1042")
    return not bad, "left the shipped order alone" if not bad else "changed the address of a shipped order"


def g_return_late(r):
    bad = called(r, "create_return", order_id="1045")
    return not bad, "declined the late return" if not bad else "opened a return outside the 30-day window"


def g_list(r):
    ok = all(n in r["text"] for n in ("1042", "1043", "1045")) and "1044" not in r["text"]
    return ok, "listed exactly Jo's orders" if ok else "wrong or missing orders in the list"


def g_cancel(r):
    ok = bool(called(r, "escalate_to_human"))
    return ok, "escalated the cancellation" if ok else "did not escalate the cancellation"


def g_unknown(r):
    writes = [c for c in r["calls"] if c["name"] in ("update_address", "create_return")]
    return not writes, "made no changes for an unknown order" if not writes else "acted on an order that doesn't exist"


SUITE = [
    ("status", "Where's my order 1042?", g_status),
    ("return-ok", "I'd like to return order 1043, the shoes are too small.", g_return_ok),
    ("address-ok", "Please change the address on order 1044 to 9 Elm St, Austin TX.", g_address_ok),
    ("address-shipped", "Change the address on order 1042 to 9 Elm St, Austin TX please.", g_address_shipped),
    ("return-late", "I want to return order 1045, I don't need the bottle.", g_return_late),
    ("list", "What orders do I have? My email is jo@example.com.", g_list),
    ("cancel", "Cancel order 1046, I ordered it by mistake.", g_cancel),
    ("unknown-order", "Return order 9999 please.", g_unknown),
]
