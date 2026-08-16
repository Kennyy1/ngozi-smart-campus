from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.department import Department
from app.models.lecturer import Lecturer
from app.models.user import User
from app.services.role_assignment_service import (
    LECTURER_ROLE,
    LECTURER_ROLE_DESCRIPTION,
    ensure_user_role,
)
from app.schemas.lecturer import AcademicRank, EmploymentStatus, LecturerCreate, LecturerRead, LecturerUpdate


class LecturerNotFoundError(Exception): pass
class LecturerDepartmentNotFoundError(Exception): pass
class DuplicateLecturerEmailError(Exception): pass
class DuplicateStaffNumberError(Exception): pass
class DuplicateLecturerError(Exception): pass


def create_lecturer(session: Session, *, institution_id: UUID, lecturer_data: LecturerCreate) -> LecturerRead:
    department = _resolve_department(session, department_id=lecturer_data.department_id, institution_id=institution_id)
    _ensure_email_available(session, institution_id=institution_id, email=str(lecturer_data.email))
    _ensure_staff_number_available(session, institution_id=institution_id, staff_number=lecturer_data.staff_number)
    user = User(institution_id=institution_id, email=str(lecturer_data.email), password_hash=hash_password(lecturer_data.password), first_name=lecturer_data.first_name, last_name=lecturer_data.last_name, phone=lecturer_data.phone, is_active=True, is_verified=False)
    session.add(user); _flush(session)
    lecturer = Lecturer(institution_id=institution_id, user_id=user.id, department_id=department.id, staff_number=lecturer_data.staff_number, academic_rank=lecturer_data.academic_rank.value, specialization=lecturer_data.specialization, employment_status=lecturer_data.employment_status.value, employment_date=lecturer_data.employment_date, office_location=lecturer_data.office_location)
    lecturer.user = user
    session.add(lecturer)
    ensure_user_role(
        session,
        user=user,
        institution_id=institution_id,
        role_name=LECTURER_ROLE,
        role_description=LECTURER_ROLE_DESCRIPTION,
    )
    _commit(session); session.refresh(lecturer)
    return _build_lecturer_response(lecturer)


def list_lecturers(session: Session, *, institution_id: UUID, department_id: UUID | None = None, academic_rank: AcademicRank | None = None, employment_status: EmploymentStatus | None = None, is_active: bool | None = None) -> list[LecturerRead]:
    statement = select(Lecturer).options(joinedload(Lecturer.user)).where(Lecturer.institution_id == institution_id, Lecturer.employment_status != EmploymentStatus.INACTIVE.value)
    if department_id is not None: statement = statement.where(Lecturer.department_id == department_id)
    if academic_rank is not None: statement = statement.where(Lecturer.academic_rank == academic_rank.value)
    if employment_status is not None: statement = statement.where(Lecturer.employment_status == employment_status.value)
    if is_active is not None: statement = statement.join(Lecturer.user).where(User.is_active == is_active)
    return [_build_lecturer_response(item) for item in session.scalars(statement.order_by(Lecturer.staff_number, Lecturer.id)).all()]


def get_lecturer(session: Session, *, lecturer_id: UUID, institution_id: UUID) -> LecturerRead:
    return _build_lecturer_response(_get_lecturer_model(session, lecturer_id=lecturer_id, institution_id=institution_id))


def get_lecturer_by_staff_number(session: Session, *, staff_number: str, institution_id: UUID) -> LecturerRead:
    lecturer = session.scalar(select(Lecturer).options(joinedload(Lecturer.user)).where(Lecturer.institution_id == institution_id, Lecturer.staff_number == staff_number.strip(), Lecturer.employment_status != EmploymentStatus.INACTIVE.value))
    if lecturer is None: raise LecturerNotFoundError()
    return _build_lecturer_response(lecturer)


def update_lecturer(session: Session, *, lecturer_id: UUID, institution_id: UUID, lecturer_data: LecturerUpdate) -> LecturerRead:
    lecturer = _get_lecturer_model(session, lecturer_id=lecturer_id, institution_id=institution_id); user = lecturer.user
    changes = lecturer_data.model_dump(exclude_unset=True)
    department = _resolve_department(session, department_id=changes.get("department_id", lecturer.department_id), institution_id=institution_id)
    email = changes.get("email")
    if email is not None and str(email) != user.email: _ensure_email_available(session, institution_id=institution_id, email=str(email), exclude_id=user.id)
    staff_number = changes.get("staff_number")
    if staff_number is not None and staff_number != lecturer.staff_number: _ensure_staff_number_available(session, institution_id=institution_id, staff_number=staff_number, exclude_id=lecturer.id)
    for field in ("email", "first_name", "last_name", "phone", "is_active", "is_verified"):
        if field in changes: setattr(user, field, str(changes[field]) if field == "email" else changes[field])
    lecturer.department_id = department.id
    for field in ("staff_number", "academic_rank", "specialization", "employment_status", "employment_date", "office_location"):
        if field in changes:
            value = changes[field]; setattr(lecturer, field, value.value if isinstance(value, (AcademicRank, EmploymentStatus)) else value)
    _commit(session); session.refresh(lecturer); return _build_lecturer_response(lecturer)


def delete_lecturer(session: Session, *, lecturer_id: UUID, institution_id: UUID) -> None:
    lecturer = _get_lecturer_model(session, lecturer_id=lecturer_id, institution_id=institution_id)
    lecturer.employment_status = EmploymentStatus.INACTIVE.value; lecturer.user.is_active = False; _commit(session)


def _get_lecturer_model(session: Session, *, lecturer_id: UUID, institution_id: UUID) -> Lecturer:
    lecturer = session.scalar(select(Lecturer).options(joinedload(Lecturer.user)).where(Lecturer.id == lecturer_id, Lecturer.institution_id == institution_id, Lecturer.employment_status != EmploymentStatus.INACTIVE.value))
    if lecturer is None: raise LecturerNotFoundError()
    return lecturer


def _resolve_department(session: Session, *, department_id: UUID, institution_id: UUID) -> Department:
    department = session.scalar(select(Department).where(Department.id == department_id, Department.institution_id == institution_id, Department.status == "active"))
    if department is None: raise LecturerDepartmentNotFoundError()
    return department


def _ensure_email_available(session: Session, *, institution_id: UUID, email: str, exclude_id: UUID | None = None) -> None:
    statement = select(User.id).where(User.institution_id == institution_id, User.email == email)
    if exclude_id is not None: statement = statement.where(User.id != exclude_id)
    if session.scalar(statement) is not None: raise DuplicateLecturerEmailError()


def _ensure_staff_number_available(session: Session, *, institution_id: UUID, staff_number: str, exclude_id: UUID | None = None) -> None:
    statement = select(Lecturer.id).where(Lecturer.institution_id == institution_id, Lecturer.staff_number == staff_number)
    if exclude_id is not None: statement = statement.where(Lecturer.id != exclude_id)
    if session.scalar(statement) is not None: raise DuplicateStaffNumberError()


def _build_lecturer_response(lecturer: Lecturer) -> LecturerRead:
    user = lecturer.user
    return LecturerRead(id=lecturer.id, institution_id=lecturer.institution_id, user_id=lecturer.user_id, email=user.email, first_name=user.first_name, last_name=user.last_name, phone=user.phone, department_id=lecturer.department_id, staff_number=lecturer.staff_number, academic_rank=lecturer.academic_rank, specialization=lecturer.specialization, employment_status=lecturer.employment_status, employment_date=lecturer.employment_date, office_location=lecturer.office_location, is_active=user.is_active, is_verified=user.is_verified, created_at=lecturer.created_at, updated_at=lecturer.updated_at)


def _commit(session: Session) -> None:
    try: session.commit()
    except IntegrityError as error: session.rollback(); raise DuplicateLecturerError() from error


def _flush(session: Session) -> None:
    try: session.flush()
    except IntegrityError as error: session.rollback(); raise DuplicateLecturerError() from error
