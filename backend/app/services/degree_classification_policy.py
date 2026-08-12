"""Temporary default five-point degree-classification policy.

Institutions, programmes, award types, and Senate regulations may require a
different policy. Keeping bands here allows the default to be replaced without
changing evaluation services or endpoints.
"""

from decimal import Decimal
from enum import StrEnum
from typing import NamedTuple


class DegreeClassification(StrEnum):
    FIRST_CLASS = "first_class"
    SECOND_CLASS_UPPER = "second_class_upper"
    SECOND_CLASS_LOWER = "second_class_lower"
    THIRD_CLASS = "third_class"
    PASS = "pass"
    UNCLASSIFIED = "unclassified"


class GraduationOutcome(StrEnum):
    NOT_ELIGIBLE = "not_eligible"
    ELIGIBLE = "eligible"
    ELIGIBLE_WITH_CLASSIFICATION = "eligible_with_classification"


class ClassificationBand(NamedTuple):
    classification: DegreeClassification
    label: str
    minimum_cgpa: Decimal | None
    maximum_cgpa: Decimal


CLASSIFICATION_POLICY = "default_5_point"
MAXIMUM_CGPA = Decimal("5.00")
CLASSIFICATION_BANDS = (
    ClassificationBand(DegreeClassification.FIRST_CLASS, "First Class Honours", Decimal("4.50"), Decimal("5.00")),
    ClassificationBand(DegreeClassification.SECOND_CLASS_UPPER, "Second Class Honours (Upper Division)", Decimal("3.50"), Decimal("4.49")),
    ClassificationBand(DegreeClassification.SECOND_CLASS_LOWER, "Second Class Honours (Lower Division)", Decimal("2.40"), Decimal("3.49")),
    ClassificationBand(DegreeClassification.THIRD_CLASS, "Third Class Honours", Decimal("1.50"), Decimal("2.39")),
    ClassificationBand(DegreeClassification.PASS, "Pass", Decimal("1.00"), Decimal("1.49")),
    ClassificationBand(DegreeClassification.UNCLASSIFIED, "Unclassified", None, Decimal("0.99")),
)


def classify_cgpa(cgpa: Decimal) -> ClassificationBand:
    if cgpa >= Decimal("4.50"):
        return CLASSIFICATION_BANDS[0]
    if cgpa >= Decimal("3.50"):
        return CLASSIFICATION_BANDS[1]
    if cgpa >= Decimal("2.40"):
        return CLASSIFICATION_BANDS[2]
    if cgpa >= Decimal("1.50"):
        return CLASSIFICATION_BANDS[3]
    if cgpa >= Decimal("1.00"):
        return CLASSIFICATION_BANDS[4]
    return CLASSIFICATION_BANDS[5]
