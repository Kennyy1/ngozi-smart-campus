from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_level import AcademicLevel
from app.models.course import Course
from app.models.department import Department
from app.models.programme import Programme
from app.schemas.course import CourseCreate, CourseStatus, CourseType, CourseUpdate


class CourseNotFoundError(Exception):
    """Raised when an active Course is absent from an institution."""


class CourseDepartmentNotFoundError(Exception):
    """Raised when the selected active Department is unavailable."""


class CourseProgrammeNotFoundError(Exception):
    """Raised when the selected active Programme is unavailable."""


class CourseAcademicLevelNotFoundError(Exception):
    """Raised when the selected active Academic Level is unavailable."""


class CourseHierarchyMismatchError(Exception):
    """Raised when Department, Programme, and Academic Level do not align."""


class DuplicateCourseCodeError(Exception):
    """Raised when a Course code is already used in an institution."""


class DuplicateCourseTitleError(Exception):
    """Raised when a title is already used in a Programme and Level."""


class DuplicateCourseError(Exception):
    """Raised for a concurrent Course uniqueness conflict."""


def create_course(
    session: Session,
    *,
    institution_id: UUID,
    course_data: CourseCreate,
) -> Course:
    _validate_hierarchy(
        session,
        institution_id=institution_id,
        department_id=course_data.department_id,
        programme_id=course_data.programme_id,
        academic_level_id=course_data.academic_level_id,
    )
    _ensure_code_available(
        session,
        institution_id=institution_id,
        code=course_data.code,
    )
    _ensure_title_available(
        session,
        programme_id=course_data.programme_id,
        academic_level_id=course_data.academic_level_id,
        title=course_data.title,
    )
    course = Course(institution_id=institution_id, **course_data.model_dump())
    session.add(course)
    _commit(session)
    session.refresh(course)
    return course


def list_courses(
    session: Session,
    *,
    institution_id: UUID,
    department_id: UUID | None = None,
    programme_id: UUID | None = None,
    academic_level_id: UUID | None = None,
    course_type: CourseType | None = None,
    status: CourseStatus | None = None,
) -> list[Course]:
    statement = select(Course).where(
        Course.institution_id == institution_id,
        Course.status == "active",
    )
    if department_id is not None:
        statement = statement.where(Course.department_id == department_id)
    if programme_id is not None:
        statement = statement.where(Course.programme_id == programme_id)
    if academic_level_id is not None:
        statement = statement.where(Course.academic_level_id == academic_level_id)
    if course_type is not None:
        statement = statement.where(Course.course_type == course_type.value)
    if status is not None:
        statement = statement.where(Course.status == status)
    return list(session.scalars(statement.order_by(Course.code, Course.id)).all())


def get_course(
    session: Session,
    *,
    course_id: UUID,
    institution_id: UUID,
) -> Course:
    course = session.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.institution_id == institution_id,
            Course.status == "active",
        )
    )
    if course is None:
        raise CourseNotFoundError()
    return course


def update_course(
    session: Session,
    *,
    course_id: UUID,
    institution_id: UUID,
    course_data: CourseUpdate,
) -> Course:
    course = get_course(
        session,
        course_id=course_id,
        institution_id=institution_id,
    )
    changes = course_data.model_dump(exclude_unset=True)
    department_id = changes.get("department_id", course.department_id)
    programme_id = changes.get("programme_id", course.programme_id)
    academic_level_id = changes.get(
        "academic_level_id",
        course.academic_level_id,
    )
    _validate_hierarchy(
        session,
        institution_id=institution_id,
        department_id=department_id,
        programme_id=programme_id,
        academic_level_id=academic_level_id,
    )
    code = changes.get("code", course.code)
    if code != course.code:
        _ensure_code_available(
            session,
            institution_id=institution_id,
            code=code,
            exclude_id=course.id,
        )
    title = changes.get("title", course.title)
    if (
        programme_id != course.programme_id
        or academic_level_id != course.academic_level_id
        or title != course.title
    ):
        _ensure_title_available(
            session,
            programme_id=programme_id,
            academic_level_id=academic_level_id,
            title=title,
            exclude_id=course.id,
        )
    for field, value in changes.items():
        setattr(course, field, value)
    _commit(session)
    session.refresh(course)
    return course


def delete_course(
    session: Session,
    *,
    course_id: UUID,
    institution_id: UUID,
) -> Course:
    course = get_course(
        session,
        course_id=course_id,
        institution_id=institution_id,
    )
    course.status = "inactive"
    _commit(session)
    session.refresh(course)
    return course


def _validate_hierarchy(
    session: Session,
    *,
    institution_id: UUID,
    department_id: UUID,
    programme_id: UUID,
    academic_level_id: UUID,
) -> None:
    department = _resolve_department(
        session,
        department_id=department_id,
        institution_id=institution_id,
    )
    programme = _resolve_programme(
        session,
        programme_id=programme_id,
        institution_id=institution_id,
    )
    if programme.department_id != department.id:
        raise CourseHierarchyMismatchError()
    academic_level = _resolve_academic_level(
        session,
        academic_level_id=academic_level_id,
        institution_id=institution_id,
    )
    if academic_level.programme_id != programme.id:
        raise CourseHierarchyMismatchError()


def _resolve_department(
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
        raise CourseDepartmentNotFoundError()
    return department


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
        raise CourseProgrammeNotFoundError()
    return programme


def _resolve_academic_level(
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
        raise CourseAcademicLevelNotFoundError()
    return academic_level


def _ensure_code_available(
    session: Session,
    *,
    institution_id: UUID,
    code: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Course.id).where(
        Course.institution_id == institution_id,
        Course.code == code,
    )
    if exclude_id is not None:
        statement = statement.where(Course.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateCourseCodeError()


def _ensure_title_available(
    session: Session,
    *,
    programme_id: UUID,
    academic_level_id: UUID,
    title: str,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(Course.id).where(
        Course.programme_id == programme_id,
        Course.academic_level_id == academic_level_id,
        Course.title == title,
    )
    if exclude_id is not None:
        statement = statement.where(Course.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateCourseTitleError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateCourseError() from error
