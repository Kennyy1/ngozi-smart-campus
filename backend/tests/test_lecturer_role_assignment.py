from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies import require_roles
from app.api.v1.endpoints import auth
from app.models.institution import Institution
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.authentication import AuthenticatedUserContext
from app.services.role_assignment_service import (
    LECTURER_ROLE,
    RoleAssignmentInstitutionMismatchError,
    ensure_user_role,
)


class FakeSession:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.added: list[object] = []

    def scalar(self, statement: object) -> object:
        return self.results.pop(0) if self.results else None

    def add(self, value: object) -> None:
        self.added.append(value)


def _user(institution_id=None, *, email="lecturer001@ngozi.smartcampus.com") -> User:
    institution_id = institution_id or uuid4()
    return User(
        id=uuid4(),
        institution_id=institution_id,
        email=email,
        password_hash="not-exposed",
        first_name="Test",
        last_name="Lecturer",
        is_active=True,
        is_verified=True,
    )


def test_existing_lecturer_role_is_not_duplicated() -> None:
    institution_id = uuid4()
    user = _user(institution_id)
    role = Role(id=uuid4(), name=LECTURER_ROLE)
    assignment = UserRole(
        id=uuid4(),
        user_id=user.id,
        role_id=role.id,
        institution_id=institution_id,
    )
    session = FakeSession(role, assignment)

    changed = ensure_user_role(
        session,  # type: ignore[arg-type]
        user=user,
        institution_id=institution_id,
        role_name=LECTURER_ROLE,
    )

    assert changed is False
    assert session.added == []


def test_role_assignment_rejects_cross_institution_user() -> None:
    with pytest.raises(RoleAssignmentInstitutionMismatchError):
        ensure_user_role(
            FakeSession(),  # type: ignore[arg-type]
            user=_user(uuid4()),
            institution_id=uuid4(),
            role_name=LECTURER_ROLE,
        )


def test_lecturer_me_response_and_portal_authorization_use_assigned_role() -> None:
    institution = Institution(
        id=uuid4(), name="Ngozi University", code="NGOZI", status="active"
    )
    context = AuthenticatedUserContext(
        user=_user(institution.id),
        institution=institution,
        roles=(LECTURER_ROLE,),
    )

    assert auth.get_me(context).roles == [LECTURER_ROLE]
    assert require_roles(LECTURER_ROLE)(context) is context


def test_profile_or_email_does_not_grant_lecturer_authorization() -> None:
    institution = Institution(
        id=uuid4(), name="Ngozi University", code="NGOZI", status="active"
    )
    context = AuthenticatedUserContext(
        user=_user(institution.id, email="lecturer@ngozi.edu"),
        institution=institution,
        roles=(),
    )

    with pytest.raises(HTTPException) as raised:
        require_roles(LECTURER_ROLE)(context)
    assert raised.value.status_code == 403


@pytest.mark.parametrize("roles", [("administrator",), ("student",)])
def test_non_lecturer_role_semantics_are_unchanged(roles: tuple[str, ...]) -> None:
    institution = Institution(
        id=uuid4(), name="Ngozi University", code="NGOZI", status="active"
    )
    context = AuthenticatedUserContext(
        user=_user(institution.id), institution=institution, roles=roles
    )
    assert auth.get_me(context).roles == list(roles)
