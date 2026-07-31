from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.faculty import Faculty
from app.models.programme import Programme
from app.schemas.programme import (
    ProgrammeAward,
    ProgrammeCreate,
    ProgrammeUpdate,
    StudyMode,
)


class ProgrammeNotFoundError(Exception):
    """Raised when an active programme is absent from an institution."""


class ProgrammeFacultyNotFoundError(Exception):
    """Raised when the selected active faculty is unavailable."""


class ProgrammeDepartmentNotFoundError(Exception):
    """Raised when the selected active department is unavailable."""


class DuplicateProgrammeCodeError(Exception):
    """Raised when a programme code is already used in an institution."""


class DuplicateProgrammeNameError(Exception):
    """Raised when a programme name is already used in a department."""


class DuplicateProgrammeError(Exception):
    """Raised for a concurrent programme uniqueness conflict."""


def create_programme(
    session: Session,
    *,
    institution_id: UUID,
    programme_data: ProgrammeCreate,
) -> Programme:
    _validate_hierarchy(
        session,
        institution_id=institution_id,
        faculty_id=programme_data.faculty_id,
        department_id=programme_data.department_id,
    )
    _ensure_code_available(
        session,
        institution_id=institution_id,
        code=programme_data.code,
    )
    _ensure_name_available(
        session,
        department_id=programme_data.department_id,
        name=programme_data.name,
    )
    values = programme_data.model_dump()
    programme = Programme(
        institution_id=institution_id,
        status="active",
        **values,
    )
    session.add(programme)
    _commit(session)
    session.refresh(programme)
    return programme


def list_programmes(
    session: Session,
    *,
    institution_id: UUID,
    faculty_id: UUID | None = None,
    department_id: UUID | None = None,
    award: ProgrammeAward | None = None,
    study_mode: StudyMode | None = None,
) -> list[Programme]:
    statement = select(Programme).where(
        Programme.institution_id == institution_id,
        Programme.status == "active",
    )
    if faculty_id is not None:
        statement = statement.where(Programme.faculty_id == faculty_id)
    if department_id is not None:
        statement = statement.where(Programme.department_id == department_id)
    if award is not None:
        statement = statement.where(Programme.award == award.value)
    if study_mode is not None:
        statement = statement.where(Programme.study_mode == study_mode.value)
    return list(
        session.scalars(
            statement.order_by(Programme.name, Programme.id)
        ).all()
    )


def get_programme(
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
        raise ProgrammeNotFoundError()
    return programme


def update_programme(
    session: Session,
    *,
    programme_id: UUID,
    institution_id: UUID,
    programme_data: ProgrammeUpdate,
) -> Programme:
    programme = get_programme(
        session,
        programme_id=programme_id,
        institution_id=institution_id,
    )
    changes = programme_data.model_dump(exclude_unset=True)
    faculty_id = changes.get("faculty_id", programme.faculty_id)
    department_id = changes.get("department_id", programme.department_id)
    if "faculty_id" in changes or "department_id" in changes:
        _validate_hierarchy(
            session,
            institution_id=institution_id,
            faculty_id=faculty_id,
            department_id=department_id,
        )
    code = changes.get("code")
    if code is not None and code != programme.code:
        _ensure_code_available(
            session,
            institution_id=institution_id,
            code=code,
            exclude_id=programme.id,
        )
    name = changes.get("name", programme.name)
    if department_id != programme.department_id or name != programme.name:
        _ensure_name_available(
            session,
            department_id=department_id,
            name=name,
            exclude_id=programme.id,
        )
    for field, value in changes.items():
        setattr(programme, field, value)
    _commit(session)
    session.refresh(programme)
    return programme


def delete_programme(
    session: Session,
    *,
    programme_id: UUID,
    institution_id: UUID,
) -> Programme:
    programme = get_programme(
        session,
        programme_id=programme_id,
        institution_id=institution_id,
    )
    programme.status = "inactive"
    _commit(session)
    session.refresh(programme)
    return programme


def _validate_hierarchy(
    session: Session,
    *,
    institution_id: UUID,
    faculty_id: UUID,
    department_id: UUID,
) -> None:
    faculty = session.scalar(
        select(Faculty.id).where(
            Faculty.id == faculty_id,
            Faculty.institution_id == institution_id,
            Faculty.status == "active",
        )
    )
    if faculty is None:
        raise ProgrammeFacultyNotFoundError()
    department = session.scalar(
        select(Department.id).where(
            Department.id == department_id,
            Department.faculty_id == faculty_id,
            Department.institution_id == institution_id,
            Department.status == "active",
        )
    )
    if department is None:
        raise ProgrammeDepartmentNotFoundError()


def _ensure_code_available(
    session: Session,
    *,
    institution_id: UUID,
    code: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Programme.id).where(
        Programme.institution_id == institution_id,
        Programme.code == code,
    )
    if exclude_id is not None:
        statement = statement.where(Programme.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateProgrammeCodeError()


def _ensure_name_available(
    session: Session,
    *,
    department_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Programme.id).where(
        Programme.department_id == department_id,
        Programme.name == name,
    )
    if exclude_id is not None:
        statement = statement.where(Programme.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateProgrammeNameError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateProgrammeError() from error
