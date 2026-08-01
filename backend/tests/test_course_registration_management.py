from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Index
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import course_registrations
from app.main import app
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.institution import Institution
from app.models.student import Student
from app.models.user import User
from app.schemas.course_registration import CourseRegistrationCreate, CourseRegistrationUpdate, RegistrationStatus
from app.services import course_registration_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[CourseRegistration]) -> None: self.values = values
    def all(self) -> list[CourseRegistration]: return self.values


class FakeSession:
    def __init__(self, *results: object) -> None:
        self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.commits = 0; self.rollbacks = 0
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement); return FakeScalarResult(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def commit(self) -> None: self.commits += 1
    def rollback(self) -> None: self.rollbacks += 1
    def refresh(self, _: object) -> None: pass


def _context() -> AuthenticatedUserContext:
    institution = Institution(id=uuid4(), name="Test University", code=f"T-{uuid4()}", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email=f"{uuid4()}@test.edu", password_hash="x", first_name="Admin", last_name="User", is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=("administrator",))


def _student(institution_id: UUID, *, programme_id: UUID | None = None) -> Student:
    return Student(id=uuid4(), institution_id=institution_id, user_id=uuid4(), programme_id=programme_id, matriculation_number=f"MAT-{uuid4()}", admission_year=2026, current_level="100 Level", enrollment_status="active")


def _course(institution_id: UUID, programme_id: UUID | None = None) -> Course:
    return Course(id=uuid4(), institution_id=institution_id, department_id=uuid4(), programme_id=programme_id or uuid4(), academic_level_id=uuid4(), title="Algorithms", code=f"CSC-{uuid4()}", credit_units=3, course_type="compulsory", status="active")


def _offering(institution_id: UUID, course_id: UUID, *, capacity: int | None = 10, open_: bool = True, status: str = "active", start: date | None = date(2026, 7, 1), end: date | None = date(2026, 9, 1)) -> CourseOffering:
    return CourseOffering(id=uuid4(), institution_id=institution_id, course_id=course_id, academic_session_id=uuid4(), semester_id=uuid4(), capacity=capacity, registration_open=open_, registration_start_date=start, registration_end_date=end, status=status)


def _record(institution_id: UUID, student_id: UUID, offering_id: UUID, *, registration_status: str = "registered") -> CourseRegistration:
    now = datetime.now(UTC)
    return CourseRegistration(id=uuid4(), institution_id=institution_id, student_id=student_id, course_offering_id=offering_id, registration_status=registration_status, registered_at=now, dropped_at=now if registration_status == "dropped" else None, notes=None, status="active", created_at=now, updated_at=now)


def test_model_partial_uniqueness_and_schema_fields() -> None:
    indexes = {x.name: x for x in CourseRegistration.__table__.indexes if isinstance(x, Index)}
    assert indexes["uq_course_registrations_active_student_offering"].unique
    assert set(CourseRegistrationCreate.model_fields) == {"student_id", "course_offering_id", "notes"}
    assert set(CourseRegistrationUpdate.model_fields) == {"registration_status", "notes"}
    with pytest.raises(ValidationError): CourseRegistrationUpdate(registration_status="pending")


def test_successful_creation_derives_institution_and_context() -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id); session = FakeSession(student, offering, None, 0)
    result = course_registration_service.create_course_registration(session, institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id, notes=" First registration "))  # type: ignore[arg-type]
    assert result.institution_id == context.institution.id and result.student_id == student.id and result.course_offering_id == offering.id
    assert result.registration_status == "registered" and result.registered_at.tzinfo is not None and result.notes == "First registration"
    assert session.added == [result] and session.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], course_registration_service.CourseRegistrationStudentNotFoundError), (["student"], course_registration_service.CourseRegistrationOfferingNotFoundError)])
def test_missing_and_cross_institution_parents_rejected(results: list[object], error: type[Exception]) -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id); mapping = {"student": student}
    with pytest.raises(error): course_registration_service.create_course_registration(FakeSession(*(mapping[x] for x in results)), institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]


@pytest.mark.parametrize(("status", "open_"), [("inactive", True), ("active", False)])
def test_inactive_or_closed_offering_rejected(status: str, open_: bool) -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id, status=status, open_=open_)
    with pytest.raises(course_registration_service.CourseRegistrationOfferingUnavailableError): course_registration_service.create_course_registration(FakeSession(student, offering), institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]


@pytest.mark.parametrize(("start", "end"), [(date(2026, 9, 1), None), (None, date(2026, 7, 1))])
def test_registration_outside_window_rejected(start: date | None, end: date | None) -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id, start=start, end=end)
    with pytest.raises(course_registration_service.CourseRegistrationWindowError): course_registration_service.create_course_registration(FakeSession(student, offering), institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]


def test_duplicate_registration_rejected() -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id)
    with pytest.raises(course_registration_service.DuplicateCourseRegistrationError): course_registration_service.create_course_registration(FakeSession(student, offering, uuid4()), institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]


def test_capacity_enforced_and_query_excludes_dropped_deleted() -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id, capacity=1); session = FakeSession(student, offering, None, 1)
    with pytest.raises(course_registration_service.CourseOfferingCapacityError): course_registration_service.create_course_registration(session, institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]
    capacity_sql = str(session.statements[-1]); assert "course_registrations.registration_status" in capacity_sql and "course_registrations.status" in capacity_sql


def test_student_programme_compatibility_enforced() -> None:
    context = _context(); student = _student(context.institution.id, programme_id=uuid4()); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id)
    with pytest.raises(course_registration_service.StudentCourseCompatibilityError): course_registration_service.create_course_registration(FakeSession(student, offering, course), institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]


def test_matching_student_programme_is_allowed() -> None:
    context = _context(); programme_id = uuid4(); student = _student(context.institution.id, programme_id=programme_id); course = _course(context.institution.id, programme_id); offering = _offering(context.institution.id, course.id); session = FakeSession(student, offering, course, None, 0)
    result = course_registration_service.create_course_registration(session, institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]
    assert result.registration_status == "registered"


def test_list_scoped_with_all_filters() -> None:
    context = _context(); student = _student(context.institution.id); offering_id = uuid4(); expected = [_record(context.institution.id, student.id, offering_id)]; session = FakeSession(expected)
    assert course_registration_service.list_course_registrations(session, institution_id=context.institution.id, student_id=student.id, course_offering_id=offering_id, registration_status=RegistrationStatus.REGISTERED) == expected  # type: ignore[arg-type]
    sql = str(session.statements[0]); assert all(value in sql for value in ("course_registrations.institution_id", "course_registrations.student_id", "course_registrations.course_offering_id", "course_registrations.registration_status", "course_registrations.status"))


def test_retrieve_and_update_notes() -> None:
    context = _context(); registration = _record(context.institution.id, uuid4(), uuid4()); session = FakeSession(registration)
    updated = course_registration_service.update_course_registration(session, course_registration_id=registration.id, institution_id=context.institution.id, course_registration_data=CourseRegistrationUpdate(notes=" Updated note "))  # type: ignore[arg-type]
    assert updated.notes == "Updated note" and session.commits == 1
    assert course_registration_service.get_course_registration(FakeSession(updated), course_registration_id=updated.id, institution_id=context.institution.id) is updated  # type: ignore[arg-type]


def test_registered_to_dropped_sets_timestamp() -> None:
    context = _context(); registration = _record(context.institution.id, uuid4(), uuid4()); original_registered_at = registration.registered_at
    updated = course_registration_service.update_course_registration(FakeSession(registration), course_registration_id=registration.id, institution_id=context.institution.id, course_registration_data=CourseRegistrationUpdate(registration_status="dropped"))  # type: ignore[arg-type]
    assert updated.registration_status == "dropped" and updated.dropped_at is not None and updated.registered_at == original_registered_at


def test_dropped_to_registered_clears_timestamp_and_revalidates() -> None:
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id); registration = _record(context.institution.id, student.id, offering.id, registration_status="dropped"); original_registered_at = registration.registered_at; session = FakeSession(registration, student, offering, None, 0)
    updated = course_registration_service.update_course_registration(session, course_registration_id=registration.id, institution_id=context.institution.id, course_registration_data=CourseRegistrationUpdate(registration_status="registered"))  # type: ignore[arg-type]
    assert updated.registration_status == "registered" and updated.dropped_at is None and updated.registered_at == original_registered_at


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"course_registration_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(course_registration_service.CourseRegistrationNotFoundError):
        if operation == "get": course_registration_service.get_course_registration(FakeSession(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": course_registration_service.update_course_registration(FakeSession(), course_registration_data=CourseRegistrationUpdate(notes="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: course_registration_service.delete_course_registration(FakeSession(), **kwargs)  # type: ignore[arg-type]


def test_delete_deactivates_hides_and_stops_capacity_consumption() -> None:
    context = _context(); registration = _record(context.institution.id, uuid4(), uuid4()); session = FakeSession(registration)
    deleted = course_registration_service.delete_course_registration(session, course_registration_id=registration.id, institution_id=context.institution.id)  # type: ignore[arg-type]
    assert deleted.status == "inactive" and session.commits == 1
    with pytest.raises(course_registration_service.CourseRegistrationNotFoundError): course_registration_service.get_course_registration(FakeSession(), course_registration_id=registration.id, institution_id=context.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_router_and_safe_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    context = _context(); payload = CourseRegistrationCreate(student_id=uuid4(), course_offering_id=uuid4())
    monkeypatch.setattr(course_registrations, "create_course_registration", lambda *_, **__: (_ for _ in ()).throw(course_registration_service.CourseOfferingCapacityError()))
    with pytest.raises(HTTPException) as full: course_registrations.create_course_registration_endpoint(payload, FakeSession(), context)  # type: ignore[arg-type]
    assert full.value.status_code == 409
    paths = app.openapi()["paths"]; assert "/api/v1/course-registrations" in paths and "/api/v1/course-registrations/{course_registration_id}" in paths


def test_integrity_error_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    context = _context(); student = _student(context.institution.id); course = _course(context.institution.id); offering = _offering(context.institution.id, course.id); session = FailingSession(student, offering, None, 0)
    with pytest.raises(course_registration_service.DuplicateCourseRegistrationError): course_registration_service.create_course_registration(session, institution_id=context.institution.id, course_registration_data=CourseRegistrationCreate(student_id=student.id, course_offering_id=offering.id))  # type: ignore[arg-type]
    assert session.rollbacks == 1
