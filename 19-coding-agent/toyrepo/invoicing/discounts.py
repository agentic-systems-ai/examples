"""Discounts."""


def apply_discount(amount: float, percent: float) -> float:
    """Reduce amount by percent (0-100). Discounts above 100% are capped at 100%."""
    percent = max(0.0, min(percent, 100.0))
    return round(amount * (1 - percent / 100), 2)
