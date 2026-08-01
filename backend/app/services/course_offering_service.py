from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_session import AcademicSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.semester import Semester
from app.schemas.course_offering import (
    CourseOfferingCreate,
    CourseOfferingStatus,
    CourseOfferingUpdate,
)


class CourseOfferingNotFoundError(Exception):
    """Raised when an active offering is absent from an institution."""


class CourseOfferingCourseNotFoundError(Exception):
    """Raised when the selected active Course is unavailable."""


class CourseOfferingAcademicSessionNotFoundError(Exception):
    """Raised when the selected Academic Session is unavailable."""


class CourseOfferingSemesterNotFoundError(Exception):
    """Raised when the selected Semester is unavailable."""


class CourseOfferingHierarchyMismatchError(Exception):
    """Raised when a Semester does not belong to the Academic Session."""


class DuplicateCourseOfferingError(Exception):
    """Raised when a Course already has an offering in the term."""


class InvalidRegistrationWindowError(Exception):
    """Raised when registration dates are invalid or outside the term."""


def create_course_offering(
    session: Session,
    *,
    institution_id: UUID,
    course_offering_data: CourseOfferingCreate,
) -> CourseOffering:
    _, academic_session, semester = _resolve_hierarchy(
        session,
        institution_id=institution_id,
        course_id=course_offering_data.course_id,
        academic_session_id=course_offering_data.academic_session_id,
        semester_id=course_offering_data.semester_id,
    )
    _validate_registration_window(
        registration_start_date=course_offering_data.registration_start_date,
        registration_end_date=course_offering_data.registration_end_date,
        academic_session=academic_session,
        semester=semester,
    )
    _ensure_offering_available(
        session,
        course_id=course_offering_data.course_id,
        academic_session_id=course_offering_data.academic_session_id,
        semester_id=course_offering_data.semester_id,
    )
    course_offering = CourseOffering(
        institution_id=institution_id,
        **course_offering_data.model_dump(),
    )
    session.add(course_offering)
    _commit(session)
    session.refresh(course_offering)
    return course_offering


def list_course_offerings(
    session: Session,
    *,
    institution_id: UUID,
    course_id: UUID | None = None,
    academic_session_id: UUID | None = None,
    semester_id: UUID | None = None,
    registration_open: bool | None = None,
    status: CourseOfferingStatus | None = None,
) -> list[CourseOffering]:
    statement = select(CourseOffering).where(
        CourseOffering.institution_id == institution_id,
        CourseOffering.status == "active",
    )
    if course_id is not None:
        statement = statement.where(CourseOffering.course_id == course_id)
    if academic_session_id is not None:
        statement = statement.where(
            CourseOffering.academic_session_id == academic_session_id
        )
    if semester_id is not None:
        statement = statement.where(CourseOffering.semester_id == semester_id)
    if registration_open is not None:
        statement = statement.where(
            CourseOffering.registration_open == registration_open
        )
    if status is not None:
        statement = statement.where(CourseOffering.status == status)
    return list(
        session.scalars(
            statement.order_by(
                CourseOffering.academic_session_id,
                CourseOffering.semester_id,
                CourseOffering.course_id,
                CourseOffering.id,
            )
        ).all()
    )


def get_course_offering(
    session: Session,
    *,
    course_offering_id: UUID,
    institution_id: UUID,
) -> CourseOffering:
    offering = session.scalar(
        select(CourseOffering).where(
            CourseOffering.id == course_offering_id,
            CourseOffering.institution_id == institution_id,
            CourseOffering.status == "active",
        )
    )
    if offering is None:
        raise CourseOfferingNotFoundError()
    return offering


def update_course_offering(
    session: Session,
    *,
    course_offering_id: UUID,
    institution_id: UUID,
    course_offering_data: CourseOfferingUpdate,
) -> CourseOffering:
    offering = get_course_offering(
        session,
        course_offering_id=course_offering_id,
        institution_id=institution_id,
    )
    changes = course_offering_data.model_dump(exclude_unset=True)
    course_id = changes.get("course_id", offering.course_id)
    academic_session_id = changes.get(
        "academic_session_id",
        offering.academic_session_id,
    )
    semester_id = changes.get("semester_id", offering.semester_id)
    _, academic_session, semester = _resolve_hierarchy(
        session,
        institution_id=institution_id,
        course_id=course_id,
        academic_session_id=academic_session_id,
        semester_id=semester_id,
    )
    registration_start_date = changes.get(
        "registration_start_date",
        offering.registration_start_date,
    )
    registration_end_date = changes.get(
        "registration_end_date",
        offering.registration_end_date,
    )
    _validate_registration_window(
        registration_start_date=registration_start_date,
        registration_end_date=registration_end_date,
        academic_session=academic_session,
        semester=semester,
    )
    _ensure_offering_available(
        session,
        course_id=course_id,
        academic_session_id=academic_session_id,
        semester_id=semester_id,
        exclude_id=offering.id,
    )
    for field, value in changes.items():
        setattr(offering, field, value)
    _commit(session)
    session.refresh(offering)
    return offering


def delete_course_offering(
    session: Session,
    *,
    course_offering_id: UUID,
    institution_id: UUID,
) -> CourseOffering:
    offering = get_course_offering(
        session,
        course_offering_id=course_offering_id,
        institution_id=institution_id,
    )
    offering.status = "inactive"
    _commit(session)
    session.refresh(offering)
    return offering


def _resolve_hierarchy(
    session: Session,
    *,
    institution_id: UUID,
    course_id: UUID,
    academic_session_id: UUID,
    semester_id: UUID,
) -> tuple[Course, AcademicSession, Semester]:
    course = _resolve_course(
        session,
        course_id=course_id,
        institution_id=institution_id,
    )
    academic_session = _resolve_academic_session(
        session,
        academic_session_id=academic_session_id,
        institution_id=institution_id,
    )
    semester = _resolve_semester(
        session,
        semester_id=semester_id,
        institution_id=institution_id,
    )
    if semester.academic_session_id != academic_session.id:
        raise CourseOfferingHierarchyMismatchError()
    return course, academic_session, semester


def _resolve_course(
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
        raise CourseOfferingCourseNotFoundError()
    return course


def _resolve_academic_session(
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
        raise CourseOfferingAcademicSessionNotFoundError()
    return academic_session


def _resolve_semester(
    session: Session,
    *,
    semester_id: UUID,
    institution_id: UUID,
) -> Semester:
    semester = session.scalar(
        select(Semester).where(
            Semester.id == semester_id,
            Semester.institution_id == institution_id,
        )
    )
    if semester is None:
        raise CourseOfferingSemesterNotFoundError()
    return semester


def _validate_registration_window(
    *,
    registration_start_date: date | None,
    registration_end_date: date | None,
    academic_session: AcademicSession,
    semester: Semester,
) -> None:
    if (
        registration_start_date is not None
        and registration_end_date is not None
        and registration_start_date >= registration_end_date
    ):
        raise InvalidRegistrationWindowError()
    for registration_date in (registration_start_date, registration_end_date):
        if registration_date is not None and (
            registration_date < academic_session.start_date
            or registration_date > academic_session.end_date
            or registration_date < semester.start_date
            or registration_date > semester.end_date
        ):
            raise InvalidRegistrationWindowError()


def _ensure_offering_available(
    session: Session,
    *,
    course_id: UUID,
    academic_session_id: UUID,
    semester_id: UUID,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(CourseOffering.id).where(
        CourseOffering.course_id == course_id,
        CourseOffering.academic_session_id == academic_session_id,
        CourseOffering.semester_id == semester_id,
    )
    if exclude_id is not None:
        statement = statement.where(CourseOffering.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateCourseOfferingError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateCourseOfferingError() from error
