from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.models.institution import Institution
from app.models.user import User
from app.services.authentication import AuthenticatedUserContext


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
        email="user@example.edu",
        password_hash="not-exposed",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=tuple(roles),
    )


def test_require_roles_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError):
        dependencies.require_roles()
    with pytest.raises(ValueError):
        dependencies.require_roles("student", "  ")


@pytest.mark.parametrize(
    ("current_roles", "required_roles"),
    [
        (("student",), ("student",)),
        (("AdMiNiStRaToR",), (" administrator ", "librarian")),
    ],
)
def test_matching_current_database_role_is_permitted(
    current_roles: tuple[str, ...],
    required_roles: tuple[str, ...],
) -> None:
    role_dependency = dependencies.require_roles(*required_roles)
    context = _context(*current_roles)

    assert role_dependency(context) is context


def test_missing_current_role_returns_safe_403() -> None:
    role_dependency = dependencies.require_roles("administrator")

    with pytest.raises(HTTPException) as raised:
        role_dependency(_context("student"))

    assert raised.value.status_code == 403
    assert raised.value.detail == "Permission denied"


def test_unauthenticated_request_returns_401() -> None:
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(None, object())  # type: ignore[arg-type]

    assert raised.value.status_code == 401
    assert raised.value.detail == "Authentication required"
