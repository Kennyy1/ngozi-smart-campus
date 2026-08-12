"""Provisional, replaceable graduation eligibility policy."""

from decimal import Decimal
from enum import StrEnum

from app.services.academic_progression_policy import AcademicStanding


class GraduationEligibilityReason(StrEnum):
    ELIGIBLE = "eligible"
    NO_PROGRAMME = "no_programme"
    NO_PUBLISHED_RESULTS = "no_published_results"
    CURRENT_LEVEL_UNRESOLVED = "current_level_unresolved"
    FINAL_LEVEL_NOT_REACHED = "final_level_not_reached"
    OUTSTANDING_FAILED_COURSES = "outstanding_failed_courses"
    INSUFFICIENT_CGPA = "insufficient_cgpa"
    ACADEMIC_REVIEW = "academic_review"
    INSUFFICIENT_EARNED_UNITS = "insufficient_earned_units"
    CREDIT_REQUIREMENT_NOT_CONFIGURED = "credit_requirement_not_configured"
    ENROLLMENT_STATUS_INELIGIBLE = "enrollment_status_ineligible"


MINIMUM_GRADUATION_CGPA = Decimal("1.00")
ELIGIBLE_ENROLLMENT_STATUSES = frozenset({"active"})


def evaluate_graduation_policy(
    *, has_published_results: bool, current_level_resolved: bool,
    final_level_reached: bool, outstanding_failed_course_count: int,
    cgpa: Decimal, academic_standing: AcademicStanding, enrollment_status: str,
    minimum_required_units: int | None, cumulative_earned_units: int,
) -> tuple[bool, list[GraduationEligibilityReason]]:
    reasons: list[GraduationEligibilityReason] = []
    if not has_published_results:
        reasons.append(GraduationEligibilityReason.NO_PUBLISHED_RESULTS)
    if not current_level_resolved:
        reasons.append(GraduationEligibilityReason.CURRENT_LEVEL_UNRESOLVED)
    elif not final_level_reached:
        reasons.append(GraduationEligibilityReason.FINAL_LEVEL_NOT_REACHED)
    if outstanding_failed_course_count:
        reasons.append(GraduationEligibilityReason.OUTSTANDING_FAILED_COURSES)
    if has_published_results and cgpa < MINIMUM_GRADUATION_CGPA:
        reasons.append(GraduationEligibilityReason.INSUFFICIENT_CGPA)
    if academic_standing == AcademicStanding.ACADEMIC_REVIEW:
        reasons.append(GraduationEligibilityReason.ACADEMIC_REVIEW)
    if minimum_required_units is not None and cumulative_earned_units < minimum_required_units:
        reasons.append(GraduationEligibilityReason.INSUFFICIENT_EARNED_UNITS)
    if enrollment_status not in ELIGIBLE_ENROLLMENT_STATUSES:
        reasons.append(GraduationEligibilityReason.ENROLLMENT_STATUS_INELIGIBLE)
    return (True, [GraduationEligibilityReason.ELIGIBLE]) if not reasons else (False, reasons)
