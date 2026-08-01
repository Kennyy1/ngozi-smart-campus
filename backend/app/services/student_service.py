from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.academic_level import AcademicLevel
from app.models.programme import Programme
from app.models.student import Student
from app.models.user import User
from app.schemas.student import (
    EnrollmentStatus,
    StudentCreate,
    StudentRead,
    StudentUpdate,
    validate_graduation_state,
)


class StudentNotFoundError(Exception): pass
class StudentProgrammeNotFoundError(Exception): pass
class InvalidStudentCurrentLevelError(Exception): pass
class InvalidStudentGraduationStateError(Exception): pass
class DuplicateStudentEmailError(Exception): pass
class DuplicateMatriculationNumberError(Exception): pass
class DuplicateStudentError(Exception): pass


def create_student(session: Session, *, institution_id: UUID, student_data: StudentCreate) -> StudentRead:
    programme = _resolve_programme(session, programme_id=student_data.programme_id, institution_id=institution_id)
    _validate_current_level(session, programme_id=programme.id, current_level=student_data.current_level)
    _ensure_email_available(session, institution_id=institution_id, email=str(student_data.email))
    _ensure_matriculation_available(session, institution_id=institution_id, matriculation_number=student_data.matriculation_number)
    user = User(
        institution_id=institution_id,
        email=str(student_data.email),
        password_hash=hash_password(student_data.password),
        first_name=student_data.first_name,
        last_name=student_data.last_name,
        phone=student_data.phone,
        is_active=True,
        is_verified=False,
    )
    session.add(user)
    _flush(session)
    student = Student(
        institution_id=institution_id,
        user_id=user.id,
        programme_id=programme.id,
        matriculation_number=student_data.matriculation_number,
        admission_year=student_data.admission_year,
        current_level=student_data.current_level,
        enrollment_status=student_data.enrollment_status.value,
        graduation_date=student_data.graduation_date,
    )
    student.user = user
    session.add(student)
    _commit(session)
    session.refresh(student)
    return _build_student_response(student)


def list_students(
    session: Session,
    *,
    institution_id: UUID,
    programme_id: UUID | None = None,
    enrollment_status: EnrollmentStatus | None = None,
    admission_year: int | None = None,
    current_level: str | None = None,
    is_active: bool | None = None,
) -> list[StudentRead]:
    statement = select(Student).options(joinedload(Student.user)).where(
        Student.institution_id == institution_id,
        Student.enrollment_status != EnrollmentStatus.INACTIVE.value,
    )
    if programme_id is not None:
        statement = statement.where(Student.programme_id == programme_id)
    if enrollment_status is not None:
        statement = statement.where(Student.enrollment_status == enrollment_status.value)
    if admission_year is not None:
        statement = statement.where(Student.admission_year == admission_year)
    if current_level is not None:
        statement = statement.where(Student.current_level == current_level.strip())
    if is_active is not None:
        statement = statement.join(Student.user).where(User.is_active == is_active)
    students = session.scalars(statement.order_by(Student.matriculation_number, Student.id)).all()
    return [_build_student_response(student) for student in students]


def get_student(session: Session, *, student_id: UUID, institution_id: UUID) -> StudentRead:
    return _build_student_response(_get_student_model(session, student_id=student_id, institution_id=institution_id))


def get_student_by_matriculation(session: Session, *, matriculation_number: str, institution_id: UUID) -> StudentRead:
    student = session.scalar(
        select(Student).options(joinedload(Student.user)).where(
            Student.institution_id == institution_id,
            Student.matriculation_number == matriculation_number.strip(),
            Student.enrollment_status != EnrollmentStatus.INACTIVE.value,
        )
    )
    if student is None:
        raise StudentNotFoundError()
    return _build_student_response(student)


def update_student(
    session: Session,
    *,
    student_id: UUID,
    institution_id: UUID,
    student_data: StudentUpdate,
) -> StudentRead:
    student = _get_student_model(session, student_id=student_id, institution_id=institution_id)
    user = student.user
    changes = student_data.model_dump(exclude_unset=True)
    programme_id = changes.get("programme_id", student.programme_id)
    programme = _resolve_programme(session, programme_id=programme_id, institution_id=institution_id)
    current_level = changes.get("current_level", student.current_level)
    _validate_current_level(session, programme_id=programme.id, current_level=current_level)
    enrollment_status = changes.get("enrollment_status", student.enrollment_status)
    graduation_date = changes.get("graduation_date", student.graduation_date)
    try:
        validate_graduation_state(enrollment_status, graduation_date)
    except ValueError as error:
        raise InvalidStudentGraduationStateError() from error
    email = changes.get("email")
    if email is not None and str(email) != user.email:
        _ensure_email_available(session, institution_id=institution_id, email=str(email), exclude_id=user.id)
    matriculation_number = changes.get("matriculation_number")
    if matriculation_number is not None and matriculation_number != student.matriculation_number:
        _ensure_matriculation_available(session, institution_id=institution_id, matriculation_number=matriculation_number, exclude_id=student.id)
    for field in ("email", "first_name", "last_name", "phone", "is_active", "is_verified"):
        if field in changes:
            setattr(user, field, str(changes[field]) if field == "email" else changes[field])
    for field in ("programme_id", "matriculation_number", "admission_year", "current_level", "enrollment_status", "graduation_date"):
        if field in changes:
            value = changes[field]
            setattr(student, field, value.value if isinstance(value, EnrollmentStatus) else value)
    _commit(session)
    session.refresh(student)
    return _build_student_response(student)


def delete_student(session: Session, *, student_id: UUID, institution_id: UUID) -> None:
    student = _get_student_model(session, student_id=student_id, institution_id=institution_id)
    student.enrollment_status = EnrollmentStatus.INACTIVE.value
    student.user.is_active = False
    _commit(session)


def _get_student_model(session: Session, *, student_id: UUID, institution_id: UUID) -> Student:
    student = session.scalar(
        select(Student).options(joinedload(Student.user)).where(
            Student.id == student_id,
            Student.institution_id == institution_id,
            Student.enrollment_status != EnrollmentStatus.INACTIVE.value,
        )
    )
    if student is None:
        raise StudentNotFoundError()
    return student


def _resolve_programme(session: Session, *, programme_id: UUID | None, institution_id: UUID) -> Programme:
    programme = session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.institution_id == institution_id,
            Programme.status == "active",
        )
    )
    if programme is None:
        raise StudentProgrammeNotFoundError()
    return programme


def _validate_current_level(session: Session, *, programme_id: UUID, current_level: str | None) -> None:
    if current_level is None:
        return
    level = session.scalar(
        select(AcademicLevel.id).where(
            AcademicLevel.programme_id == programme_id,
            AcademicLevel.name == current_level,
            AcademicLevel.status == "active",
        )
    )
    if level is None:
        raise InvalidStudentCurrentLevelError()


def _ensure_email_available(session: Session, *, institution_id: UUID, email: str, exclude_id: UUID | None = None) -> None:
    statement = select(User.id).where(User.institution_id == institution_id, User.email == email)
    if exclude_id is not None:
        statement = statement.where(User.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateStudentEmailError()


def _ensure_matriculation_available(session: Session, *, institution_id: UUID, matriculation_number: str, exclude_id: UUID | None = None) -> None:
    statement = select(Student.id).where(Student.institution_id == institution_id, Student.matriculation_number == matriculation_number)
    if exclude_id is not None:
        statement = statement.where(Student.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateMatriculationNumberError()


def _build_student_response(student: Student) -> StudentRead:
    user = student.user
    if student.programme_id is None:
        raise StudentProgrammeNotFoundError()
    return StudentRead(
        id=student.id, institution_id=student.institution_id, user_id=student.user_id,
        email=user.email, first_name=user.first_name, last_name=user.last_name,
        phone=user.phone, programme_id=student.programme_id,
        matriculation_number=student.matriculation_number, admission_year=student.admission_year,
        current_level=student.current_level, enrollment_status=student.enrollment_status,
        graduation_date=student.graduation_date, is_active=user.is_active,
        is_verified=user.is_verified, created_at=student.created_at, updated_at=student.updated_at,
    )


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateStudentError() from error


def _flush(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateStudentError() from error
