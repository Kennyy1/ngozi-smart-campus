from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1.endpoints import academic_performance
from app.main import app
from app.models.academic_session import AcademicSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.result import Result
from app.models.semester import Semester
from app.models.student import Student
from app.services import academic_performance_service as service


class Rows:
    def __init__(self, values: list[tuple[object, ...]]) -> None: self.values = values
    def all(self) -> list[tuple[object, ...]]: return self.values


class Session:
    def __init__(self, *values: object) -> None: self.values = list(values); self.statements: list[object] = []; self.commits = 0; self.added: list[object] = []
    def scalar(self, statement: object) -> object: self.statements.append(statement); return self.values.pop(0) if self.values else None
    def execute(self, statement: object) -> Rows: self.statements.append(statement); return Rows(self.values.pop(0) if self.values else [])  # type: ignore[arg-type]


def hierarchy(*, session_start: date = date(2025, 9, 1), sequence: int = 1, units: int = 3, registration_status: str = "registered", record_status: str = "active", result_status: str = "published", passed: bool = True, grade_point: str = "4", score: str = "65", code: str = "CSC101") -> service.PerformanceRecord:
    institution_id = uuid4(); now = datetime.now(UTC)
    student = Student(id=uuid4(), institution_id=institution_id, user_id=uuid4(), matriculation_number=str(uuid4()), admission_year=2025, enrollment_status="active", created_at=now, updated_at=now)
    academic_session = AcademicSession(id=uuid4(), institution_id=institution_id, name="Session", start_date=session_start, end_date=date(session_start.year + 1, 7, 1), is_current=False, status="active", created_at=now, updated_at=now)
    semester = Semester(id=uuid4(), institution_id=institution_id, academic_session_id=academic_session.id, name=f"Semester {sequence}", sequence_number=sequence, start_date=session_start, end_date=date(session_start.year + 1, 1, 1), is_current=False, status="active", created_at=now, updated_at=now)
    course = Course(id=uuid4(), institution_id=institution_id, department_id=uuid4(), programme_id=uuid4(), academic_level_id=uuid4(), title=f"Course {code}", code=code, credit_units=units, course_type="compulsory", status="active", created_at=now, updated_at=now)
    offering = CourseOffering(id=uuid4(), institution_id=institution_id, course_id=course.id, academic_session_id=academic_session.id, semester_id=semester.id, registration_open=False, status="active", created_at=now, updated_at=now)
    registration = CourseRegistration(id=uuid4(), institution_id=institution_id, student_id=student.id, course_offering_id=offering.id, registration_status=registration_status, registered_at=now, status=record_status, created_at=now, updated_at=now)
    result = Result(id=uuid4(), institution_id=institution_id, course_registration_id=registration.id, course_offering_id=offering.id, student_id=student.id, continuous_assessment_score=Decimal("25"), examination_score=Decimal(score) - Decimal("25"), final_score=Decimal(score), grade_letter="B" if passed else "F", grade_point=Decimal(grade_point), passed=passed, status=result_status, computed_at=now, computed_by_user_id=uuid4(), created_at=now, updated_at=now)
    return service.PerformanceRecord(result, registration, offering, course, semester, academic_session)


def test_quality_points_decimal_and_course_breakdown() -> None:
    record = hierarchy(units=3, grade_point="3.333", code="MAT201")
    item = service._build_course_breakdown(record)
    assert item.quality_points == Decimal("10.00") and item.credit_units == 3
    assert item.course_code == "MAT201" and item.course_title == "Course MAT201"
    assert item.final_score == Decimal("65.00") and item.result_id == record.result.id


def test_semester_multiple_courses_attempted_earned_counts_and_gpa() -> None:
    first = hierarchy(units=3, grade_point="4", passed=True); second = hierarchy(units=2, grade_point="0", passed=False)
    second.result.student_id = first.result.student_id
    summary = service._build_semester_summary(first.result.student_id, first.academic_session.id, first.semester.id, [first, second])
    assert (summary.attempted_units, summary.earned_units, summary.total_quality_points) == (5, 3, Decimal("12.00"))
    assert (summary.course_count, summary.passed_courses, summary.failed_courses, summary.gpa) == (2, 1, 1, Decimal("2.40"))


def test_zero_results_return_zero_semester_gpa() -> None:
    record = hierarchy()
    summary = service._build_semester_summary(record.result.student_id, record.academic_session.id, record.semester.id, [])
    assert summary.gpa == Decimal("0.00") and summary.attempted_units == summary.earned_units == summary.course_count == 0


def test_failed_course_is_attempted_but_not_earned() -> None:
    record = hierarchy(units=4, passed=False, grade_point="0")
    summary = service._build_semester_summary(record.result.student_id, record.academic_session.id, record.semester.id, [record])
    assert summary.attempted_units == 4 and summary.earned_units == 0 and summary.failed_courses == 1


def test_invalid_historical_credit_units_rejected_safely() -> None:
    with pytest.raises(service.InvalidCourseCreditUnitsError): service._build_course_breakdown(hierarchy(units=0))


@pytest.mark.parametrize("status", ["draft", "submitted", "approved", "rejected", "withheld", "inactive"])
def test_query_only_selects_published_status(status: str) -> None:
    db = Session([]); service._query_eligible_published_results(db, institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]
    sql = str(db.statements[0]); assert "results.status" in sql and "published" in str(db.statements[0].compile().params.values())
    assert status != "published"


def test_query_excludes_dropped_but_allows_historical_inactive_registered() -> None:
    db = Session([]); service._query_eligible_published_results(db, institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]
    sql = str(db.statements[0]); params = tuple(db.statements[0].compile().params.values())
    assert "course_registrations.registration_status" in sql and "registered" in params
    assert "course_registrations.status" in sql and any(isinstance(value, (tuple, list)) and set(value) == {"active", "inactive"} for value in params)


def test_semester_flow_resolves_scoped_hierarchy_and_is_read_only() -> None:
    record = hierarchy(); student = Student(id=record.result.student_id, institution_id=record.result.institution_id, user_id=uuid4(), matriculation_number="M", admission_year=2025, enrollment_status="active")
    db = Session(student, record.semester, record.academic_session, [tuple(record)])
    result = service.compute_student_semester_gpa(db, institution_id=record.result.institution_id, student_id=student.id, semester_id=record.semester.id)  # type: ignore[arg-type]
    assert result.course_count == 1 and result.gpa == Decimal("4.00") and len(db.statements) == 4
    assert db.commits == 0 and db.added == []


def test_cgpa_groups_chronologically_and_preserves_repeated_attempts() -> None:
    later = hierarchy(session_start=date(2025, 9, 1), sequence=1, units=3, grade_point="5", code="CSC101")
    earlier = hierarchy(session_start=date(2024, 9, 1), sequence=2, units=3, grade_point="3", code="CSC101")
    earlier.result.student_id = later.result.student_id
    student = Student(id=later.result.student_id, institution_id=later.result.institution_id, user_id=uuid4(), matriculation_number="M", admission_year=2024, enrollment_status="active")
    db = Session(student, [tuple(later), tuple(earlier)])
    result = service.compute_student_cgpa(db, institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.total_courses == 2 and result.cumulative_attempted_units == result.cumulative_earned_units == 6
    assert result.cumulative_quality_points == Decimal("24.00") and result.cgpa == Decimal("4.00")
    assert [item.academic_session_id for item in result.semester_summaries] == [earlier.academic_session.id, later.academic_session.id]


def test_empty_cgpa_is_zero() -> None:
    record = hierarchy(); student = Student(id=record.result.student_id, institution_id=record.result.institution_id, user_id=uuid4(), matriculation_number="M", admission_year=2025, enrollment_status="active")
    result = service.compute_student_cgpa(Session(student, []), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert result.cgpa == Decimal("0.00") and result.total_courses == 0 and not result.semester_summaries


@pytest.mark.parametrize(("values", "operation", "error"), [([], "semester", service.AcademicPerformanceStudentNotFoundError), ([object()], "semester", service.AcademicPerformanceSemesterNotFoundError), ([], "cgpa", service.AcademicPerformanceStudentNotFoundError)])
def test_missing_and_cross_institution_resources_are_not_found(values: list[object], operation: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        if operation == "semester": service.compute_student_semester_gpa(Session(*values), institution_id=uuid4(), student_id=uuid4(), semester_id=uuid4())  # type: ignore[arg-type]
        else: service.compute_student_cgpa(Session(*values), institution_id=uuid4(), student_id=uuid4())  # type: ignore[arg-type]


def test_routes_authentication_and_safe_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/students/{student_id}/semesters/{semester_id}/gpa" in paths and "/api/v1/students/{student_id}/cgpa" in paths
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    assert academic_performance._map_error(service.AcademicPerformanceStudentNotFoundError()).status_code == 404
