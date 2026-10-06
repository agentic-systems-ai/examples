from invoicing.discounts import apply_discount
from invoicing.lines import Line
from invoicing.totals import subtotal, total_with_tax

LINES = [Line("Team plan", 2, 49.0), Line("Extra storage", 1, 12.0)]


def test_subtotal():
    assert subtotal(LINES) == 110.0


def test_total_with_tax():
    assert total_with_tax(LINES, tax_rate=0.2) == 132.0


def test_total_with_tax_and_discount():
    assert total_with_tax(LINES, tax_rate=0.2, discount_percent=10) == 118.8


def test_discount_is_capped():
    assert apply_discount(100.0, 150) == 0.0
