from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.models.institution import Institution
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services import authentication


PASSWORD = "test-password-value"


class FakeSession:
    def __init__(self, results: Sequence[object | None]) -> None:
        self.results = iter(results)
        self.statements: list[Any] = []

    def scalar(self, statement: Any) -> object | None:
        self.statements.append(statement)
        return next(self.results)


def _institution(
    *,
    institution_id: UUID | None = None,
    status: str = "active",
) -> Institution:
    return Institution(
        id=institution_id or uuid4(),
        name="Test University",
        code="TEST",
        status=status,
    )


def _user(
    institution: Institution,
    *,
    active: bool = True,
    role_names: Sequence[str] = ("student",),
    foreign_role: bool = False,
) -> User:
    user = User(
        id=uuid4(),
        institution_id=institution.id,
        email="user@example.edu",
        password_hash="stored-password-hash",
        first_name="Test",
        last_name="User",
        is_active=active,
        is_verified=True,
    )
    assignments = [
        UserRole(
            id=uuid4(),
            user_id=user.id,
            role_id=uuid4(),
            institution_id=institution.id,
            role=Role(id=uuid4(), name=role_name),
        )
        for role_name in role_names
    ]
    if foreign_role:
        assignments.append(
            UserRole(
                id=uuid4(),
                user_id=user.id,
                role_id=uuid4(),
                institution_id=uuid4(),
                role=Role(id=uuid4(), name="administrator"),
            )
        )
    user.role_assignments = assignments
    user.institution = institution
    return user


def test_authentication_normalizes_identity_and_returns_current_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    institution = _institution()
    user = _user(
        institution,
        role_names=("student", "lecturer", "student"),
        foreign_role=True,
    )
    session = FakeSession([institution, user])
    monkeypatch.setattr(authentication, "verify_password", lambda *_: True)

    context = authentication.authenticate_user(
        session,  # type: ignore[arg-type]
        institution_code="  TEST  ",
        email="  USER@EXAMPLE.EDU ",
        password=PASSWORD,
    )

    statement_parameters = {
        value
        for statement in session.statements
        for value in statement.compile().params.values()
    }
    assert "TEST" in statement_parameters
    assert "user@example.edu" in statement_parameters
    assert context.user is user
    assert context.institution is institution
    assert context.roles == ("lecturer", "student")


def test_missing_or_inactive_institution_is_invalid_credentials() -> None:
    with pytest.raises(InvalidCredentialsError):
        authentication.authenticate_user(
            FakeSession([None]),  # type: ignore[arg-type]
            institution_code="TEST",
            email="user@example.edu",
            password=PASSWORD,
        )

    with pytest.raises(InvalidCredentialsError):
        authentication.authenticate_user(
            FakeSession([_institution(status="suspended")]),  # type: ignore[arg-type]
            institution_code="TEST",
            email="user@example.edu",
            password=PASSWORD,
        )


def test_missing_user_is_invalid_credentials() -> None:
    institution = _institution()

    with pytest.raises(InvalidCredentialsError):
        authentication.authenticate_user(
            FakeSession([institution, None]),  # type: ignore[arg-type]
            institution_code="TEST",
            email="user@example.edu",
            password=PASSWORD,
        )


def test_wrong_password_is_invalid_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    institution = _institution()
    user = _user(institution)
    monkeypatch.setattr(authentication, "verify_password", lambda *_: False)

    with pytest.raises(InvalidCredentialsError):
        authentication.authenticate_user(
            FakeSession([institution, user]),  # type: ignore[arg-type]
            institution_code="TEST",
            email="user@example.edu",
            password=PASSWORD,
        )


def test_inactive_user_is_rejected_before_password_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    institution = _institution()
    user = _user(institution, active=False)
    password_check_called = False

    def password_check(*_: object) -> bool:
        nonlocal password_check_called
        password_check_called = True
        return True

    monkeypatch.setattr(authentication, "verify_password", password_check)

    with pytest.raises(InactiveAccountError):
        authentication.authenticate_user(
            FakeSession([institution, user]),  # type: ignore[arg-type]
            institution_code="TEST",
            email="user@example.edu",
            password=PASSWORD,
        )

    assert not password_check_called


def test_load_authenticated_user_requires_matching_active_context() -> None:
    institution = _institution()
    user = _user(institution, role_names=("student", "librarian"))

    context = authentication.load_authenticated_user(
        FakeSession([user]),  # type: ignore[arg-type]
        user_id=user.id,
        institution_id=institution.id,
    )

    assert context.roles == ("librarian", "student")

    with pytest.raises(InvalidTokenError):
        authentication.load_authenticated_user(
            FakeSession([None]),  # type: ignore[arg-type]
            user_id=user.id,
            institution_id=uuid4(),
        )


def test_load_authenticated_user_rejects_inactive_user() -> None:
    institution = _institution()
    user = _user(institution, active=False)

    with pytest.raises(InactiveAccountError):
        authentication.load_authenticated_user(
            FakeSession([user]),  # type: ignore[arg-type]
            user_id=user.id,
            institution_id=institution.id,
        )


def test_authentication_service_does_not_print_password(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    institution = _institution()
    user = _user(institution)
    monkeypatch.setattr(authentication, "verify_password", lambda *_: True)

    authentication.authenticate_user(
        FakeSession([institution, user]),  # type: ignore[arg-type]
        institution_code="TEST",
        email="user@example.edu",
        password=PASSWORD,
    )

    captured = capsys.readouterr()
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
