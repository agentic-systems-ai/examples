"""Invoice totals."""

from .discounts import apply_discount
from .lines import Line


def subtotal(lines: list[Line]) -> float:
    return round(sum(line.quantity * line.unit_price for line in lines), 2)


def total_with_tax(lines: list[Line], tax_rate: float, discount_percent: float = 0.0) -> float:
    """Subtotal, minus any discount, plus tax. tax_rate is a fraction, e.g. 0.2 for 20%."""
    discounted = apply_discount(subtotal(lines), discount_percent)
    return round(discounted * tax_rate, 2)
