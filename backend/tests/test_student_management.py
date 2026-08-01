from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import students
from app.main import app
from app.models.academic_level import AcademicLevel
from app.models.institution import Institution
from app.models.programme import Programme
from app.models.student import Student
from app.models.user import User
from app.schemas.student import EnrollmentStatus, StudentCreate, StudentUpdate
from app.services import student_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[Student]) -> None: self.values = values
    def all(self) -> list[Student]: return self.values


class FakeSession:
    def __init__(self, *results: object) -> None:
        self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.commits = 0; self.rollbacks = 0; self.flushes = 0
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement); return FakeScalarResult(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def flush(self) -> None:
        self.flushes += 1
        for value in self.added:
            if getattr(value, "id", None) is None: value.id = uuid4()
    def commit(self) -> None:
        self.commits += 1
        now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None: value.id = uuid4()
            if getattr(value, "created_at", None) is None: value.created_at = now
            if getattr(value, "updated_at", None) is None: value.updated_at = now
    def rollback(self) -> None: self.rollbacks += 1
    def refresh(self, value: object) -> None:
        now = datetime.now(UTC)
        if getattr(value, "created_at", None) is None: value.created_at = now
        if getattr(value, "updated_at", None) is None: value.updated_at = now


def _context() -> AuthenticatedUserContext:
    institution = Institution(id=uuid4(), name="Test University", code=f"T-{uuid4()}", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email=f"{uuid4()}@test.edu", password_hash="x", first_name="Admin", last_name="User", is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=("administrator",))


def _programme(institution_id: UUID) -> Programme:
    return Programme(id=uuid4(), institution_id=institution_id, faculty_id=uuid4(), department_id=uuid4(), name="Computer Science", code=f"CS-{uuid4()}", award="BSc", duration_years=4, study_mode="FULL_TIME", status="active")


def _level(institution_id: UUID, programme_id: UUID, name: str = "200 Level") -> AcademicLevel:
    return AcademicLevel(id=uuid4(), institution_id=institution_id, programme_id=programme_id, name=name, code="200", sequence_number=2, status="active")


def _payload(programme_id: UUID, *, current_level: str | None = "200 Level") -> StudentCreate:
    return StudentCreate(email=" Student.Test@Example.edu ", password="ChangeMe123!", first_name=" Test ", last_name=" Student ", phone=" 0800 ", programme_id=programme_id, matriculation_number=" NSC/2026/0001 ", admission_year=2026, current_level=current_level)


def _record(institution_id: UUID, programme_id: UUID, *, status: str = "active") -> Student:
    now = datetime.now(UTC); user = User(id=uuid4(), institution_id=institution_id, email="student@example.edu", password_hash="secret-hash", first_name="Test", last_name="Student", phone=None, is_active=True, is_verified=False, created_at=now, updated_at=now)
    student = Student(id=uuid4(), institution_id=institution_id, user_id=user.id, programme_id=programme_id, matriculation_number="NSC/2026/0001", admission_year=2026, current_level="200 Level", enrollment_status=status, graduation_date=None, created_at=now, updated_at=now); student.user = user; return student


def test_schema_normalization_security_and_graduation_validation() -> None:
    payload = _payload(uuid4())
    assert str(payload.email) == "student.test@example.edu" and payload.first_name == "Test" and payload.matriculation_number == "NSC/2026/0001"
    forbidden = {"institution_id", "user_id", "password_hash", "id", "created_at", "updated_at", "last_login_at"}
    assert forbidden.isdisjoint(StudentCreate.model_fields)
    with pytest.raises(ValidationError): _payload(uuid4()).model_copy(update={"password": "short"}) if False else StudentCreate(email="a@b.com", password="short", first_name="A", last_name="B", programme_id=uuid4(), matriculation_number="M", admission_year=2026)
    with pytest.raises(ValidationError): StudentCreate(email="a@b.com", password="longpassword", first_name="A", last_name="B", programme_id=uuid4(), matriculation_number="M", admission_year=2026, enrollment_status="graduated")


def test_successful_user_student_creation_hashes_password_and_derives_institution() -> None:
    context = _context(); programme = _programme(context.institution.id); session = FakeSession(programme, uuid4(), None, None)
    result = student_service.create_student(session, institution_id=context.institution.id, student_data=_payload(programme.id))  # type: ignore[arg-type]
    user, profile = session.added
    assert user.password_hash != "ChangeMe123!" and "password_hash" not in result.model_dump()
    assert profile.institution_id == context.institution.id and result.institution_id == context.institution.id
    assert session.flushes == 1 and session.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], student_service.StudentProgrammeNotFoundError), (["programme", None], student_service.InvalidStudentCurrentLevelError), (["programme", "level", uuid4()], student_service.DuplicateStudentEmailError), (["programme", "level", None, uuid4()], student_service.DuplicateMatriculationNumberError)])
def test_parent_level_and_uniqueness_validation(results: list[object], error: type[Exception]) -> None:
    context = _context(); programme = _programme(context.institution.id); level = _level(context.institution.id, programme.id); mapping = {"programme": programme, "level": level}; values = [mapping.get(x, x) if isinstance(x, str) else x for x in results]
    with pytest.raises(error): student_service.create_student(FakeSession(*values), institution_id=context.institution.id, student_data=_payload(programme.id))  # type: ignore[arg-type]


def test_valid_current_level_accepted() -> None:
    context = _context(); programme = _programme(context.institution.id); level = _level(context.institution.id, programme.id); session = FakeSession(programme, level.id, None, None)
    assert student_service.create_student(session, institution_id=context.institution.id, student_data=_payload(programme.id)).current_level == "200 Level"  # type: ignore[arg-type]


def test_list_scoped_with_all_filters() -> None:
    context = _context(); programme = _programme(context.institution.id); record = _record(context.institution.id, programme.id); session = FakeSession([record])
    result = student_service.list_students(session, institution_id=context.institution.id, programme_id=programme.id, enrollment_status=EnrollmentStatus.ACTIVE, admission_year=2026, current_level=" 200 Level ", is_active=True)  # type: ignore[arg-type]
    assert result[0].id == record.id
    sql = str(session.statements[0]); assert all(field in sql for field in ("students.institution_id", "students.programme_id", "students.enrollment_status", "students.admission_year", "students.current_level", "users.is_active"))


def test_retrieve_by_id_and_matriculation() -> None:
    context = _context(); programme = _programme(context.institution.id); record = _record(context.institution.id, programme.id)
    assert student_service.get_student(FakeSession(record), student_id=record.id, institution_id=context.institution.id).id == record.id  # type: ignore[arg-type]
    assert student_service.get_student_by_matriculation(FakeSession(record), matriculation_number=" NSC/2026/0001 ", institution_id=context.institution.id).id == record.id  # type: ignore[arg-type]


def test_update_user_and_student_fields() -> None:
    context = _context(); programme = _programme(context.institution.id); record = _record(context.institution.id, programme.id); level = _level(context.institution.id, programme.id); session = FakeSession(record, programme, level.id, None, None)
    result = student_service.update_student(session, student_id=record.id, institution_id=context.institution.id, student_data=StudentUpdate(email="new@example.edu", first_name="New", phone="123", matriculation_number="NSC/2026/0002", admission_year=2025, is_verified=True))  # type: ignore[arg-type]
    assert result.email == "new@example.edu" and result.first_name == "New" and result.matriculation_number == "NSC/2026/0002" and result.is_verified


def test_programme_reassignment_revalidates_level() -> None:
    context = _context(); old = _programme(context.institution.id); new = _programme(context.institution.id); record = _record(context.institution.id, old.id)
    with pytest.raises(student_service.InvalidStudentCurrentLevelError): student_service.update_student(FakeSession(record, new, None), student_id=record.id, institution_id=context.institution.id, student_data=StudentUpdate(programme_id=new.id))  # type: ignore[arg-type]


@pytest.mark.parametrize(("changes", "results", "error"), [(StudentUpdate(email="taken@example.edu"), ["programme", "level", uuid4()], student_service.DuplicateStudentEmailError), (StudentUpdate(matriculation_number="TAKEN"), ["programme", "level", uuid4()], student_service.DuplicateMatriculationNumberError)])
def test_update_uniqueness_revalidated(changes: StudentUpdate, results: list[object], error: type[Exception]) -> None:
    context = _context(); programme = _programme(context.institution.id); record = _record(context.institution.id, programme.id); level = _level(context.institution.id, programme.id); mapping = {"programme": programme, "level": level}; values = [mapping.get(x, x) if isinstance(x, str) else x for x in results]
    with pytest.raises(error): student_service.update_student(FakeSession(record, *values), student_id=record.id, institution_id=context.institution.id, student_data=changes)  # type: ignore[arg-type]


def test_graduation_final_state_validation() -> None:
    context = _context(); programme = _programme(context.institution.id); record = _record(context.institution.id, programme.id); level = _level(context.institution.id, programme.id)
    with pytest.raises(student_service.InvalidStudentGraduationStateError): student_service.update_student(FakeSession(record, programme, level.id), student_id=record.id, institution_id=context.institution.id, student_data=StudentUpdate(enrollment_status="graduated"))  # type: ignore[arg-type]
    with pytest.raises(student_service.InvalidStudentGraduationStateError): student_service.update_student(FakeSession(record, programme, level.id), student_id=record.id, institution_id=context.institution.id, student_data=StudentUpdate(graduation_date=date(2026, 7, 1)))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"student_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(student_service.StudentNotFoundError):
        if operation == "get": student_service.get_student(FakeSession(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": student_service.update_student(FakeSession(), student_data=StudentUpdate(first_name="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: student_service.delete_student(FakeSession(), **kwargs)  # type: ignore[arg-type]


def test_delete_deactivates_user_student_and_preserves_registrations() -> None:
    context = _context(); programme = _programme(context.institution.id); record = _record(context.institution.id, programme.id); registrations = record.course_registrations
    session = FakeSession(record); student_service.delete_student(session, student_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]
    assert record.enrollment_status == "inactive" and record.user.is_active is False and record.course_registrations is registrations and session.commits == 1


def test_unauthenticated_router_registration_order_and_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    context = _context(); programme = _programme(context.institution.id)
    monkeypatch.setattr(students, "create_student", lambda *_, **__: (_ for _ in ()).throw(student_service.DuplicateStudentEmailError()))
    with pytest.raises(HTTPException) as duplicate: students.create_student_endpoint(_payload(programme.id), FakeSession(), context)  # type: ignore[arg-type]
    assert duplicate.value.status_code == 409
    paths = app.openapi()["paths"]; assert "/api/v1/students/by-matriculation/{matriculation_number}" in paths and "/api/v1/students/{student_id}" in paths
    route_paths = [route.path for route in students.router.routes]; assert route_paths.index("/students/by-matriculation/{matriculation_number}") < route_paths.index("/students/{student_id}")


def test_integrity_failure_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    context = _context(); programme = _programme(context.institution.id); level = _level(context.institution.id, programme.id); session = FailingSession(programme, level.id, None, None)
    with pytest.raises(student_service.DuplicateStudentError): student_service.create_student(session, institution_id=context.institution.id, student_data=_payload(programme.id))  # type: ignore[arg-type]
    assert session.rollbacks == 1
