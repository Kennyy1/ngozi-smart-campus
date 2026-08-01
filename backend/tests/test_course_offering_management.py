from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import course_offerings
from app.main import app
from app.models.academic_session import AcademicSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.institution import Institution
from app.models.semester import Semester
from app.models.user import User
from app.schemas.course_offering import CourseOfferingCreate, CourseOfferingUpdate
from app.services import course_offering_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[CourseOffering]) -> None: self.values = values
    def all(self) -> list[CourseOffering]: return self.values


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


def _parents(institution_id: UUID) -> tuple[Course, AcademicSession, Semester]:
    course = Course(id=uuid4(), institution_id=institution_id, department_id=uuid4(), programme_id=uuid4(), academic_level_id=uuid4(), title="Algorithms", code="CSC201", credit_units=3, course_type="compulsory", status="active")
    academic_session = AcademicSession(id=uuid4(), institution_id=institution_id, name="2026/27", start_date=date(2026, 9, 1), end_date=date(2027, 7, 31), is_current=True, status="active")
    semester = Semester(id=uuid4(), institution_id=institution_id, academic_session_id=academic_session.id, name="First Semester", sequence_number=1, start_date=date(2026, 9, 1), end_date=date(2027, 1, 31), is_current=True, status="active")
    return course, academic_session, semester


def _payload(course: Course, academic_session: AcademicSession, semester: Semester) -> CourseOfferingCreate:
    return CourseOfferingCreate(course_id=course.id, academic_session_id=academic_session.id, semester_id=semester.id, capacity=100, registration_open=False, registration_start_date=date(2026, 9, 1), registration_end_date=date(2026, 9, 30), description=" Registration period ")


def _record(institution_id: UUID, course: Course, academic_session: AcademicSession, semester: Semester) -> CourseOffering:
    now = datetime.now(UTC)
    return CourseOffering(id=uuid4(), institution_id=institution_id, course_id=course.id, academic_session_id=academic_session.id, semester_id=semester.id, capacity=100, registration_open=False, registration_start_date=date(2026, 9, 1), registration_end_date=date(2026, 9, 30), status="active", description=None, created_at=now, updated_at=now)


def test_model_constraints_and_request_schema() -> None:
    unique = {tuple(c.name for c in x.columns) for x in CourseOffering.__table__.constraints if isinstance(x, UniqueConstraint)}
    checks = {str(x.sqltext) for x in CourseOffering.__table__.constraints if isinstance(x, CheckConstraint)}
    assert ("course_id", "academic_session_id", "semester_id") in unique
    assert "capacity IS NULL OR capacity > 0" in checks
    assert any("registration_start_date < registration_end_date" in check for check in checks)
    assert "institution_id" not in CourseOfferingCreate.model_fields and "institution_id" not in CourseOfferingUpdate.model_fields


def test_successful_creation_derives_institution() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); session = FakeSession(course, academic_session, semester, None)
    result = course_offering_service.create_course_offering(session, institution_id=context.institution.id, course_offering_data=_payload(course, academic_session, semester))  # type: ignore[arg-type]
    assert result.institution_id == context.institution.id and result.description == "Registration period" and result.registration_open is False
    assert session.added == [result] and session.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], course_offering_service.CourseOfferingCourseNotFoundError), (["course"], course_offering_service.CourseOfferingAcademicSessionNotFoundError), (["course", "session"], course_offering_service.CourseOfferingSemesterNotFoundError)])
def test_missing_and_cross_institution_parents_rejected(results: list[object], error: type[Exception]) -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); mapping = {"course": course, "session": academic_session}
    with pytest.raises(error): course_offering_service.create_course_offering(FakeSession(*(mapping[x] for x in results)), institution_id=context.institution.id, course_offering_data=_payload(course, academic_session, semester))  # type: ignore[arg-type]


def test_semester_session_mismatch_rejected() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); semester.academic_session_id = uuid4()
    with pytest.raises(course_offering_service.CourseOfferingHierarchyMismatchError): course_offering_service.create_course_offering(FakeSession(course, academic_session, semester), institution_id=context.institution.id, course_offering_data=_payload(course, academic_session, semester))  # type: ignore[arg-type]


def test_duplicate_offering_rejected() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id)
    with pytest.raises(course_offering_service.DuplicateCourseOfferingError): course_offering_service.create_course_offering(FakeSession(course, academic_session, semester, uuid4()), institution_id=context.institution.id, course_offering_data=_payload(course, academic_session, semester))  # type: ignore[arg-type]


@pytest.mark.parametrize("capacity", [0, -1])
def test_non_positive_capacity_rejected(capacity: int) -> None:
    course, academic_session, semester = _parents(uuid4())
    with pytest.raises(ValidationError): CourseOfferingCreate(course_id=course.id, academic_session_id=academic_session.id, semester_id=semester.id, capacity=capacity)


@pytest.mark.parametrize(("start", "end"), [(date(2026, 9, 1), date(2026, 9, 1)), (date(2026, 10, 1), date(2026, 9, 1))])
def test_invalid_registration_order_rejected(start: date, end: date) -> None:
    course, academic_session, semester = _parents(uuid4())
    with pytest.raises(ValidationError): CourseOfferingCreate(course_id=course.id, academic_session_id=academic_session.id, semester_id=semester.id, registration_start_date=start, registration_end_date=end)


@pytest.mark.parametrize(("start", "end"), [(date(2026, 8, 31), date(2026, 9, 30)), (date(2026, 9, 1), date(2027, 2, 1))])
def test_registration_dates_outside_session_or_semester_rejected(start: date, end: date) -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); payload = _payload(course, academic_session, semester).model_copy(update={"registration_start_date": start, "registration_end_date": end})
    with pytest.raises(course_offering_service.InvalidRegistrationWindowError): course_offering_service.create_course_offering(FakeSession(course, academic_session, semester), institution_id=context.institution.id, course_offering_data=payload)  # type: ignore[arg-type]


def test_list_scoped_with_all_filters() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); expected = [_record(context.institution.id, course, academic_session, semester)]; session = FakeSession(expected)
    assert course_offering_service.list_course_offerings(session, institution_id=context.institution.id, course_id=course.id, academic_session_id=academic_session.id, semester_id=semester.id, registration_open=False, status="active") == expected  # type: ignore[arg-type]
    sql = str(session.statements[0]); assert all(value in sql for value in ("course_offerings.institution_id", "course_offerings.course_id", "course_offerings.academic_session_id", "course_offerings.semester_id", "course_offerings.registration_open", "course_offerings.status"))


def test_retrieve_and_update_revalidate_hierarchy() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); record = _record(context.institution.id, course, academic_session, semester); session = FakeSession(record, course, academic_session, semester, None)
    updated = course_offering_service.update_course_offering(session, course_offering_id=record.id, institution_id=context.institution.id, course_offering_data=CourseOfferingUpdate(capacity=150, registration_open=True, registration_end_date=date(2026, 10, 15)))  # type: ignore[arg-type]
    assert updated.capacity == 150 and updated.registration_open and updated.registration_end_date == date(2026, 10, 15) and session.commits == 1
    assert course_offering_service.get_course_offering(FakeSession(updated), course_offering_id=updated.id, institution_id=context.institution.id) is updated  # type: ignore[arg-type]


def test_update_hierarchy_mismatch_rejected() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); record = _record(context.institution.id, course, academic_session, semester); semester.academic_session_id = uuid4()
    with pytest.raises(course_offering_service.CourseOfferingHierarchyMismatchError): course_offering_service.update_course_offering(FakeSession(record, course, academic_session, semester), course_offering_id=record.id, institution_id=context.institution.id, course_offering_data=CourseOfferingUpdate(capacity=200))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"course_offering_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(course_offering_service.CourseOfferingNotFoundError):
        if operation == "get": course_offering_service.get_course_offering(FakeSession(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": course_offering_service.update_course_offering(FakeSession(), course_offering_data=CourseOfferingUpdate(capacity=10), **kwargs)  # type: ignore[arg-type]
        else: course_offering_service.delete_course_offering(FakeSession(), **kwargs)  # type: ignore[arg-type]


def test_delete_deactivates_and_hides_offering() -> None:
    context = _context(); course, academic_session, semester = _parents(context.institution.id); record = _record(context.institution.id, course, academic_session, semester); session = FakeSession(record)
    deleted = course_offering_service.delete_course_offering(session, course_offering_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]
    assert deleted.status == "inactive" and session.commits == 1
    with pytest.raises(course_offering_service.CourseOfferingNotFoundError): course_offering_service.get_course_offering(FakeSession(), course_offering_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_router_and_safe_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    context = _context(); course, academic_session, semester = _parents(context.institution.id)
    monkeypatch.setattr(course_offerings, "create_course_offering", lambda *_, **__: (_ for _ in ()).throw(course_offering_service.DuplicateCourseOfferingError()))
    with pytest.raises(HTTPException) as duplicate: course_offerings.create_course_offering_endpoint(_payload(course, academic_session, semester), FakeSession(), context)  # type: ignore[arg-type]
    assert duplicate.value.status_code == 409
    paths = app.openapi()["paths"]; assert "/api/v1/course-offerings" in paths and "/api/v1/course-offerings/{course_offering_id}" in paths


def test_integrity_error_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    context = _context(); course, academic_session, semester = _parents(context.institution.id); session = FailingSession(course, academic_session, semester, None)
    with pytest.raises(course_offering_service.DuplicateCourseOfferingError): course_offering_service.create_course_offering(session, institution_id=context.institution.id, course_offering_data=_payload(course, academic_session, semester))  # type: ignore[arg-type]
    assert session.rollbacks == 1
