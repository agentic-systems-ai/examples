"""A toy wallet for agent payments: signed spending mandates, cart checks, human approval, scoped payment tokens.

The ideas come from the agent-payments protocols announced in 2025: AP2's signed *mandates* (what the user asked
for, and the exact cart they approved) and ACP's *shared payment tokens* scoped to one merchant and one amount.
Nothing here touches real money; signatures are HMAC so the example has no dependencies.
"""

import hashlib
import hmac
import json
import secrets
import time

_KEY = secrets.token_bytes(32)        # the wallet's signing key
APPROVAL_THRESHOLD = 40.00            # carts above this need the user's explicit approval
TOKENS: dict[str, dict] = {}          # issued payment tokens
LEDGER: list[dict] = []               # what actually got charged


def _sign(payload: dict) -> str:
    return hmac.new(_KEY, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def intent_mandate(description: str, category: str, max_total: float, merchants: list[str], hours: float = 24,
                   max_purchases: int = 1) -> dict:
    """What the user authorized, in their own words and in checkable limits. Signed by the user's wallet."""
    m = {"type": "intent", "description": description, "category": category, "max_total": max_total,
         "merchants": merchants, "expires": time.time() + hours * 3600, "max_purchases": max_purchases, "used": 0}
    m["signature"] = _sign({k: v for k, v in m.items() if k != "used"})
    return m


def check_cart(mandate: dict, cart: dict) -> list[str]:
    """Every reason this cart falls outside the mandate. Empty list = within the mandate."""
    problems = []
    if not hmac.compare_digest(mandate["signature"], _sign({k: v for k, v in mandate.items() if k not in ("signature", "used")})):
        problems.append("mandate_invalid: signature does not match")
    if time.time() > mandate["expires"]:
        problems.append("mandate_expired: the authorization has lapsed")
    if mandate["used"] >= mandate["max_purchases"]:
        problems.append("mandate_used: this authorization covered one purchase")
    if cart["merchant"] not in mandate["merchants"]:
        problems.append(f"merchant_not_approved: {cart['merchant']!r} is not one the user approved")
    if cart["total"] > mandate["max_total"] + 1e-9:
        problems.append(f"over_limit: total ${cart['total']:.2f} is over the limit of ${mandate['max_total']:.2f}")
    off = [i["name"] for i in cart["items"] if i["category"] != mandate["category"]]
    if off:
        problems.append(f"outside_category: not {mandate['category']}: {', '.join(off)}")
    return problems


def issue_token(mandate: dict, cart: dict, approve) -> dict:
    """Check the cart, get the user's approval if needed (their signature on the exact cart), then issue a payment
    token usable once, by one merchant, for exactly this amount, for 15 minutes."""
    problems = check_cart(mandate, cart)
    if problems:
        return {"ok": False, "reasons": problems}
    needs_approval = cart["total"] > APPROVAL_THRESHOLD
    if needs_approval and not approve(cart):
        return {"ok": False, "reasons": ["user_declined: the user declined this cart"]}
    cart_mandate = {"type": "cart", "cart_id": cart["id"], "merchant": cart["merchant"], "total": cart["total"],
                    "items": [i["name"] for i in cart["items"]], "approved_by_user": needs_approval}
    cart_mandate["signature"] = _sign(cart_mandate)
    token = "spt_" + secrets.token_hex(8)
    TOKENS[token] = {"merchant": cart["merchant"], "amount": cart["total"], "cart_id": cart["id"],
                     "expires": time.time() + 900, "used": False, "cart_mandate": cart_mandate}
    mandate["used"] += 1
    return {"ok": True, "token": token, "approved_by_user": needs_approval}


def charge(token: str, merchant: str, amount: float, cart_id: str) -> str:
    """Called by the merchant. The token only works for what it was issued for."""
    t = TOKENS.get(token)
    if t is None:
        raise PermissionError("token_unknown: no such token")
    if t["used"]:
        raise PermissionError("token_used: tokens work once")
    if time.time() > t["expires"]:
        raise PermissionError("token_expired: tokens last 15 minutes")
    if merchant != t["merchant"]:
        raise PermissionError(f"wrong_merchant: token is for {t['merchant']}, not {merchant}")
    if abs(amount - t["amount"]) > 1e-9 or cart_id != t["cart_id"]:
        raise PermissionError(f"cart_changed: token is for ${t['amount']:.2f} on {t['cart_id']}, not ${amount:.2f}")
    t["used"] = True
    LEDGER.append({"merchant": merchant, "amount": amount, "cart_id": cart_id, "cart_mandate": t["cart_mandate"]})
    return f"charged ${amount:.2f}"
