from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.institution import Institution
from app.models.lecturer import Lecturer
from app.models.user import User
from app.models.user_role import UserRole


LECTURER_ROLE = "lecturer"
LECTURER_ROLE_DESCRIPTION = "Institution lecturer."


class RoleAssignmentInstitutionMismatchError(Exception):
    pass


class LecturerRoleRepairTargetNotFoundError(Exception):
    pass


def ensure_user_role(
    session: Session,
    *,
    user: User,
    institution_id: UUID,
    role_name: str,
    role_description: str | None = None,
) -> bool:
    """Ensure one institution-scoped assignment, returning whether it was added."""
    if user.institution_id != institution_id:
        raise RoleAssignmentInstitutionMismatchError()

    role = session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(
            id=uuid4(),
            name=role_name,
            description=role_description,
        )
        session.add(role)

    assignment = session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.institution_id == institution_id,
        )
    )
    if assignment is not None:
        return False

    session.add(
        UserRole(
            id=uuid4(),
            user_id=user.id,
            role_id=role.id,
            institution_id=institution_id,
        )
    )
    return True


def repair_lecturer_role(
    session: Session,
    *,
    user_id: UUID,
    institution_code: str,
) -> bool:
    """Idempotently repair a Lecturer User selected explicitly by ID."""
    try:
        institution = session.scalar(
            select(Institution).where(
                Institution.code == institution_code.strip().upper(),
                Institution.status == "active",
            )
        )
        if institution is None:
            raise LecturerRoleRepairTargetNotFoundError()

        user = session.scalar(
            select(User).where(
                User.id == user_id,
                User.institution_id == institution.id,
            )
        )
        if user is None:
            raise LecturerRoleRepairTargetNotFoundError()

        lecturer_id = session.scalar(
            select(Lecturer.id).where(
                Lecturer.user_id == user.id,
                Lecturer.institution_id == institution.id,
                Lecturer.employment_status != "inactive",
            )
        )
        if lecturer_id is None:
            raise LecturerRoleRepairTargetNotFoundError()

        changed = ensure_user_role(
            session,
            user=user,
            institution_id=institution.id,
            role_name=LECTURER_ROLE,
            role_description=LECTURER_ROLE_DESCRIPTION,
        )
        session.commit()
        return changed
    except Exception:
        session.rollback()
        raise
