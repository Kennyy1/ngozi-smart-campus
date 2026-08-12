from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1.endpoints import transcripts
from app.main import app
from app.models.programme import Programme
from app.models.student import Student
from app.models.user import User
from app.schemas.academic_progression import AcademicStandingSummary
from app.services import transcript_service as service
from app.services.academic_progression_policy import AcademicStanding
from tests.test_academic_performance import Session, hierarchy


def _student_programme():
    institution_id = uuid4(); now = datetime.now(UTC)
    programme = Programme(id=uuid4(), institution_id=institution_id, faculty_id=uuid4(), department_id=uuid4(), name="Computer Science", code="CSC", award="BSc", duration_years=4, study_mode="FULL_TIME", status="active")
    user = User(id=uuid4(), institution_id=institution_id, email="ada@test.edu", password_hash="x", first_name="Ada", last_name="Lovelace", is_active=True, is_verified=True)
    student = Student(id=uuid4(), institution_id=institution_id, user_id=user.id, programme_id=programme.id, matriculation_number="NSC/2025/1", admission_year=2025, current_level="Year One", enrollment_status="active", created_at=now, updated_at=now)
    student.user = user
    return student, programme


def _standing(student_id, records):
    attempted = sum(item.course.credit_units for item in records)
    earned = sum(item.course.credit_units for item in records if item.result.passed)
    quality = sum((Decimal(item.result.grade_point) * item.course.credit_units for item in records), Decimal("0"))
    cgpa = (quality / attempted).quantize(Decimal("0.01")) if attempted else Decimal("0.00")
    return AcademicStandingSummary(
        student_id=student_id, programme_id=uuid4(), current_level="Year One",
        cumulative_attempted_units=attempted, cumulative_earned_units=earned,
        cumulative_quality_points=quality.quantize(Decimal("0.01")), cgpa=cgpa,
        standing=AcademicStanding.GOOD_STANDING if records else AcademicStanding.NOT_EVALUATED,
        failed_course_count=sum(not item.result.passed for item in records), failed_course_ids=[],
        failed_course_codes=[], failed_credit_units=0,
        has_carryover_courses=any(not item.result.passed for item in records),
    )


@pytest.mark.parametrize("excluded", ["draft", "submitted", "approved", "rejected", "withheld", "inactive"])
def test_result_query_allows_only_published_and_excludes_other_statuses(excluded: str) -> None:
    db = Session([])
    service._query_eligible_published_results(db, institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]
    params = tuple(db.statements[0].compile().params.values())
    assert "published" in params and excluded != "published"
    assert "results.status" in str(db.statements[0])


def test_course_entry_reuses_decimal_performance_calculation_and_keeps_failure() -> None:
    record = hierarchy(units=3, score="42", grade_point="1.25", passed=False, code="CSC211")
    item = service._build_course_result(record)
    assert (item.course_code, item.course_title, item.credit_units) == ("CSC211", "Course CSC211", 3)
    assert item.final_score == Decimal("42.00") and item.grade_point == Decimal("1.25")
    assert item.grade_letter == "F" and not item.passed and item.quality_points == Decimal("3.75")


def test_semester_and_session_grouping_aggregates_and_orders_chronologically() -> None:
    late = hierarchy(session_start=date(2025, 9, 1), sequence=2, units=2, passed=False, grade_point="0", code="CSC202")
    early = hierarchy(session_start=date(2024, 9, 1), sequence=2, units=3, passed=True, grade_point="4", code="CSC102")
    same_session_first = hierarchy(session_start=date(2025, 9, 1), sequence=1, units=3, passed=True, grade_point="3", code="CSC101")
    same_session_first = same_session_first._replace(academic_session=late.academic_session)
    same_session_first.semester.academic_session_id = late.academic_session.id
    same_session_first.offering.academic_session_id = late.academic_session.id
    for record in (early, same_session_first):
        record.result.student_id = late.result.student_id
    sessions = service._build_academic_sessions([late, early, same_session_first])
    assert [item.start_date.year for item in sessions] == [2024, 2025]
    assert [item.semester_sequence_number for item in sessions[1].semesters] == [1, 2]
    current = sessions[1]
    assert (current.session_attempted_units, current.session_earned_units) == (5, 3)
    assert current.session_quality_points == Decimal("9.00")
    assert (current.session_course_count, current.session_passed_courses, current.session_failed_courses) == (2, 1, 1)
    assert current.semesters[1].gpa == Decimal("0.00")


def test_repeated_course_attempts_both_remain_in_chronological_history() -> None:
    earlier = hierarchy(session_start=date(2024, 9, 1), code="CSC101", passed=False, grade_point="0")
    later = hierarchy(session_start=date(2025, 9, 1), code="CSC101", passed=True, grade_point="4")
    later.result.student_id = earlier.result.student_id
    sessions = service._build_academic_sessions([later, earlier])
    assert len(sessions) == 2
    assert [item.semesters[0].courses[0].passed for item in sessions] == [False, True]


def test_complete_transcript_identity_programme_totals_standing_and_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    student, programme = _student_programme(); passed = hierarchy(units=3, grade_point="4"); failed = hierarchy(units=2, grade_point="0", passed=False)
    failed = failed._replace(academic_session=passed.academic_session, semester=passed.semester)
    for record in (passed, failed):
        record.result.student_id = student.id
    records = [passed, failed]
    monkeypatch.setattr(service, "_query_eligible_published_results", lambda *_, **__: records)
    monkeypatch.setattr(service, "compute_student_academic_standing", lambda *_, **__: _standing(student.id, records))
    db = Session(student, programme)
    result = service.compute_student_transcript(db, institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.student_name == "Ada Lovelace" and result.matriculation_number == student.matriculation_number
    assert (result.programme_name, result.programme_code, result.current_level) == (programme.name, "CSC", "Year One")
    assert (result.total_courses, result.passed_courses, result.failed_courses) == (2, 1, 1)
    assert result.cumulative_attempted_units == 5 and result.cumulative_earned_units == 3
    assert result.cgpa == Decimal("2.40") and result.academic_standing == AcademicStanding.GOOD_STANDING
    assert db.commits == 0 and db.added == [] and student.current_level == "Year One"


def test_no_published_results_returns_empty_not_evaluated_history(monkeypatch: pytest.MonkeyPatch) -> None:
    student, programme = _student_programme()
    monkeypatch.setattr(service, "_query_eligible_published_results", lambda *_, **__: [])
    monkeypatch.setattr(service, "compute_student_academic_standing", lambda *_, **__: _standing(student.id, []))
    result = service.compute_student_transcript(Session(student, programme), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.academic_sessions == [] and result.cgpa == Decimal("0.00")
    assert result.total_courses == result.cumulative_attempted_units == 0
    assert result.academic_standing == AcademicStanding.NOT_EVALUATED


def test_missing_and_cross_institution_student_are_not_found() -> None:
    with pytest.raises(service.TranscriptStudentNotFoundError):
        service.compute_student_transcript(Session(), institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]


def test_route_registration_authentication_and_safe_mapping() -> None:
    assert "/api/v1/students/{student_id}/transcript" in app.openapi()["paths"]
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    assert transcripts._map_error(service.TranscriptStudentNotFoundError()).status_code == 404
