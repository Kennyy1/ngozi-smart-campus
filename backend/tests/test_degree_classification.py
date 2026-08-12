from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1.endpoints import degree_classification
from app.main import app
from app.schemas.academic_performance import CGPAResult
from app.schemas.graduation_eligibility import GraduationEligibilityEvaluation
from app.services import degree_classification_service as service
from app.services.academic_progression_policy import AcademicStanding
from app.services.degree_classification_policy import (
    CLASSIFICATION_POLICY, DegreeClassification, GraduationOutcome, classify_cgpa,
)
from app.services.graduation_eligibility_service import GraduationEligibilityStudentNotFoundError
from app.services.graduation_policy import GraduationEligibilityReason
from tests.test_academic_performance import Session


@pytest.mark.parametrize(("cgpa", "classification", "label"), [
    ("5.00", DegreeClassification.FIRST_CLASS, "First Class Honours"),
    ("4.50", DegreeClassification.FIRST_CLASS, "First Class Honours"),
    ("4.49", DegreeClassification.SECOND_CLASS_UPPER, "Second Class Honours (Upper Division)"),
    ("3.50", DegreeClassification.SECOND_CLASS_UPPER, "Second Class Honours (Upper Division)"),
    ("3.49", DegreeClassification.SECOND_CLASS_LOWER, "Second Class Honours (Lower Division)"),
    ("2.40", DegreeClassification.SECOND_CLASS_LOWER, "Second Class Honours (Lower Division)"),
    ("2.39", DegreeClassification.THIRD_CLASS, "Third Class Honours"),
    ("1.50", DegreeClassification.THIRD_CLASS, "Third Class Honours"),
    ("1.49", DegreeClassification.PASS, "Pass"),
    ("1.00", DegreeClassification.PASS, "Pass"),
    ("0.99", DegreeClassification.UNCLASSIFIED, "Unclassified"),
])
def test_decimal_classification_boundaries(cgpa: str, classification: DegreeClassification, label: str) -> None:
    band = classify_cgpa(Decimal(cgpa))
    assert band.classification == classification and band.label == label
    assert isinstance(band.maximum_cgpa, Decimal)


def eligibility(*, eligible: bool = True, cgpa: str = "4.50", reasons=None, standing=AcademicStanding.GOOD_STANDING, failures: int = 0) -> GraduationEligibilityEvaluation:
    return GraduationEligibilityEvaluation(
        student_id=uuid4(), matriculation_number="NSC/1", student_name="Ada Lovelace",
        programme_id=uuid4(), programme_name="Computer Science", programme_code="CSC",
        current_academic_level_id=uuid4(), current_level="Final Year", current_level_sequence=4,
        final_academic_level_id=uuid4(), final_level="Final Year", final_level_sequence=4,
        cumulative_attempted_units=120, cumulative_earned_units=120,
        minimum_required_units=None, credit_requirement_configured=False,
        curriculum_completion_verified=False, cgpa=Decimal(cgpa), minimum_graduation_cgpa=Decimal("1.00"),
        academic_standing=standing, total_published_courses=40, passed_course_count=40,
        outstanding_failed_course_count=failures, outstanding_failed_credit_units=0,
        outstanding_courses=[], final_level_reached=True, meets_cgpa_requirement=True,
        meets_credit_requirement=None, has_published_results=True,
        eligible_for_graduation=eligible,
        eligibility_reasons=reasons or [GraduationEligibilityReason.ELIGIBLE],
    )


def cgpa_result(item: GraduationEligibilityEvaluation) -> CGPAResult:
    return CGPAResult(student_id=item.student_id, cumulative_attempted_units=item.cumulative_attempted_units, cumulative_earned_units=item.cumulative_earned_units, cumulative_quality_points=Decimal("540.00"), total_courses=40, passed_courses=40, failed_courses=0, cgpa=item.cgpa, semester_summaries=[])


def test_eligible_student_reuses_eligibility_and_cgpa_and_receives_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    item = eligibility()
    calls = {"eligibility": 0, "cgpa": 0}
    def get_eligibility(*args, **kwargs): calls["eligibility"] += 1; return item
    def get_cgpa(*args, **kwargs): calls["cgpa"] += 1; return cgpa_result(item)
    monkeypatch.setattr(service, "evaluate_student_graduation_eligibility", get_eligibility)
    monkeypatch.setattr(service, "compute_student_cgpa", get_cgpa)
    db = Session()
    result = service.evaluate_student_degree_classification(db, institution_id=uuid4(), student_id=item.student_id)  # type: ignore[arg-type]
    assert calls == {"eligibility": 1, "cgpa": 1}
    assert result.degree_classification == DegreeClassification.FIRST_CLASS
    assert result.degree_classification_label == "First Class Honours"
    assert result.graduation_outcome == GraduationOutcome.ELIGIBLE_WITH_CLASSIFICATION
    assert result.classification_policy == CLASSIFICATION_POLICY == "default_5_point"
    assert result.student_name == "Ada Lovelace" and result.programme_code == "CSC"
    assert result.cgpa == Decimal("4.50") and result.academic_standing == AcademicStanding.GOOD_STANDING
    assert result.cumulative_attempted_units == result.cumulative_earned_units == 120
    assert db.commits == 0 and db.added == []


@pytest.mark.parametrize(("reason", "standing", "failures"), [
    (GraduationEligibilityReason.NO_PUBLISHED_RESULTS, AcademicStanding.NOT_EVALUATED, 0),
    (GraduationEligibilityReason.FINAL_LEVEL_NOT_REACHED, AcademicStanding.GOOD_STANDING, 0),
    (GraduationEligibilityReason.OUTSTANDING_FAILED_COURSES, AcademicStanding.GOOD_STANDING, 1),
    (GraduationEligibilityReason.ACADEMIC_REVIEW, AcademicStanding.ACADEMIC_REVIEW, 0),
])
def test_ineligible_students_receive_no_classification_and_propagate_reason(monkeypatch: pytest.MonkeyPatch, reason: GraduationEligibilityReason, standing: AcademicStanding, failures: int) -> None:
    item = eligibility(eligible=False, reasons=[reason], standing=standing, failures=failures)
    monkeypatch.setattr(service, "evaluate_student_graduation_eligibility", lambda *_, **__: item)
    monkeypatch.setattr(service, "compute_student_cgpa", lambda *_, **__: cgpa_result(item))
    result = service.evaluate_student_degree_classification(Session(), institution_id=uuid4(), student_id=item.student_id)  # type: ignore[arg-type]
    assert result.graduation_outcome == GraduationOutcome.NOT_ELIGIBLE
    assert result.degree_classification is None and result.degree_classification_label is None
    assert result.graduation_eligibility_reasons == [reason]
    assert result.outstanding_failed_course_count == failures


def test_missing_student_mapping_route_registration_and_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "evaluate_student_graduation_eligibility", lambda *_, **__: (_ for _ in ()).throw(GraduationEligibilityStudentNotFoundError()))
    with pytest.raises(GraduationEligibilityStudentNotFoundError):
        service.evaluate_student_degree_classification(Session(), institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]
    assert degree_classification._map_error(GraduationEligibilityStudentNotFoundError()).status_code == 404
    assert "/api/v1/students/{student_id}/graduation-outcome" in app.openapi()["paths"]
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
