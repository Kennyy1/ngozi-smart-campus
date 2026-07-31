from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import programmes
from app.main import app
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.institution import Institution
from app.models.programme import Programme
from app.models.user import User
from app.schemas.programme import (
    ProgrammeAward,
    ProgrammeCreate,
    ProgrammeUpdate,
    StudyMode,
)
from app.services import programme_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[Programme]) -> None:
        self.values = values

    def all(self) -> list[Programme]:
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
        email="admin@example.edu",
        password_hash="not-returned",
        first_name="Programme",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=("administrator",),
    )


def _faculty(institution_id: UUID) -> Faculty:
    return Faculty(
        id=uuid4(),
        institution_id=institution_id,
        name="Science",
        code="SCI",
        status="active",
    )


def _department(institution_id: UUID, faculty_id: UUID) -> Department:
    return Department(
        id=uuid4(),
        institution_id=institution_id,
        faculty_id=faculty_id,
        name="Computer Science",
        code="CSC",
        status="active",
    )


def _programme(
    institution_id: UUID,
    faculty_id: UUID,
    department_id: UUID,
) -> Programme:
    now = datetime.now(UTC)
    return Programme(
        id=uuid4(),
        institution_id=institution_id,
        faculty_id=faculty_id,
        department_id=department_id,
        name="Computer Science",
        code="BSC-CS",
        award="BSc",
        duration_years=4,
        study_mode="FULL_TIME",
        description=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


def _create_payload(faculty_id: UUID, department_id: UUID) -> ProgrammeCreate:
    return ProgrammeCreate(
        faculty_id=faculty_id,
        department_id=department_id,
        name="Computer Science",
        code=" bsc-cs ",
        award=ProgrammeAward.BSC,
        duration_years=4,
        study_mode=StudyMode.FULL_TIME,
        description="  Undergraduate computing ",
    )


def test_model_constraints_and_schema_validation() -> None:
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in Programme.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        str(constraint.sqltext)
        for constraint in Programme.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert ("institution_id", "code") in unique_sets
    assert ("department_id", "name") in unique_sets
    assert "duration_years > 0" in checks

    payload = _create_payload(uuid4(), uuid4())
    assert payload.name == "Computer Science"
    assert payload.code == "BSC-CS"
    assert payload.description == "Undergraduate computing"

    for changes in (
        {"name": " "},
        {"code": ""},
        {"duration_years": 0},
        {"award": "LLB"},
        {"study_mode": "HYBRID"},
    ):
        with pytest.raises(ValidationError):
            ProgrammeUpdate(**changes)


def test_create_programme_validates_hierarchy_and_institution() -> None:
    context = _context()
    faculty = _faculty(context.institution.id)
    department = _department(context.institution.id, faculty.id)
    session = FakeSession(faculty.id, department.id, None, None)

    result = programme_service.create_programme(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        programme_data=_create_payload(faculty.id, department.id),
    )

    assert result.institution_id == context.institution.id
    assert result.faculty_id == faculty.id
    assert result.department_id == department.id
    assert result.code == "BSC-CS"
    assert result.status == "active"
    assert session.added == [result]
    assert session.commits == 1


def test_invalid_and_cross_institution_faculty_return_not_found() -> None:
    context = _context()
    other_faculty = _faculty(uuid4())
    with pytest.raises(programme_service.ProgrammeFacultyNotFoundError):
        programme_service.create_programme(
            FakeSession(None),  # institution-scoped faculty query
            institution_id=context.institution.id,
            programme_data=_create_payload(other_faculty.id, uuid4()),
        )


def test_invalid_or_mismatched_department_returns_not_found() -> None:
    context = _context()
    faculty = _faculty(context.institution.id)
    with pytest.raises(programme_service.ProgrammeDepartmentNotFoundError):
        programme_service.create_programme(
            FakeSession(faculty.id, None),
            institution_id=context.institution.id,
            programme_data=_create_payload(faculty.id, uuid4()),
        )


@pytest.mark.parametrize(
    ("results", "expected_error"),
    [
        (
            (uuid4(), uuid4(), uuid4()),
            programme_service.DuplicateProgrammeCodeError,
        ),
        (
            (uuid4(), uuid4(), None, uuid4()),
            programme_service.DuplicateProgrammeNameError,
        ),
    ],
)
def test_duplicate_code_and_name(
    results: tuple[object, ...],
    expected_error: type[Exception],
) -> None:
    context = _context()
    with pytest.raises(expected_error):
        programme_service.create_programme(
            FakeSession(*results),  # type: ignore[arg-type]
            institution_id=context.institution.id,
            programme_data=_create_payload(uuid4(), uuid4()),
        )


def test_list_is_scoped_and_supports_all_filters() -> None:
    context = _context()
    faculty_id = uuid4()
    department_id = uuid4()
    expected = [_programme(context.institution.id, faculty_id, department_id)]
    session = FakeSession(expected)

    result = programme_service.list_programmes(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        faculty_id=faculty_id,
        department_id=department_id,
        award=ProgrammeAward.BSC,
        study_mode=StudyMode.FULL_TIME,
    )

    assert result == expected
    statement = str(session.statements[0])
    for column in (
        "programmes.institution_id",
        "programmes.faculty_id",
        "programmes.department_id",
        "programmes.award",
        "programmes.study_mode",
        "programmes.status",
    ):
        assert column in statement


def test_retrieve_update_delete_and_cross_institution_protection() -> None:
    context = _context()
    programme = _programme(context.institution.id, uuid4(), uuid4())
    session = FakeSession(programme, programme, None, programme)

    assert (
        programme_service.get_programme(
            session,  # type: ignore[arg-type]
            programme_id=programme.id,
            institution_id=context.institution.id,
        )
        is programme
    )
    updated = programme_service.update_programme(
        session,  # type: ignore[arg-type]
        programme_id=programme.id,
        institution_id=context.institution.id,
        programme_data=ProgrammeUpdate(duration_years=5, code=" msc-cs "),
    )
    assert updated.duration_years == 5
    assert updated.code == "MSC-CS"

    deleted = programme_service.delete_programme(
        session,  # type: ignore[arg-type]
        programme_id=programme.id,
        institution_id=context.institution.id,
    )
    assert deleted.status == "inactive"

    for operation in (
        programme_service.get_programme,
        programme_service.delete_programme,
    ):
        with pytest.raises(programme_service.ProgrammeNotFoundError):
            operation(
                FakeSession(),  # type: ignore[arg-type]
                programme_id=programme.id,
                institution_id=uuid4(),
            )
    with pytest.raises(programme_service.ProgrammeNotFoundError):
        programme_service.update_programme(
            FakeSession(),  # type: ignore[arg-type]
            programme_id=programme.id,
            institution_id=uuid4(),
            programme_data=ProgrammeUpdate(name="Hidden"),
        )


def test_integrity_conflict_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    context = _context()
    session = FailingSession(uuid4(), uuid4(), None, None)
    with pytest.raises(programme_service.DuplicateProgrammeError):
        programme_service.create_programme(
            session,  # type: ignore[arg-type]
            institution_id=context.institution.id,
            programme_data=_create_payload(uuid4(), uuid4()),
        )
    assert session.rollbacks == 1


def test_unauthenticated_access_is_rejected() -> None:
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(
            None,
            FakeSession(),  # type: ignore[arg-type]
        )
    assert raised.value.status_code == 401


def test_route_error_mapping_and_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    monkeypatch.setattr(
        programmes,
        "create_programme",
        lambda *_, **__: (_ for _ in ()).throw(
            programme_service.DuplicateProgrammeCodeError()
        ),
    )
    with pytest.raises(HTTPException) as duplicate:
        programmes.create_programme_endpoint(
            _create_payload(uuid4(), uuid4()),
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert duplicate.value.status_code == 409

    monkeypatch.setattr(
        programmes,
        "get_programme",
        lambda *_, **__: (_ for _ in ()).throw(
            programme_service.ProgrammeNotFoundError()
        ),
    )
    with pytest.raises(HTTPException) as missing:
        programmes.get_programme_endpoint(
            uuid4(),
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert missing.value.status_code == 404

    paths = app.openapi()["paths"]
    assert "/api/v1/programmes" in paths
    assert "/api/v1/programmes/{programme_id}" in paths
