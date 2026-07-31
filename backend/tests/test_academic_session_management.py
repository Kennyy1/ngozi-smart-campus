from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import academic_sessions
from app.main import app
from app.models.academic_session import AcademicSession
from app.models.institution import Institution
from app.models.user import User
from app.schemas.academic_session import (
    AcademicSessionCreate,
    AcademicSessionUpdate,
)
from app.services import academic_session_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[AcademicSession]) -> None:
        self.values = values

    def all(self) -> list[AcademicSession]:
        return self.values


class FakeSession:
    def __init__(self, *scalar_results: object) -> None:
        self.scalar_results = list(scalar_results)
        self.statements: list[object] = []
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, statement: object) -> object:
        self.statements.append(statement)
        return self.scalar_results.pop(0) if self.scalar_results else None

    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement)
        values = self.scalar_results.pop(0) if self.scalar_results else []
        return FakeScalarResult(values)  # type: ignore[arg-type]

    def execute(self, statement: object) -> None:
        self.statements.append(statement)

    def add(self, value: object) -> None:
        self.added.append(value)

    def delete(self, value: object) -> None:
        self.deleted.append(value)

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


def _session_record(
    institution_id: UUID,
    *,
    name: str = "2026/2027",
    is_current: bool = False,
    status: str = "active",
) -> AcademicSession:
    now = datetime.now(UTC)
    return AcademicSession(
        id=uuid4(),
        institution_id=institution_id,
        name=name,
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        is_current=is_current,
        status=status,
        description=None,
        created_at=now,
        updated_at=now,
    )


def _create_payload(
    *,
    name: str = "2026/2027",
    is_current: bool = False,
) -> AcademicSessionCreate:
    return AcademicSessionCreate(
        name=name,
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        is_current=is_current,
        status="active",
        description=" Academic year ",
    )


def test_model_constraints_and_schema_fields() -> None:
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in AcademicSession.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        str(constraint.sqltext)
        for constraint in AcademicSession.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name: index
        for index in AcademicSession.__table__.indexes
        if isinstance(index, Index)
    }
    assert ("institution_id", "name") in unique_sets
    assert "start_date < end_date" in checks
    assert indexes["uq_academic_sessions_current_institution"].unique
    assert "institution_id" not in AcademicSessionCreate.model_fields
    assert "institution_id" not in AcademicSessionUpdate.model_fields


def test_successful_creation_derives_institution_and_defaults() -> None:
    context = _context()
    session = FakeSession(None)
    result = academic_session_service.create_academic_session(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        academic_session_data=_create_payload(),
    )
    assert result.institution_id == context.institution.id
    assert result.description == "Academic year"
    assert result.status == "active"
    assert result.is_current is False
    assert session.added == [result]
    assert session.commits == 1


def test_duplicate_name_is_rejected_within_institution() -> None:
    context = _context()
    with pytest.raises(
        academic_session_service.DuplicateAcademicSessionNameError
    ):
        academic_session_service.create_academic_session(
            FakeSession(uuid4()),  # type: ignore[arg-type]
            institution_id=context.institution.id,
            academic_session_data=_create_payload(),
        )


def test_same_name_query_is_scoped_so_another_institution_is_allowed() -> None:
    context = _context()
    session = FakeSession(None)
    academic_session_service.create_academic_session(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        academic_session_data=_create_payload(),
    )
    statement = str(session.statements[0])
    assert "academic_sessions.institution_id" in statement
    assert "academic_sessions.name" in statement


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (date(2026, 9, 1), date(2026, 9, 1)),
        (date(2027, 1, 1), date(2026, 9, 1)),
    ],
)
def test_invalid_create_date_ranges_are_rejected(
    start_date: date,
    end_date: date,
) -> None:
    with pytest.raises(ValidationError):
        AcademicSessionCreate(
            name="Invalid",
            start_date=start_date,
            end_date=end_date,
        )


def test_list_is_institution_scoped_and_filters_status_and_current() -> None:
    context = _context()
    expected = [_session_record(context.institution.id, is_current=True)]
    session = FakeSession(expected)
    result = academic_session_service.list_academic_sessions(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        status="active",
        is_current=True,
    )
    assert result == expected
    statement = str(session.statements[0])
    assert "academic_sessions.institution_id" in statement
    assert "academic_sessions.status" in statement
    assert "academic_sessions.is_current" in statement


def test_retrieve_session_by_id_and_current_session() -> None:
    context = _context()
    record = _session_record(context.institution.id, is_current=True)
    session = FakeSession(record, record)
    assert (
        academic_session_service.get_academic_session(
            session,  # type: ignore[arg-type]
            academic_session_id=record.id,
            institution_id=context.institution.id,
        )
        is record
    )
    assert (
        academic_session_service.get_current_academic_session(
            session,  # type: ignore[arg-type]
            institution_id=context.institution.id,
        )
        is record
    )


def test_no_current_session_returns_not_found() -> None:
    with pytest.raises(academic_session_service.AcademicSessionNotFoundError):
        academic_session_service.get_current_academic_session(
            FakeSession(),  # type: ignore[arg-type]
            institution_id=uuid4(),
        )


def test_update_success_and_partial_final_date_validation() -> None:
    context = _context()
    record = _session_record(context.institution.id)
    session = FakeSession(record, None)
    updated = academic_session_service.update_academic_session(
        session,  # type: ignore[arg-type]
        academic_session_id=record.id,
        institution_id=context.institution.id,
        academic_session_data=AcademicSessionUpdate(
            name="2026-2027",
            end_date=date(2027, 8, 31),
        ),
    )
    assert updated.name == "2026-2027"
    assert updated.end_date == date(2027, 8, 31)
    with pytest.raises(
        academic_session_service.InvalidAcademicSessionDateRangeError
    ):
        academic_session_service.update_academic_session(
            FakeSession(record),  # type: ignore[arg-type]
            academic_session_id=record.id,
            institution_id=context.institution.id,
            academic_session_data=AcademicSessionUpdate(
                start_date=date(2028, 1, 1)
            ),
        )


def test_setting_new_current_unsets_previous_in_same_commit() -> None:
    context = _context()
    record = _session_record(context.institution.id)
    session = FakeSession(record)
    updated = academic_session_service.update_academic_session(
        session,  # type: ignore[arg-type]
        academic_session_id=record.id,
        institution_id=context.institution.id,
        academic_session_data=AcademicSessionUpdate(is_current=True),
    )
    assert updated.is_current is True
    assert session.commits == 1
    assert any(
        str(statement).startswith("UPDATE academic_sessions")
        for statement in session.statements
    )


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    record = _session_record(uuid4())
    other_institution_id = uuid4()
    with pytest.raises(academic_session_service.AcademicSessionNotFoundError):
        if operation == "get":
            academic_session_service.get_academic_session(
                FakeSession(),  # type: ignore[arg-type]
                academic_session_id=record.id,
                institution_id=other_institution_id,
            )
        elif operation == "update":
            academic_session_service.update_academic_session(
                FakeSession(),  # type: ignore[arg-type]
                academic_session_id=record.id,
                institution_id=other_institution_id,
                academic_session_data=AcademicSessionUpdate(name="Hidden"),
            )
        else:
            academic_session_service.delete_academic_session(
                FakeSession(),  # type: ignore[arg-type]
                academic_session_id=record.id,
                institution_id=other_institution_id,
            )


def test_delete_clears_current_and_removes_record() -> None:
    context = _context()
    record = _session_record(context.institution.id, is_current=True)
    session = FakeSession(record)
    academic_session_service.delete_academic_session(
        session,  # type: ignore[arg-type]
        academic_session_id=record.id,
        institution_id=context.institution.id,
    )
    assert record.is_current is False
    assert session.deleted == [record]
    assert session.commits == 1
    with pytest.raises(academic_session_service.AcademicSessionNotFoundError):
        academic_session_service.get_academic_session(
            FakeSession(),  # type: ignore[arg-type]
            academic_session_id=record.id,
            institution_id=context.institution.id,
        )


def test_integrity_conflict_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None:
            raise IntegrityError("insert", {}, Exception("constraint"))

    with pytest.raises(
        academic_session_service.DuplicateAcademicSessionError
    ):
        academic_session_service.create_academic_session(
            FailingSession(None),  # type: ignore[arg-type]
            institution_id=uuid4(),
            academic_session_data=_create_payload(),
        )


def test_unauthenticated_access_is_rejected() -> None:
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(
            None,
            FakeSession(),  # type: ignore[arg-type]
        )
    assert raised.value.status_code == 401


def test_route_error_mapping_registration_and_current_route_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    monkeypatch.setattr(
        academic_sessions,
        "create_academic_session",
        lambda *_, **__: (_ for _ in ()).throw(
            academic_session_service.DuplicateAcademicSessionNameError()
        ),
    )
    with pytest.raises(HTTPException) as duplicate:
        academic_sessions.create_academic_session_endpoint(
            _create_payload(),
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert duplicate.value.status_code == 409

    monkeypatch.setattr(
        academic_sessions,
        "get_current_academic_session",
        lambda *_, **__: (_ for _ in ()).throw(
            academic_session_service.AcademicSessionNotFoundError()
        ),
    )
    with pytest.raises(HTTPException) as missing:
        academic_sessions.get_current_academic_session_endpoint(
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert missing.value.status_code == 404

    paths = app.openapi()["paths"]
    assert "/api/v1/academic-sessions" in paths
    assert "/api/v1/academic-sessions/current" in paths
    assert "/api/v1/academic-sessions/{academic_session_id}" in paths
    route_paths = [
        route.path
        for route in academic_sessions.router.routes
        if getattr(route, "path", "").startswith("/academic-sessions/")
    ]
    assert route_paths.index("/academic-sessions/current") < (
        route_paths.index(
            "/academic-sessions/{academic_session_id}"
        )
    )
