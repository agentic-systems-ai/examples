from dataclasses import dataclass


@dataclass
class Line:
    description: str
    quantity: int
    unit_price: float  # in dollars
