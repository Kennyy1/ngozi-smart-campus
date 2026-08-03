from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.course_registration import CourseRegistration
from app.schemas.attendance_record import (
    AttendanceBulkCreate,
    AttendanceRecordCreate,
    AttendanceRecordStatus,
    AttendanceRecordUpdate,
    AttendanceStatus,
    validate_attendance_state,
)


class AttendanceRecordNotFoundError(Exception): pass
class AttendanceClassSessionNotFoundError(Exception): pass
class AttendanceCourseRegistrationNotFoundError(Exception): pass
class AttendanceSessionUnavailableError(Exception): pass
class AttendanceRegistrationUnavailableError(Exception): pass
class AttendanceOfferingMismatchError(Exception): pass
class InvalidAttendanceStateError(Exception): pass
class DuplicateAttendanceRecordError(Exception): pass
class AttendanceRecorderUnauthorizedError(Exception): pass


def create_attendance_record(
    session: Session,
    *,
    institution_id: UUID,
    recorded_by_user_id: UUID,
    attendance_data: AttendanceRecordCreate,
) -> AttendanceRecord:
    class_session = _resolve_class_session(session, class_session_id=attendance_data.class_session_id, institution_id=institution_id)
    _validate_session_eligibility(class_session)
    registration = _resolve_course_registration(session, course_registration_id=attendance_data.course_registration_id, institution_id=institution_id)
    _validate_registration_eligibility(registration)
    _validate_offering_match(class_session, registration)
    _validate_recorder_authorization(recorded_by_user_id)
    _validate_attendance(attendance_data.attendance_status, attendance_data.check_in_time)
    _ensure_attendance_available(session, class_session_id=class_session.id, course_registration_id=registration.id)
    record = AttendanceRecord(
        institution_id=institution_id,
        class_session_id=class_session.id,
        course_registration_id=registration.id,
        attendance_status=attendance_data.attendance_status.value,
        check_in_time=attendance_data.check_in_time,
        recorded_by_user_id=recorded_by_user_id,
        remarks=attendance_data.remarks,
        status=AttendanceRecordStatus.ACTIVE.value,
    )
    session.add(record)
    _commit(session)
    session.refresh(record)
    return record


def create_attendance_records_bulk(
    session: Session,
    *,
    institution_id: UUID,
    recorded_by_user_id: UUID,
    attendance_data: AttendanceBulkCreate,
) -> list[AttendanceRecord]:
    class_session = _resolve_class_session(session, class_session_id=attendance_data.class_session_id, institution_id=institution_id)
    _validate_session_eligibility(class_session)
    _validate_recorder_authorization(recorded_by_user_id)
    registration_ids = [item.course_registration_id for item in attendance_data.records]
    if len(registration_ids) != len(set(registration_ids)):
        raise InvalidAttendanceStateError()

    resolved: list[tuple[CourseRegistration, object]] = []
    for item in attendance_data.records:
        registration = _resolve_course_registration(session, course_registration_id=item.course_registration_id, institution_id=institution_id)
        _validate_registration_eligibility(registration)
        _validate_offering_match(class_session, registration)
        _validate_attendance(item.attendance_status, item.check_in_time)
        _ensure_attendance_available(session, class_session_id=class_session.id, course_registration_id=registration.id)
        resolved.append((registration, item))

    records = [
        AttendanceRecord(
            institution_id=institution_id,
            class_session_id=class_session.id,
            course_registration_id=registration.id,
            attendance_status=item.attendance_status.value,
            check_in_time=item.check_in_time,
            recorded_by_user_id=recorded_by_user_id,
            remarks=item.remarks,
            status=AttendanceRecordStatus.ACTIVE.value,
        )
        for registration, item in resolved
    ]
    session.add_all(records)
    _commit(session)
    for record in records:
        session.refresh(record)
    return records


def list_attendance_records(
    session: Session,
    *,
    institution_id: UUID,
    class_session_id: UUID | None = None,
    course_registration_id: UUID | None = None,
    attendance_status: AttendanceStatus | None = None,
    recorded_by_user_id: UUID | None = None,
    status: AttendanceRecordStatus | None = None,
) -> list[AttendanceRecord]:
    statement = select(AttendanceRecord).where(AttendanceRecord.institution_id == institution_id)
    if status is None:
        statement = statement.where(AttendanceRecord.status == AttendanceRecordStatus.ACTIVE.value)
    else:
        statement = statement.where(AttendanceRecord.status == status.value)
    for column, value in (
        (AttendanceRecord.class_session_id, class_session_id),
        (AttendanceRecord.course_registration_id, course_registration_id),
        (AttendanceRecord.recorded_by_user_id, recorded_by_user_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if attendance_status is not None:
        statement = statement.where(AttendanceRecord.attendance_status == attendance_status.value)
    return list(session.scalars(statement.order_by(AttendanceRecord.created_at.desc(), AttendanceRecord.id)).all())


def get_attendance_record(session: Session, *, attendance_record_id: UUID, institution_id: UUID) -> AttendanceRecord:
    record = session.scalar(select(AttendanceRecord).where(
        AttendanceRecord.id == attendance_record_id,
        AttendanceRecord.institution_id == institution_id,
        AttendanceRecord.status == AttendanceRecordStatus.ACTIVE.value,
    ))
    if record is None:
        raise AttendanceRecordNotFoundError()
    return record


def update_attendance_record(
    session: Session,
    *,
    attendance_record_id: UUID,
    institution_id: UUID,
    attendance_data: AttendanceRecordUpdate,
) -> AttendanceRecord:
    record = get_attendance_record(session, attendance_record_id=attendance_record_id, institution_id=institution_id)
    changes = attendance_data.model_dump(exclude_unset=True)
    final_status = changes.get("attendance_status", AttendanceStatus(record.attendance_status))
    final_check_in = changes.get("check_in_time", record.check_in_time)
    _validate_attendance(final_status, final_check_in)
    for field, value in changes.items():
        setattr(record, field, value.value if isinstance(value, AttendanceStatus) else value)
    _commit(session)
    session.refresh(record)
    return record


def delete_attendance_record(session: Session, *, attendance_record_id: UUID, institution_id: UUID) -> None:
    record = get_attendance_record(session, attendance_record_id=attendance_record_id, institution_id=institution_id)
    record.status = AttendanceRecordStatus.INACTIVE.value
    _commit(session)


def _resolve_class_session(session: Session, *, class_session_id: UUID, institution_id: UUID) -> ClassSession:
    item = session.scalar(select(ClassSession).where(ClassSession.id == class_session_id, ClassSession.institution_id == institution_id))
    if item is None:
        raise AttendanceClassSessionNotFoundError()
    return item


def _resolve_course_registration(session: Session, *, course_registration_id: UUID, institution_id: UUID) -> CourseRegistration:
    item = session.scalar(select(CourseRegistration).where(CourseRegistration.id == course_registration_id, CourseRegistration.institution_id == institution_id))
    if item is None:
        raise AttendanceCourseRegistrationNotFoundError()
    return item


def _validate_session_eligibility(class_session: ClassSession) -> None:
    # Scheduled sessions, including future sessions, and completed sessions are eligible.
    if class_session.status not in ("scheduled", "completed"):
        raise AttendanceSessionUnavailableError()


def _validate_registration_eligibility(registration: CourseRegistration) -> None:
    if registration.status != "active" or registration.registration_status != "registered":
        raise AttendanceRegistrationUnavailableError()


def _validate_offering_match(class_session: ClassSession, registration: CourseRegistration) -> None:
    if class_session.course_offering_id != registration.course_offering_id:
        raise AttendanceOfferingMismatchError()


def _validate_recorder_authorization(recorded_by_user_id: UUID) -> None:
    if recorded_by_user_id is None:
        raise AttendanceRecorderUnauthorizedError()


def _validate_attendance(attendance_status: AttendanceStatus, check_in_time: object) -> None:
    try:
        validate_attendance_state(attendance_status, check_in_time)  # type: ignore[arg-type]
    except ValueError as error:
        raise InvalidAttendanceStateError() from error


def _ensure_attendance_available(session: Session, *, class_session_id: UUID, course_registration_id: UUID) -> None:
    existing = session.scalar(select(AttendanceRecord.id).where(
        AttendanceRecord.class_session_id == class_session_id,
        AttendanceRecord.course_registration_id == course_registration_id,
        AttendanceRecord.status == AttendanceRecordStatus.ACTIVE.value,
    ))
    if existing is not None:
        raise DuplicateAttendanceRecordError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateAttendanceRecordError() from error
