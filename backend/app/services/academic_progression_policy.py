"""Provisional academic-standing policy.

This module deliberately isolates temporary defaults so institution-configured
Senate regulations can replace them without changing progression queries or API
handlers.
"""

from decimal import Decimal
from enum import StrEnum


class AcademicStanding(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    GOOD_STANDING = "good_standing"
    WARNING = "warning"
    PROBATION = "probation"
    ACADEMIC_REVIEW = "academic_review"


class ProgressionReason(StrEnum):
    ELIGIBLE = "eligible"
    INSUFFICIENT_CGPA = "insufficient_cgpa"
    ACADEMIC_REVIEW = "academic_review"
    NO_PUBLISHED_RESULTS = "no_published_results"
    FINAL_LEVEL_REACHED = "final_level_reached"
    CURRENT_LEVEL_UNRESOLVED = "current_level_unresolved"
    NEXT_LEVEL_NOT_CONFIGURED = "next_level_not_configured"


GOOD_STANDING_CGPA = Decimal("2.00")
WARNING_CGPA = Decimal("1.50")
PROBATION_CGPA = Decimal("1.00")
PROGRESSION_CGPA = Decimal("1.00")


def determine_academic_standing(*, cgpa: Decimal, has_published_results: bool) -> AcademicStanding:
    if not has_published_results:
        return AcademicStanding.NOT_EVALUATED
    if cgpa >= GOOD_STANDING_CGPA:
        return AcademicStanding.GOOD_STANDING
    if cgpa >= WARNING_CGPA:
        return AcademicStanding.WARNING
    if cgpa >= PROBATION_CGPA:
        return AcademicStanding.PROBATION
    return AcademicStanding.ACADEMIC_REVIEW


def determine_progression_reason(
    *, cgpa: Decimal, standing: AcademicStanding, current_level_resolved: bool,
    next_level_exists: bool, final_level_reached: bool, has_published_results: bool,
) -> ProgressionReason:
    if not has_published_results:
        return ProgressionReason.NO_PUBLISHED_RESULTS
    if not current_level_resolved:
        return ProgressionReason.CURRENT_LEVEL_UNRESOLVED
    if final_level_reached:
        return ProgressionReason.FINAL_LEVEL_REACHED
    if not next_level_exists:
        return ProgressionReason.NEXT_LEVEL_NOT_CONFIGURED
    if standing == AcademicStanding.ACADEMIC_REVIEW:
        return ProgressionReason.ACADEMIC_REVIEW
    if cgpa < PROGRESSION_CGPA:
        return ProgressionReason.INSUFFICIENT_CGPA
    return ProgressionReason.ELIGIBLE
