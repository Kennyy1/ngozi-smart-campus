from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.api.v1.endpoints import attendance_analytics
from app.main import app
from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.institution import Institution
from app.models.student import Student
from app.models.user import User
from app.services import attendance_analytics_service as service
from app.services.authentication import AuthenticatedUserContext


class Result:
    def __init__(self, values: list[object]) -> None: self.values = values
    def all(self) -> list[object]: return self.values


class Session:
    def __init__(self, *results: object) -> None:
        self.results = list(results); self.statements: list[object] = []; self.commits = 0; self.added: list[object] = []
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> Result:
        self.statements.append(statement); return Result(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def commit(self) -> None: self.commits += 1
    def add(self, item: object) -> None: self.added.append(item)


def context() -> AuthenticatedUserContext:
    institution = Institution(id=uuid4(), name="University", code=f"U-{uuid4()}", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email=f"{uuid4()}@test.edu", password_hash="x", first_name="Admin", last_name="User", is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=("administrator",))


def offering(ctx: AuthenticatedUserContext) -> CourseOffering:
    return CourseOffering(id=uuid4(), institution_id=ctx.institution.id, course_id=uuid4(), academic_session_id=uuid4(), semester_id=uuid4(), registration_open=False, status="active")


def student(ctx: AuthenticatedUserContext, label: str) -> Student:
    user = User(id=uuid4(), institution_id=ctx.institution.id, email=f"{label}@test.edu", password_hash="x", first_name=label, last_name="Student", is_active=True, is_verified=True)
    item = Student(id=uuid4(), institution_id=ctx.institution.id, user_id=user.id, matriculation_number=f"MAT-{label}", admission_year=2026, current_level="100 Level", enrollment_status="active")
    item.user = user
    return item


def registration(ctx: AuthenticatedUserContext, course_offering: CourseOffering, learner: Student, *, registration_status: str = "registered", status: str = "active") -> CourseRegistration:
    now = datetime.now(UTC)
    item = CourseRegistration(id=uuid4(), institution_id=ctx.institution.id, student_id=learner.id, course_offering_id=course_offering.id, registration_status=registration_status, registered_at=now, dropped_at=None, status=status, created_at=now, updated_at=now)
    item.student = learner
    return item


def class_session(ctx: AuthenticatedUserContext, course_offering: CourseOffering, *, status: str = "completed", future: bool = False) -> ClassSession:
    now = datetime.now(UTC)
    return ClassSession(id=uuid4(), institution_id=ctx.institution.id, course_offering_id=course_offering.id, lecturer_assignment_id=uuid4(), session_date=date.today() + timedelta(days=1 if future else -1), start_time=time(9), end_time=time(10), session_type="lecture", topic="Topic", venue="A1", delivery_mode="physical", status=status, created_at=now, updated_at=now)


def attendance(ctx: AuthenticatedUserContext, meeting: ClassSession, enrolled: CourseRegistration, attendance_status: str, *, status: str = "active") -> AttendanceRecord:
    now = datetime.now(UTC)
    return AttendanceRecord(id=uuid4(), institution_id=ctx.institution.id, class_session_id=meeting.id, course_registration_id=enrolled.id, attendance_status=attendance_status, check_in_time=now if attendance_status in ("present", "late") else None, recorded_by_user_id=ctx.user.id, remarks=None, status=status, created_at=now, updated_at=now)


def test_registration_summary_counts_statuses_unmarked_excused_and_percentage() -> None:
    ctx = context(); course_offering = offering(ctx); learner = student(ctx, "Ada"); enrolled = registration(ctx, course_offering, learner)
    meetings = [class_session(ctx, course_offering) for _ in range(6)]
    records = [attendance(ctx, meetings[0], enrolled, "present"), attendance(ctx, meetings[1], enrolled, "late"), attendance(ctx, meetings[2], enrolled, "absent"), attendance(ctx, meetings[3], enrolled, "excused")]
    db = Session(enrolled, meetings, records)
    result = service.get_course_registration_attendance_summary(db, institution_id=ctx.institution.id, course_registration_id=enrolled.id)  # type: ignore[arg-type]
    assert (result.present_count, result.late_count, result.absent_count, result.excused_count) == (1, 1, 1, 1)
    assert result.total_sessions == 6 and result.recorded_sessions == 4 and result.unmarked_count == 2
    assert result.effective_session_count == 3 and result.attendance_percentage == 66.67
    assert result.minimum_required_percentage == 75.0 and not result.meets_requirement
    assert db.commits == 0 and db.added == []


def test_custom_threshold_and_rounding() -> None:
    ctx = context(); course_offering = offering(ctx); enrolled = registration(ctx, course_offering, student(ctx, "Ben")); meetings = [class_session(ctx, course_offering) for _ in range(3)]
    records = [attendance(ctx, meetings[0], enrolled, "present"), attendance(ctx, meetings[1], enrolled, "absent"), attendance(ctx, meetings[2], enrolled, "absent")]
    result = service.get_course_registration_attendance_summary(Session(enrolled, meetings, records), institution_id=ctx.institution.id, course_registration_id=enrolled.id, minimum_percentage=30.0)  # type: ignore[arg-type]
    assert result.attendance_percentage == 33.33 and result.meets_requirement


@pytest.mark.parametrize("minimum", [-0.01, 100.01])
def test_invalid_threshold_rejected(minimum: float) -> None:
    with pytest.raises(service.InvalidMinimumPercentageError):
        service.get_course_registration_attendance_summary(Session(), institution_id=uuid4(), course_registration_id=uuid4(), minimum_percentage=minimum)  # type: ignore[arg-type]


def test_no_sessions_and_no_records_return_zero_summary() -> None:
    ctx = context(); course_offering = offering(ctx); enrolled = registration(ctx, course_offering, student(ctx, "Chi"))
    result = service.get_course_registration_attendance_summary(Session(enrolled, []), institution_id=ctx.institution.id, course_registration_id=enrolled.id)  # type: ignore[arg-type]
    assert result.total_sessions == result.recorded_sessions == result.effective_session_count == 0
    assert result.unmarked_count == 0 and result.attendance_percentage == 0.0


@pytest.mark.parametrize("status", ["scheduled", "cancelled", "postponed", "inactive"])
def test_non_completed_sessions_are_excluded(status: str) -> None:
    ctx = context(); course_offering = offering(ctx); enrolled = registration(ctx, course_offering, student(ctx, status)); excluded = class_session(ctx, course_offering, status=status)
    result = service.get_course_registration_attendance_summary(Session(enrolled, []), institution_id=ctx.institution.id, course_registration_id=enrolled.id)  # type: ignore[arg-type]
    assert result.total_sessions == 0 and not service._is_eligible_session(excluded)


def test_future_completed_session_is_excluded_by_query() -> None:
    ctx = context(); course_offering = offering(ctx); future = class_session(ctx, course_offering, future=True); db = Session([])
    assert service._query_eligible_completed_sessions(db, institution_id=ctx.institution.id, course_offering_ids=[course_offering.id]) == []  # type: ignore[arg-type]
    sql = str(db.statements[0]); assert "class_sessions.status" in sql and "class_sessions.session_date" in sql and future.session_date > date.today()


def test_inactive_attendance_is_excluded_from_calculation() -> None:
    ctx = context(); course_offering = offering(ctx); enrolled = registration(ctx, course_offering, student(ctx, "Dee")); meeting = class_session(ctx, course_offering)
    inactive = attendance(ctx, meeting, enrolled, "present", status="inactive")
    result = service._build_registration_summary(enrolled, [meeting], [inactive], 75.0)
    assert result.recorded_sessions == 0 and result.unmarked_count == 1 and result.attendance_percentage == 0.0


def test_class_session_summary_counts_eligible_marked_unmarked_and_rate() -> None:
    ctx = context(); course_offering = offering(ctx); meeting = class_session(ctx, course_offering)
    registrations = [registration(ctx, course_offering, student(ctx, name)) for name in ("Efe", "Femi", "Gina")]
    records = [attendance(ctx, meeting, registrations[0], "present"), attendance(ctx, meeting, registrations[1], "absent")]
    result = service.get_class_session_attendance_summary(Session(meeting, registrations, records), institution_id=ctx.institution.id, class_session_id=meeting.id)  # type: ignore[arg-type]
    assert result.eligible_registration_count == 3 and result.marked_count == 2 and result.unmarked_count == 1
    assert result.present_count == 1 and result.absent_count == 1 and result.attendance_rate == 33.33


def test_registration_query_excludes_dropped_and_inactive() -> None:
    db = Session([])
    service._query_active_registered_registrations(db, institution_id=uuid4(), course_offering_ids=None)  # type: ignore[arg-type]
    sql = str(db.statements[0]); assert "registration_status" in sql and "course_registrations.status" in sql


def test_course_offering_aggregate_details_threshold_counts_and_query_bound() -> None:
    ctx = context(); course_offering = offering(ctx); first = registration(ctx, course_offering, student(ctx, "Hauwa")); second = registration(ctx, course_offering, student(ctx, "Ikenna"))
    completed = [class_session(ctx, course_offering) for _ in range(2)]; scheduled = class_session(ctx, course_offering, status="scheduled")
    records = [attendance(ctx, completed[0], first, "present"), attendance(ctx, completed[1], first, "present"), attendance(ctx, completed[0], second, "absent")]
    db = Session(course_offering, completed + [scheduled], [first, second], records)
    result = service.get_course_offering_attendance_summary(db, institution_id=ctx.institution.id, course_offering_id=course_offering.id, include_students=True)  # type: ignore[arg-type]
    assert result.total_class_sessions == 3 and result.completed_class_sessions == 2
    assert result.active_registration_count == 2 and result.attendance_record_count == 3
    assert result.average_attendance_percentage == 50.0 and result.students_meeting_requirement == 1 and result.students_below_requirement == 1
    assert result.student_summaries is not None and len(result.student_summaries) == 2 and len(db.statements) == 4


def test_course_offering_student_details_omitted_by_default() -> None:
    ctx = context(); course_offering = offering(ctx)
    result = service.get_course_offering_attendance_summary(Session(course_offering, [], []), institution_id=ctx.institution.id, course_offering_id=course_offering.id)  # type: ignore[arg-type]
    assert result.student_summaries is None and result.average_attendance_percentage == 0.0
    dumped = result.model_dump(exclude_none=True); assert "student_summaries" not in dumped


def test_at_risk_filters_compliant_sorts_and_builds_names() -> None:
    ctx = context(); course_offering = offering(ctx); low = registration(ctx, course_offering, student(ctx, "Low")); high = registration(ctx, course_offering, student(ctx, "High")); middle = registration(ctx, course_offering, student(ctx, "Middle"))
    meetings = [class_session(ctx, course_offering) for _ in range(2)]
    records = [attendance(ctx, meetings[0], high, "present"), attendance(ctx, meetings[1], high, "present"), attendance(ctx, meetings[0], middle, "present"), attendance(ctx, meetings[1], middle, "absent"), attendance(ctx, meetings[0], low, "absent"), attendance(ctx, meetings[1], low, "absent")]
    db = Session(course_offering, [low, high, middle], meetings, records)
    result = service.list_at_risk_course_registrations(db, institution_id=ctx.institution.id, course_offering_id=course_offering.id)  # type: ignore[arg-type]
    assert result.total_at_risk == 2 and [item.attendance_percentage for item in result.items] == [0.0, 50.0]
    assert result.items[0].student_name == "Low Student" and result.items[1].shortfall_percentage == 25.0
    assert all(item.course_offering_id == course_offering.id for item in result.items) and len(db.statements) == 4


@pytest.mark.parametrize(("operation", "error"), [("registration", service.AttendanceAnalyticsRegistrationNotFoundError), ("session", service.AttendanceAnalyticsClassSessionNotFoundError), ("offering", service.AttendanceAnalyticsCourseOfferingNotFoundError)])
def test_missing_and_cross_institution_resources_are_not_found(operation: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        if operation == "registration": service.get_course_registration_attendance_summary(Session(), institution_id=uuid4(), course_registration_id=uuid4())  # type: ignore[arg-type]
        elif operation == "session": service.get_class_session_attendance_summary(Session(), institution_id=uuid4(), class_session_id=uuid4())  # type: ignore[arg-type]
        else: service.get_course_offering_attendance_summary(Session(), institution_id=uuid4(), course_offering_id=uuid4())  # type: ignore[arg-type]


def test_unauthenticated_routes_registered_threshold_schema_and_safe_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    paths = app.openapi()["paths"]
    expected = {"/api/v1/course-registrations/{course_registration_id}/attendance-summary", "/api/v1/class-sessions/{class_session_id}/attendance-summary", "/api/v1/course-offerings/{course_offering_id}/attendance-summary", "/api/v1/attendance-analytics/at-risk"}
    assert expected.issubset(paths)
    parameter = next(item for item in paths["/api/v1/attendance-analytics/at-risk"]["get"]["parameters"] if item["name"] == "minimum_percentage")
    assert parameter["schema"]["minimum"] == 0 and parameter["schema"]["maximum"] == 100
    monkeypatch.setattr(attendance_analytics, "get_course_registration_attendance_summary", lambda *_, **__: (_ for _ in ()).throw(service.AttendanceAnalyticsRegistrationNotFoundError()))
    with pytest.raises(HTTPException) as mapped: attendance_analytics.registration_summary_endpoint(uuid4(), Session(), context())  # type: ignore[arg-type]
    assert mapped.value.status_code == 404
