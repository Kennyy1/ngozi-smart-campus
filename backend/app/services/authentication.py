from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import verify_password
from app.models.institution import Institution
from app.models.user import User
from app.models.user_role import UserRole


@dataclass(frozen=True)
class AuthenticatedUserContext:
    user: User
    institution: Institution
    roles: tuple[str, ...]


def authenticate_user(
    session: Session,
    *,
    institution_code: str,
    email: str,
    password: str,
) -> AuthenticatedUserContext:
    normalized_code = institution_code.strip()
    normalized_email = email.strip().lower()

    institution = session.scalar(
        select(Institution).where(Institution.code == normalized_code)
    )
    if institution is None or institution.status != "active":
        raise InvalidCredentialsError()

    user = session.scalar(
        select(User)
        .where(
            User.institution_id == institution.id,
            User.email == normalized_email,
        )
        .options(
            selectinload(User.role_assignments).selectinload(UserRole.role)
        )
    )
    if user is None:
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InactiveAccountError()
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()

    # A controlled write transaction may rehash valid passwords here later.
    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=_current_role_names(user, institution.id),
    )


def load_authenticated_user(
    session: Session,
    *,
    user_id: UUID,
    institution_id: UUID,
) -> AuthenticatedUserContext:
    user = session.scalar(
        select(User)
        .where(
            User.id == user_id,
            User.institution_id == institution_id,
        )
        .options(
            selectinload(User.institution),
            selectinload(User.role_assignments).selectinload(UserRole.role),
        )
    )
    if user is None:
        raise InvalidTokenError()
    if not user.is_active:
        raise InactiveAccountError()

    institution = user.institution
    if (
        institution is None
        or institution.id != institution_id
        or institution.status != "active"
    ):
        raise InvalidTokenError()

    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=_current_role_names(user, institution_id),
    )


def _current_role_names(user: User, institution_id: UUID) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                assignment.role.name
                for assignment in user.role_assignments
                if assignment.institution_id == institution_id
                and assignment.role is not None
            }
        )
    )
