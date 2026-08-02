from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import dependencies
from app.api.v1.endpoints import lecturers
from app.main import app
from app.models.department import Department
from app.models.institution import Institution
from app.models.lecturer import Lecturer
from app.models.user import User
from app.schemas.lecturer import AcademicRank, EmploymentStatus, LecturerCreate, LecturerUpdate
from app.services import lecturer_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[Lecturer]) -> None: self.values = values
    def all(self) -> list[Lecturer]: return self.values


class FakeSession:
    def __init__(self, *results: object) -> None: self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.commits = 0; self.flushes = 0; self.rollbacks = 0
    def scalar(self, statement: object) -> object: self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> FakeScalarResult: self.statements.append(statement); return FakeScalarResult(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def flush(self) -> None: self.flushes += 1; self._populate()
    def commit(self) -> None: self.commits += 1; self._populate()
    def rollback(self) -> None: self.rollbacks += 1
    def refresh(self, value: object) -> None: self._populate()
    def _populate(self) -> None:
        now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None: value.id = uuid4()
            if getattr(value, "created_at", None) is None: value.created_at = now
            if getattr(value, "updated_at", None) is None: value.updated_at = now


def _context() -> AuthenticatedUserContext:
    institution = Institution(id=uuid4(), name="Test University", code=f"T-{uuid4()}", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email="admin@test.edu", password_hash="x", first_name="Admin", last_name="User", is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=("administrator",))


def _department(institution_id: UUID) -> Department:
    return Department(id=uuid4(), institution_id=institution_id, faculty_id=uuid4(), name="Computing", code=f"C-{uuid4()}", status="active")


def _payload(department_id: UUID) -> LecturerCreate:
    return LecturerCreate(email=" Lecturer@Test.edu ", password="ChangeMe123!", first_name=" Ada ", last_name=" Lovelace ", phone=" 0800 ", department_id=department_id, staff_number=" NSC/LECT/2026/001 ", academic_rank="senior_lecturer", specialization=" Computing ", office_location=" B12 ")


def _record(institution_id: UUID, department_id: UUID) -> Lecturer:
    now = datetime.now(UTC); user = User(id=uuid4(), institution_id=institution_id, email="lecturer@test.edu", password_hash="hash", first_name="Ada", last_name="Lovelace", is_active=True, is_verified=False, created_at=now, updated_at=now)
    record = Lecturer(id=uuid4(), institution_id=institution_id, user_id=user.id, department_id=department_id, staff_number="NSC/LECT/2026/001", academic_rank="senior_lecturer", employment_status="active", specialization="Computing", employment_date=None, office_location="B12", created_at=now, updated_at=now); record.user = user; return record


def test_schema_normalization_and_security() -> None:
    payload = _payload(uuid4())
    assert str(payload.email) == "lecturer@test.edu" and payload.first_name == "Ada" and payload.staff_number == "NSC/LECT/2026/001"
    assert {"institution_id", "user_id", "password_hash", "id", "created_at", "updated_at", "last_login_at"}.isdisjoint(LecturerCreate.model_fields)
    with pytest.raises(ValidationError): LecturerCreate(email="a@b.com", password="short", first_name="A", last_name="B", department_id=uuid4(), staff_number="S", academic_rank="professor")


def test_creation_hashes_password_and_derives_institution() -> None:
    context = _context(); department = _department(context.institution.id); session = FakeSession(department, None, None)
    result = lecturer_service.create_lecturer(session, institution_id=context.institution.id, lecturer_data=_payload(department.id))  # type: ignore[arg-type]
    user, profile = session.added
    assert user.password_hash != "ChangeMe123!" and "password_hash" not in result.model_dump()
    assert profile.institution_id == context.institution.id and session.flushes == 1 and session.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], lecturer_service.LecturerDepartmentNotFoundError), (["department", uuid4()], lecturer_service.DuplicateLecturerEmailError), (["department", None, uuid4()], lecturer_service.DuplicateStaffNumberError)])
def test_department_and_uniqueness_validation(results: list[object], error: type[Exception]) -> None:
    context = _context(); department = _department(context.institution.id); values = [department if item == "department" else item for item in results]
    with pytest.raises(error): lecturer_service.create_lecturer(FakeSession(*values), institution_id=context.institution.id, lecturer_data=_payload(department.id))  # type: ignore[arg-type]


def test_list_filters_and_retrieve_routes() -> None:
    context = _context(); department = _department(context.institution.id); record = _record(context.institution.id, department.id); session = FakeSession([record])
    assert lecturer_service.list_lecturers(session, institution_id=context.institution.id, department_id=department.id, academic_rank=AcademicRank.SENIOR_LECTURER, employment_status=EmploymentStatus.ACTIVE, is_active=True)[0].id == record.id  # type: ignore[arg-type]
    sql = str(session.statements[0]); assert all(value in sql for value in ("lecturers.institution_id", "lecturers.department_id", "lecturers.academic_rank", "lecturers.employment_status", "users.is_active"))
    assert lecturer_service.get_lecturer(FakeSession(record), lecturer_id=record.id, institution_id=context.institution.id).id == record.id  # type: ignore[arg-type]
    assert lecturer_service.get_lecturer_by_staff_number(FakeSession(record), staff_number=" NSC/LECT/2026/001 ", institution_id=context.institution.id).id == record.id  # type: ignore[arg-type]


def test_update_revalidates_department_and_uniqueness() -> None:
    context = _context(); department = _department(context.institution.id); record = _record(context.institution.id, department.id); new_department = _department(context.institution.id)
    result = lecturer_service.update_lecturer(FakeSession(record, new_department, None, None), lecturer_id=record.id, institution_id=context.institution.id, lecturer_data=LecturerUpdate(department_id=new_department.id, email="new@test.edu", staff_number="STAFF-02", academic_rank="professor", first_name="Grace"))  # type: ignore[arg-type]
    assert result.department_id == new_department.id and result.email == "new@test.edu" and result.staff_number == "STAFF-02" and result.academic_rank == AcademicRank.PROFESSOR


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_are_not_found(operation: str) -> None:
    kwargs = {"lecturer_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(lecturer_service.LecturerNotFoundError):
        if operation == "get": lecturer_service.get_lecturer(FakeSession(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": lecturer_service.update_lecturer(FakeSession(), lecturer_data=LecturerUpdate(first_name="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: lecturer_service.delete_lecturer(FakeSession(), **kwargs)  # type: ignore[arg-type]


def test_delete_deactivates_without_removing_profile() -> None:
    context = _context(); record = _record(context.institution.id, uuid4()); session = FakeSession(record)
    lecturer_service.delete_lecturer(session, lecturer_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]
    assert record.employment_status == "inactive" and record.user.is_active is False and session.commits == 1 and session.added == []


def test_auth_router_order_and_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    context = _context(); department = _department(context.institution.id)
    monkeypatch.setattr(lecturers, "create_lecturer", lambda *_, **__: (_ for _ in ()).throw(lecturer_service.DuplicateLecturerEmailError()))
    with pytest.raises(HTTPException) as duplicate: lecturers.create_lecturer_endpoint(_payload(department.id), FakeSession(), context)  # type: ignore[arg-type]
    assert duplicate.value.status_code == 409
    assert "/api/v1/lecturers/{lecturer_id}" in app.openapi()["paths"]
    paths = [route.path for route in lecturers.router.routes]; assert paths.index("/lecturers/by-staff-number/{staff_number:path}") < paths.index("/lecturers/{lecturer_id}")
    lookup_route = lecturers.router.routes[paths.index("/lecturers/by-staff-number/{staff_number:path}")]
    match, scope = lookup_route.matches({"type": "http", "method": "GET", "path": "/lecturers/by-staff-number/NSC/LECT/2026/001"})
    assert match.name == "FULL" and scope["path_params"]["staff_number"] == "NSC/LECT/2026/001"
