from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.faculty import Faculty
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentNotFoundError(Exception):
    """Raised when an active department is absent from an institution."""


class DepartmentFacultyNotFoundError(Exception):
    """Raised when the selected active faculty is unavailable."""


class DuplicateDepartmentCodeError(Exception):
    """Raised when a department code is already used in an institution."""


class DuplicateDepartmentNameError(Exception):
    """Raised when a department name is already used in a faculty."""


class DuplicateDepartmentError(Exception):
    """Raised for a concurrent department uniqueness conflict."""


def create_department(
    session: Session,
    *,
    institution_id: UUID,
    department_data: DepartmentCreate,
) -> Department:
    _get_active_faculty(
        session,
        faculty_id=department_data.faculty_id,
        institution_id=institution_id,
    )
    _ensure_code_available(
        session,
        institution_id=institution_id,
        code=department_data.code,
    )
    _ensure_name_available(
        session,
        faculty_id=department_data.faculty_id,
        name=department_data.name,
    )
    department = Department(
        institution_id=institution_id,
        status="active",
        **department_data.model_dump(),
    )
    session.add(department)
    _commit(session)
    session.refresh(department)
    return department


def list_departments(
    session: Session,
    *,
    institution_id: UUID,
    faculty_id: UUID | None = None,
) -> list[Department]:
    statement = select(Department).where(
        Department.institution_id == institution_id,
        Department.status == "active",
    )
    if faculty_id is not None:
        statement = statement.where(Department.faculty_id == faculty_id)
    return list(
        session.scalars(
            statement.order_by(Department.name, Department.id)
        ).all()
    )


def get_department(
    session: Session,
    *,
    department_id: UUID,
    institution_id: UUID,
) -> Department:
    department = session.scalar(
        select(Department).where(
            Department.id == department_id,
            Department.institution_id == institution_id,
            Department.status == "active",
        )
    )
    if department is None:
        raise DepartmentNotFoundError()
    return department


def update_department(
    session: Session,
    *,
    department_id: UUID,
    institution_id: UUID,
    department_data: DepartmentUpdate,
) -> Department:
    department = get_department(
        session,
        department_id=department_id,
        institution_id=institution_id,
    )
    changes = department_data.model_dump(exclude_unset=True)
    faculty_id = changes.get("faculty_id", department.faculty_id)
    if "faculty_id" in changes:
        _get_active_faculty(
            session,
            faculty_id=faculty_id,
            institution_id=institution_id,
        )
    code = changes.get("code")
    if code is not None and code != department.code:
        _ensure_code_available(
            session,
            institution_id=institution_id,
            code=code,
            exclude_id=department.id,
        )
    name = changes.get("name", department.name)
    if faculty_id != department.faculty_id or name != department.name:
        _ensure_name_available(
            session,
            faculty_id=faculty_id,
            name=name,
            exclude_id=department.id,
        )
    for field, value in changes.items():
        setattr(department, field, value)
    _commit(session)
    session.refresh(department)
    return department


def delete_department(
    session: Session,
    *,
    department_id: UUID,
    institution_id: UUID,
) -> Department:
    department = get_department(
        session,
        department_id=department_id,
        institution_id=institution_id,
    )
    department.status = "inactive"
    _commit(session)
    session.refresh(department)
    return department


def _get_active_faculty(
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
        raise DepartmentFacultyNotFoundError()
    return faculty


def _ensure_code_available(
    session: Session,
    *,
    institution_id: UUID,
    code: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Department.id).where(
        Department.institution_id == institution_id,
        Department.code == code,
    )
    if exclude_id is not None:
        statement = statement.where(Department.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateDepartmentCodeError()


def _ensure_name_available(
    session: Session,
    *,
    faculty_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Department.id).where(
        Department.faculty_id == faculty_id,
        Department.name == name,
    )
    if exclude_id is not None:
        statement = statement.where(Department.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateDepartmentNameError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateDepartmentError() from error
