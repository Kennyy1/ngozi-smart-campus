from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.faculty import Faculty
from app.schemas.faculty import FacultyCreate, FacultyUpdate


class FacultyNotFoundError(Exception):
    """Raised when an active faculty cannot be found in an institution."""


class DuplicateFacultyCodeError(Exception):
    """Raised when a faculty code is already used in an institution."""


def create_faculty(
    session: Session,
    *,
    institution_id: UUID,
    faculty_data: FacultyCreate,
) -> Faculty:
    _ensure_code_available(
        session,
        institution_id=institution_id,
        code=faculty_data.code,
    )
    faculty = Faculty(
        institution_id=institution_id,
        status="active",
        **faculty_data.model_dump(),
    )
    session.add(faculty)
    _commit(session)
    session.refresh(faculty)
    return faculty


def list_faculties(session: Session, *, institution_id: UUID) -> list[Faculty]:
    return list(
        session.scalars(
            select(Faculty)
            .where(
                Faculty.institution_id == institution_id,
                Faculty.status == "active",
            )
            .order_by(Faculty.name, Faculty.id)
        ).all()
    )


def get_faculty(
    session: Session,
    *,
    faculty_id: UUID,
    institution_id: UUID,
) -> Faculty:
    faculty = session.scalar(
        select(Faculty).where(
            Faculty.id == faculty_id,
            Faculty.institution_id == institution_id,
            Faculty.status == "active",
        )
    )
    if faculty is None:
        raise FacultyNotFoundError()
    return faculty


def update_faculty(
    session: Session,
    *,
    faculty_id: UUID,
    institution_id: UUID,
    faculty_data: FacultyUpdate,
) -> Faculty:
    faculty = get_faculty(
        session,
        faculty_id=faculty_id,
        institution_id=institution_id,
    )
    changes = faculty_data.model_dump(exclude_unset=True)
    new_code = changes.get("code")
    if new_code is not None and new_code != faculty.code:
        _ensure_code_available(
            session,
            institution_id=institution_id,
            code=new_code,
            exclude_id=faculty.id,
        )
    for field, value in changes.items():
        setattr(faculty, field, value)
    _commit(session)
    session.refresh(faculty)
    return faculty


def delete_faculty(
    session: Session,
    *,
    faculty_id: UUID,
    institution_id: UUID,
) -> Faculty:
    faculty = get_faculty(
        session,
        faculty_id=faculty_id,
        institution_id=institution_id,
    )
    faculty.status = "inactive"
    _commit(session)
    session.refresh(faculty)
    return faculty


def _ensure_code_available(
    session: Session,
    *,
    institution_id: UUID,
    code: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Faculty.id).where(
        Faculty.institution_id == institution_id,
        Faculty.code == code,
    )
    if exclude_id is not None:
        statement = statement.where(Faculty.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateFacultyCodeError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateFacultyCodeError() from error
