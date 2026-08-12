from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1.endpoints import academic_progression
from app.main import app
from app.models.academic_level import AcademicLevel
from app.models.programme import Programme
from app.models.student import Student
from app.schemas.academic_performance import CGPAResult
from app.services import academic_progression_service as service
from app.services.academic_progression_policy import (
    AcademicStanding, ProgressionReason, determine_academic_standing,
    determine_progression_reason,
)
from tests.test_academic_performance import Session, hierarchy


@pytest.mark.parametrize(("cgpa", "expected"), [
    ("2.00", AcademicStanding.GOOD_STANDING), ("1.99", AcademicStanding.WARNING),
    ("1.50", AcademicStanding.WARNING), ("1.49", AcademicStanding.PROBATION),
    ("1.00", AcademicStanding.PROBATION), ("0.99", AcademicStanding.ACADEMIC_REVIEW),
])
def test_provisional_standing_thresholds(cgpa: str, expected: AcademicStanding) -> None:
    assert determine_academic_standing(cgpa=Decimal(cgpa), has_published_results=True) == expected


def test_no_results_are_not_evaluated_and_not_academic_review() -> None:
    assert determine_academic_standing(cgpa=Decimal("0"), has_published_results=False) == AcademicStanding.NOT_EVALUATED
    reason = determine_progression_reason(
        cgpa=Decimal("0"), standing=AcademicStanding.NOT_EVALUATED,
        current_level_resolved=True, next_level_exists=True, final_level_reached=False,
        has_published_results=False,
    )
    assert reason == ProgressionReason.NO_PUBLISHED_RESULTS


def _programme(institution_id, *, duration: int = 4) -> Programme:
    return Programme(id=uuid4(), institution_id=institution_id, faculty_id=uuid4(), department_id=uuid4(), name="Computer Science", code="CSC", award="BSc", duration_years=duration, study_mode="FULL_TIME", status="active")


def _level(institution_id, programme_id, *, name: str, sequence: int) -> AcademicLevel:
    return AcademicLevel(id=uuid4(), institution_id=institution_id, programme_id=programme_id, name=name, code=str(sequence), sequence_number=sequence, status="active")


def _student(institution_id, programme_id, *, level: str | None = "Year Two") -> Student:
    now = datetime.now(UTC)
    return Student(id=uuid4(), institution_id=institution_id, user_id=uuid4(), programme_id=programme_id, matriculation_number="NSC/1", admission_year=2025, current_level=level, enrollment_status="active", created_at=now, updated_at=now)


def _cgpa(student_id, *, value: str = "2.00", courses: int = 1) -> CGPAResult:
    return CGPAResult(student_id=student_id, cumulative_attempted_units=3 if courses else 0, cumulative_earned_units=3 if courses else 0, cumulative_quality_points=Decimal("6") if courses else Decimal("0"), total_courses=courses, passed_courses=courses, failed_courses=0, cgpa=Decimal(value), semester_summaries=[])


def test_failed_results_summary_only_includes_failed_published_eligible_records(monkeypatch: pytest.MonkeyPatch) -> None:
    failed = hierarchy(passed=False, units=4, code="CSC201")
    passed = hierarchy(passed=True, code="CSC202")
    monkeypatch.setattr(service, "_query_eligible_published_results", lambda *_, **__: [failed, passed])
    records = service._query_published_failed_results(Session(), institution_id=failed.result.institution_id, student_id=failed.result.student_id)  # type: ignore[arg-type]
    assert records == [failed]
    summary = service._build_failed_course(failed)
    assert summary.course_code == "CSC201" and summary.credit_units == 4 and summary.grade_letter == "F"


def test_standing_reports_failed_units_and_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    institution_id = uuid4(); programme = _programme(institution_id); student = _student(institution_id, programme.id)
    failed = hierarchy(passed=False, units=4)
    monkeypatch.setattr(service, "compute_student_cgpa", lambda *_, **__: _cgpa(student.id))
    monkeypatch.setattr(service, "_query_published_failed_results", lambda *_, **__: [failed])
    db = Session(student, programme)
    result = service.compute_student_academic_standing(db, institution_id=institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.standing == AcademicStanding.GOOD_STANDING
    assert result.failed_course_count == 1 and result.failed_credit_units == 4 and result.has_carryover_courses
    assert result.failed_course_ids == [failed.course.id] and db.commits == 0 and db.added == []


def test_progression_resolves_levels_by_sequence_and_carryover_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    institution_id = uuid4(); programme = _programme(institution_id); student = _student(institution_id, programme.id)
    current = _level(institution_id, programme.id, name="Year Two", sequence=2)
    next_level = _level(institution_id, programme.id, name="Clinical Year", sequence=4)
    failed = hierarchy(passed=False)
    monkeypatch.setattr(service, "compute_student_cgpa", lambda *_, **__: _cgpa(student.id, value="1.20"))
    monkeypatch.setattr(service, "_query_published_failed_results", lambda *_, **__: [failed])
    db = Session(student, programme, current, next_level)
    result = service.evaluate_student_progression(db, institution_id=institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.current_level_sequence == 2 and result.next_level_sequence == 4
    assert result.eligible_for_progression and result.has_carryover_courses
    assert result.progression_reason == ProgressionReason.ELIGIBLE and student.current_level == "Year Two"
    next_sql = str(db.statements[3])
    assert "academic_levels.programme_id" in next_sql and "academic_levels.sequence_number" in next_sql


def test_final_level_and_missing_next_level_are_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    institution_id = uuid4(); programme = _programme(institution_id, duration=4); student = _student(institution_id, programme.id)
    monkeypatch.setattr(service, "compute_student_cgpa", lambda *_, **__: _cgpa(student.id))
    monkeypatch.setattr(service, "_query_published_failed_results", lambda *_, **__: [])
    final = _level(institution_id, programme.id, name="Year Two", sequence=4)
    assert service.evaluate_student_progression(Session(student, programme, final, None), institution_id=institution_id, student_id=student.id).progression_reason == ProgressionReason.FINAL_LEVEL_REACHED  # type: ignore[arg-type]
    gap = _level(institution_id, programme.id, name="Year Two", sequence=2)
    assert service.evaluate_student_progression(Session(student, programme, gap, None), institution_id=institution_id, student_id=student.id).progression_reason == ProgressionReason.NEXT_LEVEL_NOT_CONFIGURED  # type: ignore[arg-type]


def test_unresolved_level_and_missing_student_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    institution_id = uuid4(); programme = _programme(institution_id); student = _student(institution_id, programme.id, level="Unknown")
    monkeypatch.setattr(service, "compute_student_cgpa", lambda *_, **__: _cgpa(student.id))
    monkeypatch.setattr(service, "_query_published_failed_results", lambda *_, **__: [])
    result = service.evaluate_student_progression(Session(student, programme, None), institution_id=institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.progression_reason == ProgressionReason.CURRENT_LEVEL_UNRESOLVED and not result.eligible_for_progression
    with pytest.raises(service.AcademicProgressionStudentNotFoundError):
        service.compute_student_academic_standing(Session(), institution_id=institution_id, student_id=uuid4())  # type: ignore[arg-type]


def test_routes_registration_authentication_and_error_mapping() -> None:
    paths = app.openapi()["paths"]
    for suffix in ("academic-standing", "progression", "academic-progress"):
        assert f"/api/v1/students/{{student_id}}/{suffix}" in paths
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    assert academic_progression._map_error(service.AcademicProgressionStudentNotFoundError()).status_code == 404
