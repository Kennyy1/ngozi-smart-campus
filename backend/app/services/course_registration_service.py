from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.student import Student
from app.schemas.course_registration import (
    CourseRegistrationCreate,
    CourseRegistrationUpdate,
    RegistrationStatus,
)


class CourseRegistrationNotFoundError(Exception):
    """Raised when an active registration is absent from an institution."""


class CourseRegistrationStudentNotFoundError(Exception):
    """Raised when the selected Student is unavailable."""


class CourseRegistrationOfferingNotFoundError(Exception):
    """Raised when the selected Course Offering is unavailable."""


class CourseRegistrationOfferingUnavailableError(Exception):
    """Raised when an Offering is inactive or registration is closed."""


class CourseRegistrationWindowError(Exception):
    """Raised when registration occurs outside the configured window."""


class DuplicateCourseRegistrationError(Exception):
    """Raised when a Student already has a registration for an Offering."""


class CourseOfferingCapacityError(Exception):
    """Raised when an Offering has no remaining capacity."""


class StudentCourseCompatibilityError(Exception):
    """Raised when a Student's Programme does not match the Course."""


def create_course_registration(
    session: Session,
    *,
    institution_id: UUID,
    course_registration_data: CourseRegistrationCreate,
) -> CourseRegistration:
    student = _resolve_student(
        session,
        student_id=course_registration_data.student_id,
        institution_id=institution_id,
    )
    offering = _resolve_offering(
        session,
        course_offering_id=course_registration_data.course_offering_id,
        institution_id=institution_id,
    )
    now = datetime.now(UTC)
    _validate_offering_availability(offering=offering, now=now)
    _validate_student_compatibility(
        session,
        student=student,
        offering=offering,
        institution_id=institution_id,
    )
    _ensure_registration_available(
        session,
        student_id=student.id,
        course_offering_id=offering.id,
    )
    _ensure_capacity_available(session, offering=offering)
    registration = CourseRegistration(
        institution_id=institution_id,
        student_id=student.id,
        course_offering_id=offering.id,
        registration_status=RegistrationStatus.REGISTERED.value,
        registered_at=now,
        dropped_at=None,
        status="active",
        notes=course_registration_data.notes,
    )
    session.add(registration)
    _commit(session)
    session.refresh(registration)
    return registration


def list_course_registrations(
    session: Session,
    *,
    institution_id: UUID,
    student_id: UUID | None = None,
    course_offering_id: UUID | None = None,
    registration_status: RegistrationStatus | None = None,
) -> list[CourseRegistration]:
    statement = select(CourseRegistration).where(
        CourseRegistration.institution_id == institution_id,
        CourseRegistration.status == "active",
    )
    if student_id is not None:
        statement = statement.where(CourseRegistration.student_id == student_id)
    if course_offering_id is not None:
        statement = statement.where(
            CourseRegistration.course_offering_id == course_offering_id
        )
    if registration_status is not None:
        statement = statement.where(
            CourseRegistration.registration_status == registration_status.value
        )
    return list(
        session.scalars(
            statement.order_by(
                CourseRegistration.registered_at.desc(),
                CourseRegistration.id,
            )
        ).all()
    )


def get_course_registration(
    session: Session,
    *,
    course_registration_id: UUID,
    institution_id: UUID,
) -> CourseRegistration:
    registration = session.scalar(
        select(CourseRegistration).where(
            CourseRegistration.id == course_registration_id,
            CourseRegistration.institution_id == institution_id,
            CourseRegistration.status == "active",
        )
    )
    if registration is None:
        raise CourseRegistrationNotFoundError()
    return registration


def update_course_registration(
    session: Session,
    *,
    course_registration_id: UUID,
    institution_id: UUID,
    course_registration_data: CourseRegistrationUpdate,
) -> CourseRegistration:
    registration = get_course_registration(
        session,
        course_registration_id=course_registration_id,
        institution_id=institution_id,
    )
    changes = course_registration_data.model_dump(exclude_unset=True)
    new_status = changes.get("registration_status")
    now = datetime.now(UTC)
    if (
        new_status == RegistrationStatus.DROPPED
        and registration.registration_status != RegistrationStatus.DROPPED.value
    ):
        registration.registration_status = RegistrationStatus.DROPPED.value
        registration.dropped_at = now
    elif (
        new_status == RegistrationStatus.REGISTERED
        and registration.registration_status != RegistrationStatus.REGISTERED.value
    ):
        student = _resolve_student(
            session,
            student_id=registration.student_id,
            institution_id=institution_id,
        )
        offering = _resolve_offering(
            session,
            course_offering_id=registration.course_offering_id,
            institution_id=institution_id,
        )
        _validate_offering_availability(offering=offering, now=now)
        _validate_student_compatibility(
            session,
            student=student,
            offering=offering,
            institution_id=institution_id,
        )
        _ensure_registration_available(
            session,
            student_id=student.id,
            course_offering_id=offering.id,
            exclude_id=registration.id,
        )
        _ensure_capacity_available(session, offering=offering)
        registration.registration_status = RegistrationStatus.REGISTERED.value
        registration.dropped_at = None
    if "notes" in changes:
        registration.notes = changes["notes"]
    _commit(session)
    session.refresh(registration)
    return registration


def delete_course_registration(
    session: Session,
    *,
    course_registration_id: UUID,
    institution_id: UUID,
) -> CourseRegistration:
    registration = get_course_registration(
        session,
        course_registration_id=course_registration_id,
        institution_id=institution_id,
    )
    registration.status = "inactive"
    _commit(session)
    session.refresh(registration)
    return registration


def _resolve_student(
    session: Session,
    *,
    student_id: UUID,
    institution_id: UUID,
) -> Student:
    student = session.scalar(
        select(Student).where(
            Student.id == student_id,
            Student.institution_id == institution_id,
        )
    )
    if student is None:
        raise CourseRegistrationStudentNotFoundError()
    return student


def _resolve_offering(
    session: Session,
    *,
    course_offering_id: UUID,
    institution_id: UUID,
) -> CourseOffering:
    offering = session.scalar(
        select(CourseOffering).where(
            CourseOffering.id == course_offering_id,
            CourseOffering.institution_id == institution_id,
        )
    )
    if offering is None:
        raise CourseRegistrationOfferingNotFoundError()
    return offering


def _validate_offering_availability(
    *,
    offering: CourseOffering,
    now: datetime,
) -> None:
    if offering.status != "active" or not offering.registration_open:
        raise CourseRegistrationOfferingUnavailableError()
    today = now.date()
    if (
        offering.registration_start_date is not None
        and today < offering.registration_start_date
    ) or (
        offering.registration_end_date is not None
        and today > offering.registration_end_date
    ):
        raise CourseRegistrationWindowError()


def _validate_student_compatibility(
    session: Session,
    *,
    student: Student,
    offering: CourseOffering,
    institution_id: UUID,
) -> None:
    if student.programme_id is None:
        return
    course = session.scalar(
        select(Course).where(
            Course.id == offering.course_id,
            Course.institution_id == institution_id,
            Course.status == "active",
        )
    )
    if course is None or course.programme_id != student.programme_id:
        raise StudentCourseCompatibilityError()


def _ensure_registration_available(
    session: Session,
    *,
    student_id: UUID,
    course_offering_id: UUID,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(CourseRegistration.id).where(
        CourseRegistration.student_id == student_id,
        CourseRegistration.course_offering_id == course_offering_id,
        CourseRegistration.status == "active",
    )
    if exclude_id is not None:
        statement = statement.where(CourseRegistration.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateCourseRegistrationError()


def _ensure_capacity_available(
    session: Session,
    *,
    offering: CourseOffering,
) -> None:
    if offering.capacity is None:
        return
    count = session.scalar(
        select(func.count(CourseRegistration.id)).where(
            CourseRegistration.course_offering_id == offering.id,
            CourseRegistration.registration_status
            == RegistrationStatus.REGISTERED.value,
            CourseRegistration.status == "active",
        )
    )
    if (count or 0) >= offering.capacity:
        raise CourseOfferingCapacityError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateCourseRegistrationError() from error
