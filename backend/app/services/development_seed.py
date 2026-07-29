from dataclasses import dataclass
import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.institution import Institution
from app.models.institution_setting import InstitutionSetting
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


DEVELOPMENT_SETTING_KEY = "timezone"
DEVELOPMENT_SETTING_VALUE = "Africa/Lagos"
ADMINISTRATOR_ROLE = "administrator"
SYSTEM_SUPER_ADMIN_ROLE = "system_super_admin"
DEVELOPMENT_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class DevelopmentSeedResult:
    institution_created: bool
    institution_setting_created: bool
    administrator_role_created: bool
    system_super_admin_role_created: bool
    administrator_user_created: bool
    administrator_role_assigned: bool
    system_super_admin_role_assigned: bool

    @property
    def changed(self) -> bool:
        return any(
            (
                self.institution_created,
                self.institution_setting_created,
                self.administrator_role_created,
                self.system_super_admin_role_created,
                self.administrator_user_created,
                self.administrator_role_assigned,
                self.system_super_admin_role_assigned,
            )
        )


def seed_development_data(
    session: Session,
    *,
    institution_code: str,
    institution_name: str,
    administrator_email: str,
    administrator_password: str,
) -> DevelopmentSeedResult:
    try:
        normalized_code = _normalize_institution_code(institution_code)
        normalized_name = _normalize_institution_name(institution_name)
        normalized_email = _normalize_email(administrator_email)
        _validate_password(administrator_password)

        institution = session.scalar(
            select(Institution).where(Institution.code == normalized_code)
        )
        institution_created = institution is None
        if institution is None:
            institution = Institution(
                id=uuid4(),
                code=normalized_code,
                name=normalized_name,
                status="active",
            )
            session.add(institution)
            session.flush()

        institution_setting = session.scalar(
            select(InstitutionSetting).where(
                InstitutionSetting.institution_id == institution.id,
                InstitutionSetting.setting_key == DEVELOPMENT_SETTING_KEY,
            )
        )
        institution_setting_created = institution_setting is None
        if institution_setting is None:
            session.add(
                InstitutionSetting(
                    id=uuid4(),
                    institution_id=institution.id,
                    setting_key=DEVELOPMENT_SETTING_KEY,
                    setting_value=DEVELOPMENT_SETTING_VALUE,
                    value_type="string",
                    description="Institution time zone for local development.",
                    is_public=False,
                )
            )

        administrator_role, administrator_role_created = _get_or_create_role(
            session,
            ADMINISTRATOR_ROLE,
            "Institution administrator.",
        )
        (
            system_super_admin_role,
            system_super_admin_role_created,
        ) = _get_or_create_role(
            session,
            SYSTEM_SUPER_ADMIN_ROLE,
            "Exceptional platform administrator.",
        )

        administrator_user = session.scalar(
            select(User).where(
                User.institution_id == institution.id,
                User.email == normalized_email,
            )
        )
        administrator_user_created = administrator_user is None
        if administrator_user is None:
            administrator_user = User(
                id=uuid4(),
                institution_id=institution.id,
                email=normalized_email,
                password_hash=hash_password(administrator_password),
                first_name="Development",
                last_name="Administrator",
                is_active=True,
                is_verified=True,
            )
            session.add(administrator_user)
            session.flush()

        administrator_role_assigned = _ensure_role_assignment(
            session,
            user=administrator_user,
            role=administrator_role,
            institution=institution,
        )
        system_super_admin_role_assigned = _ensure_role_assignment(
            session,
            user=administrator_user,
            role=system_super_admin_role,
            institution=institution,
        )

        result = DevelopmentSeedResult(
            institution_created=institution_created,
            institution_setting_created=institution_setting_created,
            administrator_role_created=administrator_role_created,
            system_super_admin_role_created=system_super_admin_role_created,
            administrator_user_created=administrator_user_created,
            administrator_role_assigned=administrator_role_assigned,
            system_super_admin_role_assigned=system_super_admin_role_assigned,
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _get_or_create_role(
    session: Session,
    name: str,
    description: str,
) -> tuple[Role, bool]:
    role = session.scalar(select(Role).where(Role.name == name))
    if role is not None:
        return role, False

    role = Role(id=uuid4(), name=name, description=description)
    session.add(role)
    session.flush()
    return role, True


def _ensure_role_assignment(
    session: Session,
    *,
    user: User,
    role: Role,
    institution: Institution,
) -> bool:
    assignment = session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.institution_id == institution.id,
        )
    )
    if assignment is not None:
        return False

    session.add(
        UserRole(
            id=uuid4(),
            user_id=user.id,
            role_id=role.id,
            institution_id=institution.id,
        )
    )
    return True


def _normalize_institution_code(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("Institution code is required")
    return normalized


def _normalize_institution_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Institution name is required")
    return normalized


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not DEVELOPMENT_EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Administrator email is invalid")
    return normalized


def _validate_password(value: str) -> None:
    if not value:
        raise ValueError("Administrator password is required")
    if "\x00" in value:
        raise ValueError("Administrator password contains invalid characters")


# Concurrent executions remain subject to the database uniqueness constraints.
