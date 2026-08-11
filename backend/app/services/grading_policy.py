from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Grade:
    letter: str
    point: Decimal
    passed: bool


# Phase 9O.1's isolated default. It is intentionally replaceable and is not a
# globally configured university grading rule.
def resolve_default_grade(score: Decimal) -> Grade:
    if score >= Decimal("70"):
        return Grade("A", Decimal("5.00"), True)
    if score >= Decimal("60"):
        return Grade("B", Decimal("4.00"), True)
    if score >= Decimal("50"):
        return Grade("C", Decimal("3.00"), True)
    if score >= Decimal("45"):
        return Grade("D", Decimal("2.00"), True)
    if score >= Decimal("40"):
        return Grade("E", Decimal("1.00"), True)
    return Grade("F", Decimal("0.00"), False)
