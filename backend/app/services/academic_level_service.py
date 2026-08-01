from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_level import AcademicLevel
from app.models.programme import Programme
from app.schemas.academic_level import (
    AcademicLevelCreate,
    AcademicLevelStatus,
    AcademicLevelUpdate,
)


class AcademicLevelNotFoundError(Exception):
    """Raised when an active Academic Level is absent from an institution."""


class AcademicLevelProgrammeNotFoundError(Exception):
    """Raised when the selected active Programme is unavailable."""


class DuplicateAcademicLevelNameError(Exception):
    """Raised when a name is already used in a Programme."""


class DuplicateAcademicLevelCodeError(Exception):
    """Raised when a code is already used in a Programme."""


class DuplicateAcademicLevelSequenceError(Exception):
    """Raised when a sequence number is already used in a Programme."""


class DuplicateAcademicLevelError(Exception):
    """Raised for a concurrent Academic Level uniqueness conflict."""


def create_academic_level(
    session: Session,
    *,
    institution_id: UUID,
    academic_level_data: AcademicLevelCreate,
) -> AcademicLevel:
    programme = _resolve_programme(
        session,
        programme_id=academic_level_data.programme_id,
        institution_id=institution_id,
    )
    _ensure_name_available(
        session,
        programme_id=programme.id,
        name=academic_level_data.name,
    )
    _ensure_code_available(
        session,
        programme_id=programme.id,
        code=academic_level_data.code,
    )
    _ensure_sequence_available(
        session,
        programme_id=programme.id,
        sequence_number=academic_level_data.sequence_number,
    )
    academic_level = AcademicLevel(
        institution_id=institution_id,
        **academic_level_data.model_dump(),
    )
    session.add(academic_level)
    _commit(session)
    session.refresh(academic_level)
    return academic_level


def list_academic_levels(
    session: Session,
    *,
    institution_id: UUID,
    programme_id: UUID | None = None,
    status: AcademicLevelStatus | None = None,
) -> list[AcademicLevel]:
    statement = select(AcademicLevel).where(
        AcademicLevel.institution_id == institution_id,
        AcademicLevel.status == "active",
    )
    if programme_id is not None:
        statement = statement.where(AcademicLevel.programme_id == programme_id)
    if status is not None:
        statement = statement.where(AcademicLevel.status == status)
    return list(
        session.scalars(
            statement.order_by(
                AcademicLevel.sequence_number,
                AcademicLevel.name,
                AcademicLevel.id,
            )
        ).all()
    )


def get_academic_level(
    session: Session,
    *,
    academic_level_id: UUID,
    institution_id: UUID,
) -> AcademicLevel:
    academic_level = session.scalar(
        select(AcademicLevel).where(
            AcademicLevel.id == academic_level_id,
            AcademicLevel.institution_id == institution_id,
            AcademicLevel.status == "active",
        )
    )
    if academic_level is None:
        raise AcademicLevelNotFoundError()
    return academic_level


def update_academic_level(
    session: Session,
    *,
    academic_level_id: UUID,
    institution_id: UUID,
    academic_level_data: AcademicLevelUpdate,
) -> AcademicLevel:
    academic_level = get_academic_level(
        session,
        academic_level_id=academic_level_id,
        institution_id=institution_id,
    )
    changes = academic_level_data.model_dump(exclude_unset=True)
    programme_id = changes.get("programme_id", academic_level.programme_id)
    if "programme_id" in changes:
        _resolve_programme(
            session,
            programme_id=programme_id,
            institution_id=institution_id,
        )

    name = changes.get("name", academic_level.name)
    code = changes.get("code", academic_level.code)
    sequence_number = changes.get(
        "sequence_number",
        academic_level.sequence_number,
    )
    if programme_id != academic_level.programme_id or name != academic_level.name:
        _ensure_name_available(
            session,
            programme_id=programme_id,
            name=name,
            exclude_id=academic_level.id,
        )
    if programme_id != academic_level.programme_id or code != academic_level.code:
        _ensure_code_available(
            session,
            programme_id=programme_id,
            code=code,
            exclude_id=academic_level.id,
        )
    if (
        programme_id != academic_level.programme_id
        or sequence_number != academic_level.sequence_number
    ):
        _ensure_sequence_available(
            session,
            programme_id=programme_id,
            sequence_number=sequence_number,
            exclude_id=academic_level.id,
        )
    for field, value in changes.items():
        setattr(academic_level, field, value)
    _commit(session)
    session.refresh(academic_level)
    return academic_level


def delete_academic_level(
    session: Session,
    *,
    academic_level_id: UUID,
    institution_id: UUID,
) -> AcademicLevel:
    academic_level = get_academic_level(
        session,
        academic_level_id=academic_level_id,
        institution_id=institution_id,
    )
    academic_level.status = "inactive"
    _commit(session)
    session.refresh(academic_level)
    return academic_level


def _resolve_programme(
    session: Session,
    *,
    programme_id: UUID,
    institution_id: UUID,
) -> Programme:
    programme = session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.institution_id == institution_id,
            Programme.status == "active",
        )
    )
    if programme is None:
        raise AcademicLevelProgrammeNotFoundError()
    return programme


def _ensure_name_available(
    session: Session,
    *,
    programme_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(AcademicLevel.id).where(
        AcademicLevel.programme_id == programme_id,
        AcademicLevel.name == name,
    )
    if exclude_id is not None:
        statement = statement.where(AcademicLevel.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateAcademicLevelNameError()


def _ensure_code_available(
    session: Session,
    *,
    programme_id: UUID,
    code: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(AcademicLevel.id).where(
        AcademicLevel.programme_id == programme_id,
        AcademicLevel.code == code,
    )
    if exclude_id is not None:
        statement = statement.where(AcademicLevel.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateAcademicLevelCodeError()


def _ensure_sequence_available(
    session: Session,
    *,
    programme_id: UUID,
    sequence_number: int,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(AcademicLevel.id).where(
        AcademicLevel.programme_id == programme_id,
        AcademicLevel.sequence_number == sequence_number,
    )
    if exclude_id is not None:
        statement = statement.where(AcademicLevel.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateAcademicLevelSequenceError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateAcademicLevelError() from error
