from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import academic_levels
from app.main import app
from app.models.academic_level import AcademicLevel
from app.models.institution import Institution
from app.models.programme import Programme
from app.models.user import User
from app.schemas.academic_level import AcademicLevelCreate, AcademicLevelUpdate
from app.services import academic_level_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[AcademicLevel]) -> None:
        self.values = values

    def all(self) -> list[AcademicLevel]:
        return self.values


class FakeSession:
    def __init__(self, *scalar_results: object) -> None:
        self.scalar_results = list(scalar_results)
        self.statements: list[object] = []
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, statement: object) -> object:
        self.statements.append(statement)
        return self.scalar_results.pop(0) if self.scalar_results else None

    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement)
        values = self.scalar_results.pop(0) if self.scalar_results else []
        return FakeScalarResult(values)  # type: ignore[arg-type]

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, _: object) -> None:
        return None


def _context(institution_id: UUID | None = None) -> AuthenticatedUserContext:
    institution = Institution(
        id=institution_id or uuid4(),
        name="Test University",
        code=f"TEST-{uuid4()}",
        status="active",
    )
    user = User(
        id=uuid4(),
        institution_id=institution.id,
        email=f"{uuid4()}@example.edu",
        password_hash="not-returned",
        first_name="Academic",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=("administrator",),
    )


def _programme(institution_id: UUID, *, status: str = "active") -> Programme:
    return Programme(
        id=uuid4(),
        institution_id=institution_id,
        faculty_id=uuid4(),
        department_id=uuid4(),
        name="Computer Science",
        code=f"CS-{uuid4()}",
        award="BSc",
        duration_years=4,
        study_mode="FULL_TIME",
        description=None,
        status=status,
    )


def _payload(programme_id: UUID, *, name: str = "100 Level", code: str = "100", sequence: int = 1) -> AcademicLevelCreate:
    return AcademicLevelCreate(
        programme_id=programme_id,
        name=name,
        code=code,
        sequence_number=sequence,
        description=" Entry level ",
    )


def _record(institution_id: UUID, programme_id: UUID) -> AcademicLevel:
    now = datetime.now(UTC)
    return AcademicLevel(
        id=uuid4(),
        institution_id=institution_id,
        programme_id=programme_id,
        name="100 Level",
        code="100",
        sequence_number=1,
        description=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


def test_model_constraints_and_schema_validation() -> None:
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in AcademicLevel.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        str(constraint.sqltext)
        for constraint in AcademicLevel.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert ("programme_id", "name") in unique_sets
    assert ("programme_id", "code") in unique_sets
    assert ("programme_id", "sequence_number") in unique_sets
    assert "sequence_number > 0" in checks
    payload = _payload(uuid4(), name=" Foundation Level ", code=" pgd ")
    assert payload.name == "Foundation Level"
    assert payload.code == "PGD"
    assert "institution_id" not in AcademicLevelCreate.model_fields
    assert "institution_id" not in AcademicLevelUpdate.model_fields
    with pytest.raises(ValidationError):
        AcademicLevelCreate(programme_id=uuid4(), name=" ", code=" ", sequence_number=0)


def test_successful_creation_derives_institution() -> None:
    context = _context()
    programme = _programme(context.institution.id)
    session = FakeSession(programme, None, None, None)
    result = academic_level_service.create_academic_level(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        academic_level_data=_payload(programme.id),
    )
    assert result.institution_id == context.institution.id
    assert result.description == "Entry level"
    assert session.added == [result]
    assert session.commits == 1


@pytest.mark.parametrize("parent", [None, "cross", "inactive"])
def test_missing_cross_institution_and_inactive_programme_rejected(parent: str | None) -> None:
    context = _context()
    programme = None
    if parent == "cross":
        programme = _programme(uuid4())
    elif parent == "inactive":
        programme = _programme(context.institution.id, status="inactive")
    with pytest.raises(academic_level_service.AcademicLevelProgrammeNotFoundError):
        academic_level_service.create_academic_level(
            FakeSession(),  # query is institution- and active-scoped
            institution_id=context.institution.id,
            academic_level_data=_payload(programme.id if programme else uuid4()),
        )


@pytest.mark.parametrize(
    ("results", "error"),
    [
        (("duplicate",), academic_level_service.DuplicateAcademicLevelNameError),
        ((None, "duplicate"), academic_level_service.DuplicateAcademicLevelCodeError),
        ((None, None, "duplicate"), academic_level_service.DuplicateAcademicLevelSequenceError),
    ],
)
def test_duplicate_name_code_and_sequence_rejected(results: tuple[object, ...], error: type[Exception]) -> None:
    context = _context()
    programme = _programme(context.institution.id)
    with pytest.raises(error):
        academic_level_service.create_academic_level(
            FakeSession(programme, *results),  # type: ignore[arg-type]
            institution_id=context.institution.id,
            academic_level_data=_payload(programme.id),
        )


@pytest.mark.parametrize("field", ["name", "code", "sequence_number"])
def test_same_values_are_allowed_in_another_programme(field: str) -> None:
    context = _context()
    programme = _programme(context.institution.id)
    session = FakeSession(programme, None, None, None)
    academic_level_service.create_academic_level(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        academic_level_data=_payload(programme.id),
    )
    assert f"academic_levels.{field}" in str(session.statements[{"name": 1, "code": 2, "sequence_number": 3}[field]])
    assert "academic_levels.programme_id" in str(session.statements[1])


def test_list_is_institution_scoped_and_filters_programme_and_status() -> None:
    context = _context()
    programme = _programme(context.institution.id)
    expected = [_record(context.institution.id, programme.id)]
    session = FakeSession(expected)
    result = academic_level_service.list_academic_levels(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        programme_id=programme.id,
        status="active",
    )
    assert result == expected
    statement = str(session.statements[0])
    assert "academic_levels.institution_id" in statement
    assert "academic_levels.programme_id" in statement
    assert "academic_levels.status" in statement


def test_retrieve_and_update_successfully() -> None:
    context = _context()
    programme = _programme(context.institution.id)
    record = _record(context.institution.id, programme.id)
    session = FakeSession(record, None, None, None)
    updated = academic_level_service.update_academic_level(
        session,  # type: ignore[arg-type]
        academic_level_id=record.id,
        institution_id=context.institution.id,
        academic_level_data=AcademicLevelUpdate(name="Foundation", code=" fnd ", sequence_number=2),
    )
    assert updated.name == "Foundation"
    assert updated.code == "FND"
    assert updated.sequence_number == 2
    assert session.commits == 1
    assert academic_level_service.get_academic_level(FakeSession(updated), academic_level_id=updated.id, institution_id=context.institution.id) is updated  # type: ignore[arg-type]


def test_move_to_valid_programme_revalidates_all_uniqueness() -> None:
    context = _context()
    old_programme = _programme(context.institution.id)
    new_programme = _programme(context.institution.id)
    record = _record(context.institution.id, old_programme.id)
    session = FakeSession(record, new_programme, None, None, None)
    updated = academic_level_service.update_academic_level(
        session,  # type: ignore[arg-type]
        academic_level_id=record.id,
        institution_id=context.institution.id,
        academic_level_data=AcademicLevelUpdate(programme_id=new_programme.id),
    )
    assert updated.programme_id == new_programme.id
    assert session.commits == 1


def test_move_rejects_uniqueness_conflict() -> None:
    context = _context()
    old_programme = _programme(context.institution.id)
    new_programme = _programme(context.institution.id)
    record = _record(context.institution.id, old_programme.id)
    with pytest.raises(academic_level_service.DuplicateAcademicLevelNameError):
        academic_level_service.update_academic_level(
            FakeSession(record, new_programme, uuid4()),  # type: ignore[arg-type]
            academic_level_id=record.id,
            institution_id=context.institution.id,
            academic_level_data=AcademicLevelUpdate(programme_id=new_programme.id),
        )


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    arguments = {"academic_level_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(academic_level_service.AcademicLevelNotFoundError):
        if operation == "get":
            academic_level_service.get_academic_level(FakeSession(), **arguments)  # type: ignore[arg-type]
        elif operation == "update":
            academic_level_service.update_academic_level(FakeSession(), academic_level_data=AcademicLevelUpdate(name="Hidden"), **arguments)  # type: ignore[arg-type]
        else:
            academic_level_service.delete_academic_level(FakeSession(), **arguments)  # type: ignore[arg-type]


def test_delete_soft_deactivates_and_hides_record() -> None:
    context = _context()
    programme = _programme(context.institution.id)
    record = _record(context.institution.id, programme.id)
    session = FakeSession(record)
    deleted = academic_level_service.delete_academic_level(
        session,  # type: ignore[arg-type]
        academic_level_id=record.id,
        institution_id=context.institution.id,
    )
    assert deleted.status == "inactive"
    assert session.commits == 1
    with pytest.raises(academic_level_service.AcademicLevelNotFoundError):
        academic_level_service.get_academic_level(FakeSession(), academic_level_id=record.id, institution_id=context.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_access_returns_401() -> None:
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]
    assert raised.value.status_code == 401


def test_integrity_rollback_and_router_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None:
            raise IntegrityError("insert", {}, Exception("constraint"))

    context = _context()
    programme = _programme(context.institution.id)
    failing = FailingSession(programme, None, None, None)
    with pytest.raises(academic_level_service.DuplicateAcademicLevelError):
        academic_level_service.create_academic_level(failing, institution_id=context.institution.id, academic_level_data=_payload(programme.id))  # type: ignore[arg-type]
    assert failing.rollbacks == 1

    monkeypatch.setattr(academic_levels, "create_academic_level", lambda *_, **__: (_ for _ in ()).throw(academic_level_service.DuplicateAcademicLevelCodeError()))
    with pytest.raises(HTTPException) as duplicate:
        academic_levels.create_academic_level_endpoint(_payload(programme.id), FakeSession(), context)  # type: ignore[arg-type]
    assert duplicate.value.status_code == 409
    paths = app.openapi()["paths"]
    assert "/api/v1/academic-levels" in paths
    assert "/api/v1/academic-levels/{academic_level_id}" in paths
