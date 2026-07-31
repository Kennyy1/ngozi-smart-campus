from datetime import date
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_session import AcademicSession
from app.schemas.academic_session import (
    AcademicSessionCreate,
    AcademicSessionStatus,
    AcademicSessionUpdate,
)


class AcademicSessionNotFoundError(Exception):
    """Raised when an academic session is absent from an institution."""


class DuplicateAcademicSessionNameError(Exception):
    """Raised when a session name is already used in an institution."""


class DuplicateAcademicSessionError(Exception):
    """Raised for a concurrent academic-session constraint conflict."""


class InvalidAcademicSessionDateRangeError(Exception):
    """Raised when an update would produce an invalid date range."""


def create_academic_session(
    session: Session,
    *,
    institution_id: UUID,
    academic_session_data: AcademicSessionCreate,
) -> AcademicSession:
    _ensure_name_available(
        session,
        institution_id=institution_id,
        name=academic_session_data.name,
    )
    values = academic_session_data.model_dump()
    academic_session = AcademicSession(
        institution_id=institution_id,
        **values,
    )
    if academic_session.is_current:
        _unset_current_session(session, institution_id=institution_id)
    session.add(academic_session)
    _commit(session)
    session.refresh(academic_session)
    return academic_session


def list_academic_sessions(
    session: Session,
    *,
    institution_id: UUID,
    status: AcademicSessionStatus | None = None,
    is_current: bool | None = None,
) -> list[AcademicSession]:
    statement = select(AcademicSession).where(
        AcademicSession.institution_id == institution_id,
    )
    if status is not None:
        statement = statement.where(AcademicSession.status == status)
    if is_current is not None:
        statement = statement.where(AcademicSession.is_current == is_current)
    return list(
        session.scalars(
            statement.order_by(
                AcademicSession.start_date.desc(),
                AcademicSession.id,
            )
        ).all()
    )


def get_academic_session(
    session: Session,
    *,
    academic_session_id: UUID,
    institution_id: UUID,
) -> AcademicSession:
    academic_session = session.scalar(
        select(AcademicSession).where(
            AcademicSession.id == academic_session_id,
            AcademicSession.institution_id == institution_id,
        )
    )
    if academic_session is None:
        raise AcademicSessionNotFoundError()
    return academic_session


def get_current_academic_session(
    session: Session,
    *,
    institution_id: UUID,
) -> AcademicSession:
    academic_session = session.scalar(
        select(AcademicSession).where(
            AcademicSession.institution_id == institution_id,
            AcademicSession.is_current.is_(True),
        )
    )
    if academic_session is None:
        raise AcademicSessionNotFoundError()
    return academic_session


def update_academic_session(
    session: Session,
    *,
    academic_session_id: UUID,
    institution_id: UUID,
    academic_session_data: AcademicSessionUpdate,
) -> AcademicSession:
    academic_session = get_academic_session(
        session,
        academic_session_id=academic_session_id,
        institution_id=institution_id,
    )
    changes = academic_session_data.model_dump(exclude_unset=True)
    name = changes.get("name")
    if name is not None and name != academic_session.name:
        _ensure_name_available(
            session,
            institution_id=institution_id,
            name=name,
            exclude_id=academic_session.id,
        )
    start_date = changes.get("start_date", academic_session.start_date)
    end_date = changes.get("end_date", academic_session.end_date)
    _validate_date_range(start_date=start_date, end_date=end_date)
    if changes.get("is_current") is True and not academic_session.is_current:
        _unset_current_session(
            session,
            institution_id=institution_id,
            exclude_id=academic_session.id,
        )
    for field, value in changes.items():
        setattr(academic_session, field, value)
    _commit(session)
    session.refresh(academic_session)
    return academic_session


def delete_academic_session(
    session: Session,
    *,
    academic_session_id: UUID,
    institution_id: UUID,
) -> None:
    academic_session = get_academic_session(
        session,
        academic_session_id=academic_session_id,
        institution_id=institution_id,
    )
    academic_session.is_current = False
    session.delete(academic_session)
    _commit(session)


def _ensure_name_available(
    session: Session,
    *,
    institution_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(AcademicSession.id).where(
        AcademicSession.institution_id == institution_id,
        AcademicSession.name == name,
    )
    if exclude_id is not None:
        statement = statement.where(AcademicSession.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateAcademicSessionNameError()


def _validate_date_range(*, start_date: date, end_date: date) -> None:
    if start_date >= end_date:
        raise InvalidAcademicSessionDateRangeError()


def _unset_current_session(
    session: Session,
    *,
    institution_id: UUID,
    exclude_id: UUID | None = None,
) -> None:
    statement = (
        update(AcademicSession)
        .where(
            AcademicSession.institution_id == institution_id,
            AcademicSession.is_current.is_(True),
        )
        .values(is_current=False)
    )
    if exclude_id is not None:
        statement = statement.where(AcademicSession.id != exclude_id)
    session.execute(statement)


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateAcademicSessionError() from error
