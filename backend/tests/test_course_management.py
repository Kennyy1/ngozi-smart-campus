from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import courses
from app.main import app
from app.models.academic_level import AcademicLevel
from app.models.course import Course
from app.models.department import Department
from app.models.institution import Institution
from app.models.programme import Programme
from app.models.user import User
from app.schemas.course import CourseCreate, CourseType, CourseUpdate
from app.services import course_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[Course]) -> None: self.values = values
    def all(self) -> list[Course]: return self.values


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


def _hierarchy(institution_id: UUID) -> tuple[Department, Programme, AcademicLevel]:
    department = Department(id=uuid4(), institution_id=institution_id, faculty_id=uuid4(), name="Computing", code="CMP", status="active")
    programme = Programme(id=uuid4(), institution_id=institution_id, faculty_id=department.faculty_id, department_id=department.id, name="Computer Science", code="CSC", award="BSc", duration_years=4, study_mode="FULL_TIME", status="active")
    level = AcademicLevel(id=uuid4(), institution_id=institution_id, programme_id=programme.id, name="100 Level", code="100", sequence_number=1, status="active")
    return department, programme, level


def _payload(department: Department, programme: Programme, level: AcademicLevel) -> CourseCreate:
    return CourseCreate(department_id=department.id, programme_id=programme.id, academic_level_id=level.id, title=" Introduction to Computing ", code=" csc101 ", credit_units=3, course_type="COMPULSORY", description=" Foundation course ")


def _record(institution_id: UUID, department: Department, programme: Programme, level: AcademicLevel) -> Course:
    now = datetime.now(UTC)
    return Course(id=uuid4(), institution_id=institution_id, department_id=department.id, programme_id=programme.id, academic_level_id=level.id, title="Introduction to Computing", code="CSC101", credit_units=3, course_type="compulsory", description=None, status="active", created_at=now, updated_at=now)


def test_model_constraints_and_schema_validation() -> None:
    unique = {tuple(c.name for c in x.columns) for x in Course.__table__.constraints if isinstance(x, UniqueConstraint)}
    checks = {str(x.sqltext) for x in Course.__table__.constraints if isinstance(x, CheckConstraint)}
    assert ("institution_id", "code") in unique
    assert ("programme_id", "academic_level_id", "title") in unique
    assert "credit_units > 0" in checks
    department, programme, level = _hierarchy(uuid4()); payload = _payload(department, programme, level)
    assert payload.title == "Introduction to Computing" and payload.code == "CSC101" and payload.course_type is CourseType.COMPULSORY
    assert "institution_id" not in CourseCreate.model_fields and "institution_id" not in CourseUpdate.model_fields
    with pytest.raises(ValidationError): CourseCreate(department_id=department.id, programme_id=programme.id, academic_level_id=level.id, title=" ", code=" ", credit_units=0, course_type="unknown")


def test_successful_creation_derives_institution() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); session = FakeSession(department, programme, level, None, None)
    result = course_service.create_course(session, institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]
    assert result.institution_id == context.institution.id and result.code == "CSC101" and result.description == "Foundation course"
    assert session.added == [result] and session.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], course_service.CourseDepartmentNotFoundError), (["department"], course_service.CourseProgrammeNotFoundError), (["department", "programme"], course_service.CourseAcademicLevelNotFoundError)])
def test_missing_and_cross_institution_parents_rejected(results: list[object], error: type[Exception]) -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id)
    actual = [department if x == "department" else programme for x in results]
    with pytest.raises(error): course_service.create_course(FakeSession(*actual), institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]


def test_programme_department_mismatch_rejected() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); programme.department_id = uuid4()
    with pytest.raises(course_service.CourseHierarchyMismatchError): course_service.create_course(FakeSession(department, programme), institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]


def test_academic_level_programme_mismatch_rejected() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); level.programme_id = uuid4()
    with pytest.raises(course_service.CourseHierarchyMismatchError): course_service.create_course(FakeSession(department, programme, level), institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]


@pytest.mark.parametrize(("results", "error"), [(["duplicate"], course_service.DuplicateCourseCodeError), ([None, "duplicate"], course_service.DuplicateCourseTitleError)])
def test_duplicate_code_and_title_rejected(results: list[object], error: type[Exception]) -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id)
    with pytest.raises(error): course_service.create_course(FakeSession(department, programme, level, *results), institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]


def test_same_title_allowed_in_another_programme() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); session = FakeSession(department, programme, level, None, None)
    course_service.create_course(session, institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]
    assert "courses.programme_id" in str(session.statements[4]) and "courses.academic_level_id" in str(session.statements[4])


def test_list_scoped_with_all_filters() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); expected = [_record(context.institution.id, department, programme, level)]; session = FakeSession(expected)
    assert course_service.list_courses(session, institution_id=context.institution.id, department_id=department.id, programme_id=programme.id, academic_level_id=level.id, course_type=CourseType.COMPULSORY, status="active") == expected  # type: ignore[arg-type]
    sql = str(session.statements[0]); assert all(value in sql for value in ("courses.institution_id", "courses.department_id", "courses.programme_id", "courses.academic_level_id", "courses.course_type", "courses.status"))


def test_retrieve_and_update_revalidate_hierarchy() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); record = _record(context.institution.id, department, programme, level); session = FakeSession(record, department, programme, level, None, None)
    updated = course_service.update_course(session, course_id=record.id, institution_id=context.institution.id, course_data=CourseUpdate(title="Programming I", code=" csc102 ", credit_units=4, course_type="elective"))  # type: ignore[arg-type]
    assert updated.title == "Programming I" and updated.code == "CSC102" and updated.credit_units == 4 and session.commits == 1
    assert course_service.get_course(FakeSession(updated), course_id=updated.id, institution_id=context.institution.id) is updated  # type: ignore[arg-type]


def test_update_hierarchy_mismatch_rejected() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); record = _record(context.institution.id, department, programme, level); programme.department_id = uuid4()
    with pytest.raises(course_service.CourseHierarchyMismatchError): course_service.update_course(FakeSession(record, department, programme), course_id=record.id, institution_id=context.institution.id, course_data=CourseUpdate(title="Changed"))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"course_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(course_service.CourseNotFoundError):
        if operation == "get": course_service.get_course(FakeSession(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": course_service.update_course(FakeSession(), course_data=CourseUpdate(title="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: course_service.delete_course(FakeSession(), **kwargs)  # type: ignore[arg-type]


def test_delete_deactivates_and_hides_course() -> None:
    context = _context(); department, programme, level = _hierarchy(context.institution.id); record = _record(context.institution.id, department, programme, level); session = FakeSession(record)
    deleted = course_service.delete_course(session, course_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]
    assert deleted.status == "inactive" and session.commits == 1
    with pytest.raises(course_service.CourseNotFoundError): course_service.get_course(FakeSession(), course_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_router_and_safe_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    context = _context(); department, programme, level = _hierarchy(context.institution.id)
    monkeypatch.setattr(courses, "create_course", lambda *_, **__: (_ for _ in ()).throw(course_service.DuplicateCourseCodeError()))
    with pytest.raises(HTTPException) as duplicate: courses.create_course_endpoint(_payload(department, programme, level), FakeSession(), context)  # type: ignore[arg-type]
    assert duplicate.value.status_code == 409
    assert "/api/v1/courses" in app.openapi()["paths"] and "/api/v1/courses/{course_id}" in app.openapi()["paths"]


def test_integrity_error_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    context = _context(); department, programme, level = _hierarchy(context.institution.id); session = FailingSession(department, programme, level, None, None)
    with pytest.raises(course_service.DuplicateCourseError): course_service.create_course(session, institution_id=context.institution.id, course_data=_payload(department, programme, level))  # type: ignore[arg-type]
    assert session.rollbacks == 1
