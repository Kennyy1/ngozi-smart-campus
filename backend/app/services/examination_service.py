from datetime import date, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.course_offering import CourseOffering
from app.models.examination import Examination
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.schemas.examination import DeliveryMode, ExaminationCreate, ExaminationStatus, ExaminationType, ExaminationUpdate


ACTIVE_WEIGHT_STATUSES = (ExaminationStatus.DRAFT.value, ExaminationStatus.SCHEDULED.value, ExaminationStatus.COMPLETED.value)


class ExaminationNotFoundError(Exception): pass
class ExaminationCourseOfferingNotFoundError(Exception): pass
class ExaminationLecturerAssignmentNotFoundError(Exception): pass
class ExaminationCourseOfferingUnavailableError(Exception): pass
class ExaminationLecturerAssignmentUnavailableError(Exception): pass
class ExaminationLecturerUnavailableError(Exception): pass
class ExaminationHierarchyMismatchError(Exception): pass
class ExaminationDateRangeError(Exception): pass
class ExaminationTimeRangeError(Exception): pass
class ExaminationVenueRequiredError(Exception): pass
class DuplicateExaminationError(Exception): pass
class ExaminationWeightConflictError(Exception): pass
class ExaminationConflictError(Exception): pass


def create_examination(session: Session, *, institution_id: UUID, examination_data: ExaminationCreate) -> Examination:
    offering = _resolve_course_offering(session, course_offering_id=examination_data.course_offering_id, institution_id=institution_id)
    assignment = _resolve_lecturer_assignment(session, lecturer_assignment_id=examination_data.lecturer_assignment_id, institution_id=institution_id)
    _validate_parents(offering, assignment)
    _validate_schedule(offering, examination_data.exam_date, examination_data.start_time, examination_data.end_time, examination_data.delivery_mode, examination_data.venue)
    _ensure_title_available(session, course_offering_id=offering.id, title=examination_data.title)
    _validate_active_weight(session, course_offering_id=offering.id, status=examination_data.status, weight=examination_data.weight_percentage)
    examination = Examination(institution_id=institution_id, **examination_data.model_dump(mode="python"))
    session.add(examination)
    _commit(session)
    session.refresh(examination)
    return examination


def list_examinations(session: Session, *, institution_id: UUID, course_offering_id: UUID | None = None, lecturer_assignment_id: UUID | None = None, examination_type: ExaminationType | None = None, exam_date: date | None = None, delivery_mode: DeliveryMode | None = None, status: ExaminationStatus | None = None) -> list[Examination]:
    statement = select(Examination).where(Examination.institution_id == institution_id)
    statement = statement.where(Examination.status != ExaminationStatus.INACTIVE.value) if status is None else statement.where(Examination.status == status.value)
    if course_offering_id is not None: statement = statement.where(Examination.course_offering_id == course_offering_id)
    if lecturer_assignment_id is not None: statement = statement.where(Examination.lecturer_assignment_id == lecturer_assignment_id)
    if examination_type is not None: statement = statement.where(Examination.examination_type == examination_type.value)
    if exam_date is not None: statement = statement.where(Examination.exam_date == exam_date)
    if delivery_mode is not None: statement = statement.where(Examination.delivery_mode == delivery_mode.value)
    return list(session.scalars(statement.order_by(Examination.exam_date, Examination.start_time, Examination.created_at, Examination.id)).all())


def get_examination(session: Session, *, examination_id: UUID, institution_id: UUID) -> Examination:
    examination = session.scalar(select(Examination).where(Examination.id == examination_id, Examination.institution_id == institution_id, Examination.status != ExaminationStatus.INACTIVE.value))
    if examination is None: raise ExaminationNotFoundError()
    return examination


def update_examination(session: Session, *, examination_id: UUID, institution_id: UUID, examination_data: ExaminationUpdate) -> Examination:
    examination = get_examination(session, examination_id=examination_id, institution_id=institution_id)
    changes = examination_data.model_dump(exclude_unset=True, mode="python")
    offering = _resolve_course_offering(session, course_offering_id=changes.get("course_offering_id", examination.course_offering_id), institution_id=institution_id)
    assignment = _resolve_lecturer_assignment(session, lecturer_assignment_id=changes.get("lecturer_assignment_id", examination.lecturer_assignment_id), institution_id=institution_id)
    _validate_parents(offering, assignment)
    title = changes.get("title", examination.title)
    final_status = changes.get("status", ExaminationStatus(examination.status))
    weight = changes.get("weight_percentage", examination.weight_percentage)
    _validate_schedule(offering, changes.get("exam_date", examination.exam_date), changes.get("start_time", examination.start_time), changes.get("end_time", examination.end_time), changes.get("delivery_mode", DeliveryMode(examination.delivery_mode)), changes.get("venue", examination.venue))
    _ensure_title_available(session, course_offering_id=offering.id, title=title, exclude_id=examination.id)
    _validate_active_weight(session, course_offering_id=offering.id, status=final_status, weight=weight, exclude_id=examination.id)
    for field, value in changes.items():
        setattr(examination, field, value.value if isinstance(value, (ExaminationType, DeliveryMode, ExaminationStatus)) else value)
    _commit(session)
    session.refresh(examination)
    return examination


def delete_examination(session: Session, *, examination_id: UUID, institution_id: UUID) -> None:
    examination = get_examination(session, examination_id=examination_id, institution_id=institution_id)
    examination.status = ExaminationStatus.INACTIVE.value
    _commit(session)


def _resolve_course_offering(session: Session, *, course_offering_id: UUID, institution_id: UUID) -> CourseOffering:
    offering = session.scalar(select(CourseOffering).options(joinedload(CourseOffering.semester), joinedload(CourseOffering.academic_session)).where(CourseOffering.id == course_offering_id, CourseOffering.institution_id == institution_id))
    if offering is None: raise ExaminationCourseOfferingNotFoundError()
    return offering


def _resolve_lecturer_assignment(session: Session, *, lecturer_assignment_id: UUID, institution_id: UUID) -> LecturerAssignment:
    assignment = session.scalar(select(LecturerAssignment).options(joinedload(LecturerAssignment.lecturer).joinedload(Lecturer.user)).where(LecturerAssignment.id == lecturer_assignment_id, LecturerAssignment.institution_id == institution_id))
    if assignment is None: raise ExaminationLecturerAssignmentNotFoundError()
    return assignment


def _validate_parents(offering: CourseOffering, assignment: LecturerAssignment) -> None:
    if assignment.course_offering_id != offering.id: raise ExaminationHierarchyMismatchError()
    if offering.status != "active": raise ExaminationCourseOfferingUnavailableError()
    if assignment.status != "active": raise ExaminationLecturerAssignmentUnavailableError()
    if assignment.lecturer.employment_status != "active" or not assignment.lecturer.user.is_active: raise ExaminationLecturerUnavailableError()


def _validate_schedule(offering: CourseOffering, exam_date: date, start_time: time, end_time: time, delivery_mode: DeliveryMode, venue: str | None) -> None:
    if not offering.semester.start_date <= exam_date <= offering.semester.end_date or not offering.academic_session.start_date <= exam_date <= offering.academic_session.end_date: raise ExaminationDateRangeError()
    if start_time >= end_time: raise ExaminationTimeRangeError()
    if delivery_mode in (DeliveryMode.PHYSICAL, DeliveryMode.HYBRID) and (venue is None or not venue.strip()): raise ExaminationVenueRequiredError()


def _ensure_title_available(session: Session, *, course_offering_id: UUID, title: str, exclude_id: UUID | None = None) -> None:
    normalized = " ".join(title.split()).casefold()
    statement = select(Examination.id).where(Examination.course_offering_id == course_offering_id, Examination.status != ExaminationStatus.INACTIVE.value, func.lower(Examination.title) == normalized)
    if exclude_id is not None: statement = statement.where(Examination.id != exclude_id)
    if session.scalar(statement) is not None: raise DuplicateExaminationError()


def _validate_active_weight(session: Session, *, course_offering_id: UUID, status: ExaminationStatus, weight: Decimal, exclude_id: UUID | None = None) -> None:
    if status.value not in ACTIVE_WEIGHT_STATUSES: return
    statement = select(func.coalesce(func.sum(Examination.weight_percentage), 0)).where(Examination.course_offering_id == course_offering_id, Examination.status.in_(ACTIVE_WEIGHT_STATUSES))
    if exclude_id is not None: statement = statement.where(Examination.id != exclude_id)
    if Decimal(session.scalar(statement) or 0) + weight > Decimal("100"): raise ExaminationWeightConflictError()


def _commit(session: Session) -> None:
    try: session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ExaminationConflictError() from error
