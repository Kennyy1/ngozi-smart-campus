from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.degree_classification import GraduationOutcomeEvaluation
from app.services.academic_performance_service import compute_student_cgpa
from app.services.degree_classification_policy import (
    CLASSIFICATION_POLICY, GraduationOutcome, classify_cgpa,
)
from app.services.graduation_eligibility_service import evaluate_student_graduation_eligibility


def evaluate_student_degree_classification(session: Session, *, institution_id: UUID, student_id: UUID) -> GraduationOutcomeEvaluation:
    eligibility = evaluate_student_graduation_eligibility(session, institution_id=institution_id, student_id=student_id)
    cgpa = compute_student_cgpa(session, institution_id=institution_id, student_id=student_id)
    classification = classify_cgpa(cgpa.cgpa) if eligibility.eligible_for_graduation else None
    outcome = (
        GraduationOutcome.ELIGIBLE_WITH_CLASSIFICATION
        if classification is not None
        else GraduationOutcome.NOT_ELIGIBLE
    )
    return GraduationOutcomeEvaluation(
        student_id=eligibility.student_id, matriculation_number=eligibility.matriculation_number,
        student_name=eligibility.student_name, programme_id=eligibility.programme_id,
        programme_name=eligibility.programme_name, programme_code=eligibility.programme_code,
        current_level=eligibility.current_level, cgpa=cgpa.cgpa,
        academic_standing=eligibility.academic_standing,
        eligible_for_graduation=eligibility.eligible_for_graduation,
        graduation_eligibility_reasons=eligibility.eligibility_reasons,
        graduation_outcome=outcome,
        degree_classification=classification.classification if classification else None,
        degree_classification_label=classification.label if classification else None,
        classification_policy=CLASSIFICATION_POLICY,
        outstanding_failed_course_count=eligibility.outstanding_failed_course_count,
        cumulative_attempted_units=cgpa.cumulative_attempted_units,
        cumulative_earned_units=cgpa.cumulative_earned_units,
        evaluated_at=datetime.now(UTC),
    )
