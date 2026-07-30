from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import faculties
from app.db.base import Base
from app.models.faculty import Faculty
from app.models.institution import Institution
from app.models.user import User
from app.schemas.faculty import FacultyCreate, FacultyResponse, FacultyUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services import faculty_service


class FakeSession:
    def __init__(self, scalar_result: object = None) -> None:
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, _: object) -> object:
        return self.scalar_result

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, _: object) -> None:
        return None


def _context(*roles: str) -> AuthenticatedUserContext:
    institution = Institution(
        id=uuid4(),
        name="Test University",
        code="TEST",
        status="active",
    )
    user = User(
        id=uuid4(),
        institution_id=institution.id,
        email="admin@example.edu",
        password_hash="not-returned",
        first_name="Faculty",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    return AuthenticatedUserContext(user, institution, tuple(roles))


def _faculty(institution_id: object, *, status: str = "active") -> Faculty:
    now = datetime.now(UTC)
    return Faculty(
        id=uuid4(),
        institution_id=institution_id,
        name="Science",
        code="SCI",
        description=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_faculty_model_has_required_constraints() -> None:
    table = Base.metadata.tables["faculties"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert ("institution_id", "code") in unique_columns
    assert "status IN ('active', 'inactive')" in checks


def test_faculty_schemas_normalize_and_validate_input() -> None:
    created = FacultyCreate(
        name="  Science  ",
        code=" SCI ",
        description="  Natural sciences ",
    )
    assert created.model_dump() == {
        "name": "Science",
        "code": "SCI",
        "description": "Natural sciences",
    }
    assert FacultyUpdate(description="  ").description is None

    for invalid in (
        {"name": " ", "code": "SCI"},
        {"name": "Science", "code": ""},
    ):
        with pytest.raises(ValidationError):
            FacultyCreate(**invalid)
    with pytest.raises(ValidationError):
        FacultyUpdate(status="deleted")
    with pytest.raises(ValidationError):
        FacultyUpdate(name=None)
    with pytest.raises(ValidationError):
        FacultyUpdate(status=None)


def test_create_and_response_schema() -> None:
    context = _context("administrator")
    session = FakeSession()
    result = faculty_service.create_faculty(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        faculty_data=FacultyCreate(name="Science", code="SCI"),
    )

    assert result.institution_id == context.institution.id
    assert result.status == "active"
    assert session.added == [result]
    assert session.commits == 1

    now = datetime.now(UTC)
    result.id = uuid4()
    result.created_at = now
    result.updated_at = now
    assert FacultyResponse.model_validate(result).code == "SCI"


def test_get_update_and_soft_delete_are_institution_scoped() -> None:
    context = _context("administrator")
    faculty = _faculty(context.institution.id)
    session = FakeSession(faculty)

    found = faculty_service.get_faculty(
        session,  # type: ignore[arg-type]
        faculty_id=faculty.id,
        institution_id=context.institution.id,
    )
    assert found is faculty

    updated = faculty_service.update_faculty(
        session,  # type: ignore[arg-type]
        faculty_id=faculty.id,
        institution_id=context.institution.id,
        faculty_data=FacultyUpdate(name="Engineering"),
    )
    assert updated.name == "Engineering"

    deleted = faculty_service.delete_faculty(
        session,  # type: ignore[arg-type]
        faculty_id=faculty.id,
        institution_id=context.institution.id,
    )
    assert deleted.status == "inactive"
    assert session.commits == 2

    with pytest.raises(faculty_service.FacultyNotFoundError):
        faculty_service.get_faculty(
            FakeSession(),  # type: ignore[arg-type]
            faculty_id=faculty.id,
            institution_id=uuid4(),
        )


def test_duplicate_code_is_reported_and_integrity_error_rolls_back() -> None:
    context = _context("administrator")
    with pytest.raises(faculty_service.DuplicateFacultyCodeError):
        faculty_service.create_faculty(
            FakeSession(uuid4()),  # type: ignore[arg-type]
            institution_id=context.institution.id,
            faculty_data=FacultyCreate(name="Science", code="SCI"),
        )

    class FailingSession(FakeSession):
        def commit(self) -> None:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    session = FailingSession()
    with pytest.raises(faculty_service.DuplicateFacultyCodeError):
        faculty_service.create_faculty(
            session,  # type: ignore[arg-type]
            institution_id=context.institution.id,
            faculty_data=FacultyCreate(name="Science", code="SCI"),
        )
    assert session.rollbacks == 1


@pytest.mark.parametrize("role", ["administrator", "system_super_admin"])
def test_faculty_authorization_allows_required_roles(role: str) -> None:
    dependency = dependencies.require_roles(
        "administrator",
        "system_super_admin",
    )
    context = _context(role)
    assert dependency(context) is context


def test_faculty_authorization_rejects_other_roles() -> None:
    dependency = dependencies.require_roles(
        "administrator",
        "system_super_admin",
    )
    with pytest.raises(HTTPException) as raised:
        dependency(_context("lecturer"))
    assert raised.value.status_code == 403


def test_faculty_routes_and_error_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context("administrator")
    faculty = _faculty(context.institution.id)
    monkeypatch.setattr(
        faculties,
        "create_faculty",
        lambda *_, **__: (_ for _ in ()).throw(
            faculty_service.DuplicateFacultyCodeError()
        ),
    )
    with pytest.raises(HTTPException) as duplicate:
        faculties.create_faculty_endpoint(
            FacultyCreate(name="Science", code="SCI"),
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert duplicate.value.status_code == 409

    monkeypatch.setattr(
        faculties,
        "get_faculty",
        lambda *_, **__: (_ for _ in ()).throw(
            faculty_service.FacultyNotFoundError()
        ),
    )
    with pytest.raises(HTTPException) as missing:
        faculties.get_faculty_endpoint(
            faculty.id,
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert missing.value.status_code == 404
