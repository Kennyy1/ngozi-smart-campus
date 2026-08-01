from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import semesters
from app.main import app
from app.models.academic_session import AcademicSession
from app.models.institution import Institution
from app.models.semester import Semester
from app.models.user import User
from app.schemas.semester import SemesterCreate, SemesterUpdate
from app.services import semester_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[Semester]) -> None: self.values = values
    def all(self) -> list[Semester]: return self.values


class FakeSession:
    def __init__(self, *results: object) -> None:
        self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.deleted: list[object] = []; self.commits = 0; self.rollbacks = 0
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement); return FakeScalarResult(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def execute(self, statement: object) -> None: self.statements.append(statement)
    def add(self, value: object) -> None: self.added.append(value)
    def delete(self, value: object) -> None: self.deleted.append(value)
    def commit(self) -> None: self.commits += 1
    def rollback(self) -> None: self.rollbacks += 1
    def refresh(self, _: object) -> None: pass


def _context(institution_id: UUID | None = None) -> AuthenticatedUserContext:
    institution = Institution(id=institution_id or uuid4(), name="Test University", code=f"T-{uuid4()}", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email=f"{uuid4()}@test.edu", password_hash="x", first_name="Admin", last_name="User", is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=("administrator",))


def _parent(institution_id: UUID, *, current: bool = True) -> AcademicSession:
    return AcademicSession(id=uuid4(), institution_id=institution_id, name="2026/27", start_date=date(2026, 9, 1), end_date=date(2027, 7, 31), is_current=current, status="active", description=None)


def _payload(parent_id: UUID, *, name: str = "First Semester", sequence: int = 1, current: bool = False) -> SemesterCreate:
    return SemesterCreate(academic_session_id=parent_id, name=name, sequence_number=sequence, start_date=date(2026, 9, 1), end_date=date(2027, 1, 31), is_current=current, description=" Main term ")


def _record(institution_id: UUID, parent_id: UUID, *, current: bool = False) -> Semester:
    now = datetime.now(UTC)
    return Semester(id=uuid4(), institution_id=institution_id, academic_session_id=parent_id, name="First Semester", sequence_number=1, start_date=date(2026, 9, 1), end_date=date(2027, 1, 31), is_current=current, status="active", description=None, created_at=now, updated_at=now)


def test_model_constraints_and_request_schema() -> None:
    unique = {tuple(c.name for c in x.columns) for x in Semester.__table__.constraints if isinstance(x, UniqueConstraint)}
    checks = {str(x.sqltext) for x in Semester.__table__.constraints if isinstance(x, CheckConstraint)}
    indexes = {x.name: x for x in Semester.__table__.indexes if isinstance(x, Index)}
    assert ("academic_session_id", "name") in unique
    assert ("academic_session_id", "sequence_number") in unique
    assert {"start_date < end_date", "sequence_number > 0"} <= checks
    assert indexes["uq_semesters_current_institution"].unique
    assert "institution_id" not in SemesterCreate.model_fields
    assert "institution_id" not in SemesterUpdate.model_fields


def test_successful_creation_derives_institution_and_resolves_parent() -> None:
    context = _context(); parent = _parent(context.institution.id); session = FakeSession(parent, None, None)
    result = semester_service.create_semester(session, institution_id=context.institution.id, semester_data=_payload(parent.id))  # type: ignore[arg-type]
    assert result.institution_id == context.institution.id
    assert result.description == "Main term"
    assert session.added == [result] and session.commits == 1
    assert "academic_sessions.institution_id" in str(session.statements[0])


def test_missing_and_cross_institution_parent_are_not_found() -> None:
    with pytest.raises(semester_service.SemesterAcademicSessionNotFoundError):
        semester_service.create_semester(FakeSession(), institution_id=uuid4(), semester_data=_payload(uuid4()))  # type: ignore[arg-type]


@pytest.mark.parametrize(("duplicate_index", "error"), [(1, semester_service.DuplicateSemesterNameError), (2, semester_service.DuplicateSemesterSequenceError)])
def test_duplicates_are_rejected_within_parent(duplicate_index: int, error: type[Exception]) -> None:
    context = _context(); parent = _parent(context.institution.id); results: list[object] = [parent, None, None]; results[duplicate_index] = uuid4()
    with pytest.raises(error):
        semester_service.create_semester(FakeSession(*results), institution_id=context.institution.id, semester_data=_payload(parent.id))  # type: ignore[arg-type]


def test_same_name_is_allowed_in_another_academic_session() -> None:
    context = _context(); parent = _parent(context.institution.id); session = FakeSession(parent, None, None)
    semester_service.create_semester(session, institution_id=context.institution.id, semester_data=_payload(parent.id))  # type: ignore[arg-type]
    assert "semesters.academic_session_id" in str(session.statements[1])


@pytest.mark.parametrize(("start", "end"), [(date(2026, 9, 1), date(2026, 9, 1)), (date(2027, 1, 1), date(2026, 9, 1))])
def test_equal_reversed_and_non_positive_values_rejected(start: date, end: date) -> None:
    with pytest.raises(ValidationError):
        SemesterCreate(academic_session_id=uuid4(), name="Term", sequence_number=0, start_date=start, end_date=end)


@pytest.mark.parametrize(("start", "end"), [(date(2026, 8, 31), date(2027, 1, 1)), (date(2026, 9, 1), date(2027, 8, 1))])
def test_dates_outside_parent_are_rejected(start: date, end: date) -> None:
    context = _context(); parent = _parent(context.institution.id)
    payload = _payload(parent.id).model_copy(update={"start_date": start, "end_date": end})
    with pytest.raises(semester_service.SemesterOutsideAcademicSessionError):
        semester_service.create_semester(FakeSession(parent, None, None), institution_id=context.institution.id, semester_data=payload)  # type: ignore[arg-type]


def test_list_scoping_and_all_filters() -> None:
    context = _context(); parent = _parent(context.institution.id); expected = [_record(context.institution.id, parent.id, current=True)]; session = FakeSession(expected)
    assert semester_service.list_semesters(session, institution_id=context.institution.id, academic_session_id=parent.id, status="active", is_current=True) == expected  # type: ignore[arg-type]
    sql = str(session.statements[0]); assert all(field in sql for field in ("semesters.institution_id", "semesters.academic_session_id", "semesters.status", "semesters.is_current"))


def test_retrieve_current_update_and_unset_previous() -> None:
    context = _context(); parent = _parent(context.institution.id); record = _record(context.institution.id, parent.id); session = FakeSession(record, parent, None)
    updated = semester_service.update_semester(session, semester_id=record.id, institution_id=context.institution.id, semester_data=SemesterUpdate(name="Semester One", is_current=True))  # type: ignore[arg-type]
    assert updated.name == "Semester One" and updated.is_current and session.commits == 1
    assert any(str(x).startswith("UPDATE semesters") for x in session.statements)
    assert semester_service.get_current_semester(FakeSession(updated), institution_id=context.institution.id) is updated  # type: ignore[arg-type]


def test_current_requires_current_parent() -> None:
    context = _context(); parent = _parent(context.institution.id, current=False)
    with pytest.raises(semester_service.InactiveCurrentAcademicSessionError):
        semester_service.create_semester(FakeSession(parent, None, None), institution_id=context.institution.id, semester_data=_payload(parent.id, current=True))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"semester_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(semester_service.SemesterNotFoundError):
        if operation == "get": semester_service.get_semester(FakeSession(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": semester_service.update_semester(FakeSession(), semester_data=SemesterUpdate(name="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: semester_service.delete_semester(FakeSession(), **kwargs)  # type: ignore[arg-type]


def test_delete_current_clears_and_removes_without_replacement() -> None:
    context = _context(); parent = _parent(context.institution.id); record = _record(context.institution.id, parent.id, current=True); session = FakeSession(record)
    semester_service.delete_semester(session, semester_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]
    assert not record.is_current and session.deleted == [record] and session.commits == 1
    with pytest.raises(semester_service.SemesterNotFoundError): semester_service.get_semester(FakeSession(), semester_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]


def test_no_current_and_unauthenticated_return_not_found_and_401() -> None:
    with pytest.raises(semester_service.SemesterNotFoundError): semester_service.get_current_semester(FakeSession(), institution_id=uuid4())  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401


def test_integrity_rollback_and_route_registration() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    context = _context(); parent = _parent(context.institution.id)
    with pytest.raises(semester_service.DuplicateSemesterError): semester_service.create_semester(FailingSession(parent, None, None), institution_id=context.institution.id, semester_data=_payload(parent.id))  # type: ignore[arg-type]
    paths = app.openapi()["paths"]
    assert "/api/v1/semesters/current" in paths and "/api/v1/semesters/{semester_id}" in paths
    route_paths = [route.path for route in semesters.router.routes]
    assert route_paths.index("/semesters/current") < route_paths.index("/semesters/{semester_id}")
