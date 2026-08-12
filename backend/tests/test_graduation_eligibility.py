from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1.endpoints import graduation_eligibility
from app.main import app
from app.models.academic_level import AcademicLevel
from app.models.programme import Programme
from app.models.student import Student
from app.models.user import User
from app.schemas.academic_performance import CGPAResult
from app.schemas.academic_progression import AcademicStandingSummary
from app.services import graduation_eligibility_service as service
from app.services.academic_progression_policy import AcademicStanding
from app.services.graduation_policy import GraduationEligibilityReason, MINIMUM_GRADUATION_CGPA, evaluate_graduation_policy
from tests.test_academic_performance import Session, hierarchy


def _context(*, current_level="Final Year", enrollment_status="active"):
    institution_id = uuid4(); programme_id = uuid4(); now = datetime.now(UTC)
    user = User(id=uuid4(), institution_id=institution_id, email="ada@test.edu", password_hash="x", first_name="Ada", last_name="Lovelace", is_active=True, is_verified=True)
    student = Student(id=uuid4(), institution_id=institution_id, user_id=user.id, programme_id=programme_id, matriculation_number="NSC/1", admission_year=2022, current_level=current_level, enrollment_status=enrollment_status, created_at=now, updated_at=now); student.user = user
    programme = Programme(id=programme_id, institution_id=institution_id, faculty_id=uuid4(), department_id=uuid4(), name="Computer Science", code="CSC", award="BSc", duration_years=4, study_mode="FULL_TIME", status="active")
    return student, programme


def _level(student, *, name="Final Year", sequence=4):
    return AcademicLevel(id=uuid4(), institution_id=student.institution_id, programme_id=student.programme_id, name=name, code=str(sequence), sequence_number=sequence, status="active")


def _cgpa(student_id, value="2.00", attempted=6, earned=6, courses=2):
    return CGPAResult(student_id=student_id, cumulative_attempted_units=attempted, cumulative_earned_units=earned, cumulative_quality_points=Decimal(value) * attempted, total_courses=courses, passed_courses=courses, failed_courses=0, cgpa=Decimal(value), semester_summaries=[])


def _standing(student, programme, value=AcademicStanding.GOOD_STANDING, cgpa="2.00"):
    return AcademicStandingSummary(student_id=student.id, programme_id=programme.id, current_level=student.current_level, cumulative_attempted_units=6, cumulative_earned_units=6, cumulative_quality_points=Decimal("12"), cgpa=Decimal(cgpa), standing=value, failed_course_count=0, failed_course_ids=[], failed_course_codes=[], failed_credit_units=0, has_carryover_courses=False)


def _patch_computation(monkeypatch, student, programme, records, *, cgpa="2.00", standing=AcademicStanding.GOOD_STANDING):
    monkeypatch.setattr(service, "compute_student_cgpa", lambda *_, **__: _cgpa(student.id, cgpa, courses=len(records)))
    monkeypatch.setattr(service, "compute_student_academic_standing", lambda *_, **__: _standing(student, programme, standing, cgpa))
    monkeypatch.setattr(service, "_query_eligible_published_results", lambda *_, **__: records)


@pytest.mark.parametrize("excluded", ["draft", "submitted", "approved", "rejected", "withheld", "inactive"])
def test_only_published_official_results_are_eligible(excluded):
    db = Session([]); service._query_eligible_published_results(db, institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]
    assert "published" in tuple(db.statements[0].compile().params.values()) and excluded != "published"


def test_final_level_resolution_uses_highest_sequence_number():
    db = Session(_level(_context()[0], sequence=7))
    result = service._resolve_final_academic_level(db, institution_id=uuid4(), programme_id=uuid4())  # type: ignore[arg-type]
    assert result.sequence_number == 7 and "DESC" in str(db.statements[0])


def test_outstanding_failures_group_by_course_id_and_sum_units():
    failed_one = hierarchy(passed=False, units=3, code="CSC101"); failed_two = hierarchy(passed=False, units=3, code="CSC101")
    failed_two = failed_two._replace(course=failed_one.course)
    failures = service._resolve_outstanding_failed_courses([failed_two, failed_one])
    assert len(failures) == 1 and failures[0].attempt_count == 2 and failures[0].credit_units == 3
    assert not failures[0].has_passing_attempt and failures[0].outstanding


def test_later_passing_attempt_clears_failure_without_mutating_history():
    failed = hierarchy(passed=False, code="CSC101"); passed = hierarchy(passed=True, code="CSC101")
    passed = passed._replace(course=failed.course)
    records = [failed, passed]
    assert service._resolve_outstanding_failed_courses(records) == []
    assert len(records) == 2 and not records[0].result.passed and records[1].result.passed


def test_passed_only_course_is_not_a_deficiency():
    assert service._resolve_outstanding_failed_courses([hierarchy(passed=True)]) == []


@pytest.mark.parametrize(("cgpa", "standing", "eligible", "reason"), [
    ("1.00", AcademicStanding.PROBATION, True, GraduationEligibilityReason.ELIGIBLE),
    ("0.99", AcademicStanding.ACADEMIC_REVIEW, False, GraduationEligibilityReason.INSUFFICIENT_CGPA),
])
def test_minimum_cgpa_boundary_and_standing_policy(cgpa, standing, eligible, reason):
    result, reasons = evaluate_graduation_policy(has_published_results=True, current_level_resolved=True, final_level_reached=True, outstanding_failed_course_count=0, cgpa=Decimal(cgpa), academic_standing=standing, enrollment_status="active", minimum_required_units=None, cumulative_earned_units=0)
    assert result is eligible and reason in reasons and MINIMUM_GRADUATION_CGPA == Decimal("1.00")


def test_complete_eligible_evaluation_reuses_totals_and_is_read_only(monkeypatch):
    student, programme = _context(); current = _level(student); final = _level(student); records = [hierarchy(passed=True), hierarchy(passed=True)]
    _patch_computation(monkeypatch, student, programme, records)
    db = Session(student, programme, current, final)
    result = service.evaluate_student_graduation_eligibility(db, institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.student_name == "Ada Lovelace" and result.programme_name == "Computer Science"
    assert result.final_level_reached and result.eligible_for_graduation
    assert result.eligibility_reasons == [GraduationEligibilityReason.ELIGIBLE]
    assert result.cumulative_attempted_units == result.cumulative_earned_units == 6
    assert result.minimum_required_units is None and not result.credit_requirement_configured
    assert result.meets_credit_requirement is None and not result.curriculum_completion_verified
    assert db.commits == 0 and db.added == [] and student.enrollment_status == "active"


def test_below_final_level_and_outstanding_failure_produce_multiple_reasons(monkeypatch):
    student, programme = _context(current_level="Year Three"); current = _level(student, name="Year Three", sequence=3); final = _level(student, sequence=4); failed = hierarchy(passed=False, units=4)
    _patch_computation(monkeypatch, student, programme, [failed])
    result = service.evaluate_student_graduation_eligibility(Session(student, programme, current, final), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert not result.eligible_for_graduation and result.outstanding_failed_credit_units == 4
    assert GraduationEligibilityReason.FINAL_LEVEL_NOT_REACHED in result.eligibility_reasons
    assert GraduationEligibilityReason.OUTSTANDING_FAILED_COURSES in result.eligibility_reasons


def test_no_results_is_not_evaluated_not_academic_failure(monkeypatch):
    student, programme = _context(); current = _level(student); final = _level(student)
    _patch_computation(monkeypatch, student, programme, [], cgpa="0.00", standing=AcademicStanding.NOT_EVALUATED)
    result = service.evaluate_student_graduation_eligibility(Session(student, programme, current, final), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert not result.has_published_results and not result.eligible_for_graduation
    assert result.academic_standing == AcademicStanding.NOT_EVALUATED
    assert result.eligibility_reasons == [GraduationEligibilityReason.NO_PUBLISHED_RESULTS]


def test_unresolved_level_and_ineligible_enrollment_are_reported(monkeypatch):
    student, programme = _context(current_level="Unknown", enrollment_status="withdrawn"); final = _level(student); records = [hierarchy(passed=True)]
    _patch_computation(monkeypatch, student, programme, records)
    result = service.evaluate_student_graduation_eligibility(Session(student, programme, None, final), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert GraduationEligibilityReason.CURRENT_LEVEL_UNRESOLVED in result.eligibility_reasons
    assert GraduationEligibilityReason.ENROLLMENT_STATUS_INELIGIBLE in result.eligibility_reasons


def test_missing_and_cross_institution_student_are_404_domain_errors():
    with pytest.raises(service.GraduationEligibilityStudentNotFoundError): service.evaluate_student_graduation_eligibility(Session(), institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]
    assert graduation_eligibility._map_error(service.GraduationEligibilityStudentNotFoundError()).status_code == 404


def test_route_registration_and_authentication():
    assert "/api/v1/students/{student_id}/graduation-eligibility" in app.openapi()["paths"]
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
