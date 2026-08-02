from datetime import date, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.class_session import ClassSession
from app.models.course_offering import CourseOffering
from app.models.lecturer_assignment import LecturerAssignment
from app.models.lecturer import Lecturer
from app.schemas.class_session import ClassSessionCreate, ClassSessionStatus, ClassSessionUpdate, DeliveryMode, SessionType, validate_session_state

BLOCKING_STATUSES = (ClassSessionStatus.SCHEDULED.value, ClassSessionStatus.COMPLETED.value)

class ClassSessionNotFoundError(Exception): pass
class ClassSessionOfferingNotFoundError(Exception): pass
class ClassSessionAssignmentNotFoundError(Exception): pass
class ClassSessionHierarchyError(Exception): pass
class ClassSessionParentUnavailableError(Exception): pass
class InvalidClassSessionError(Exception): pass
class DuplicateClassSessionError(Exception): pass
class OverlappingClassSessionError(Exception): pass
class ClassSessionConflictError(Exception): pass


def create_class_session(session: Session, *, institution_id: UUID, class_session_data: ClassSessionCreate) -> ClassSession:
    offering = _resolve_offering(session, course_offering_id=class_session_data.course_offering_id, institution_id=institution_id)
    assignment = _resolve_assignment(session, lecturer_assignment_id=class_session_data.lecturer_assignment_id, institution_id=institution_id)
    _validate_parents(offering, assignment); _validate_details(offering, class_session_data.session_date, class_session_data.start_time, class_session_data.end_time, class_session_data.delivery_mode, class_session_data.venue)
    if class_session_data.status.value in BLOCKING_STATUSES: _check_conflicts(session, offering.id, assignment.id, class_session_data.session_date, class_session_data.start_time, class_session_data.end_time)
    item = ClassSession(institution_id=institution_id, **class_session_data.model_dump(mode="python")); session.add(item); _commit(session); session.refresh(item); return item


def list_class_sessions(session: Session, *, institution_id: UUID, course_offering_id: UUID | None = None, lecturer_assignment_id: UUID | None = None, session_date: date | None = None, session_type: SessionType | None = None, delivery_mode: DeliveryMode | None = None, status: ClassSessionStatus | None = None) -> list[ClassSession]:
    statement = select(ClassSession).where(ClassSession.institution_id == institution_id, ClassSession.status != ClassSessionStatus.INACTIVE.value)
    for column, value in ((ClassSession.course_offering_id, course_offering_id), (ClassSession.lecturer_assignment_id, lecturer_assignment_id), (ClassSession.session_date, session_date)):
        if value is not None: statement = statement.where(column == value)
    if session_type is not None: statement = statement.where(ClassSession.session_type == session_type.value)
    if delivery_mode is not None: statement = statement.where(ClassSession.delivery_mode == delivery_mode.value)
    if status is not None: statement = statement.where(ClassSession.status == status.value)
    return list(session.scalars(statement.order_by(ClassSession.session_date, ClassSession.start_time, ClassSession.id)).all())


def get_class_session(session: Session, *, class_session_id: UUID, institution_id: UUID) -> ClassSession:
    item = session.scalar(select(ClassSession).where(ClassSession.id == class_session_id, ClassSession.institution_id == institution_id, ClassSession.status != ClassSessionStatus.INACTIVE.value))
    if item is None: raise ClassSessionNotFoundError()
    return item


def update_class_session(session: Session, *, class_session_id: UUID, institution_id: UUID, class_session_data: ClassSessionUpdate) -> ClassSession:
    item = get_class_session(session, class_session_id=class_session_id, institution_id=institution_id); changes = class_session_data.model_dump(exclude_unset=True)
    offering_id = changes.get("course_offering_id", item.course_offering_id); assignment_id = changes.get("lecturer_assignment_id", item.lecturer_assignment_id)
    offering = _resolve_offering(session, course_offering_id=offering_id, institution_id=institution_id); assignment = _resolve_assignment(session, lecturer_assignment_id=assignment_id, institution_id=institution_id); _validate_parents(offering, assignment)
    session_date = changes.get("session_date", item.session_date); start_time = changes.get("start_time", item.start_time); end_time = changes.get("end_time", item.end_time); mode = changes.get("delivery_mode", DeliveryMode(item.delivery_mode)); venue = changes.get("venue", item.venue)
    _validate_details(offering, session_date, start_time, end_time, mode, venue)
    final_status = changes.get("status", ClassSessionStatus(item.status))
    if final_status.value in BLOCKING_STATUSES: _check_conflicts(session, offering_id, assignment_id, session_date, start_time, end_time, exclude_id=item.id)
    for field, value in changes.items(): setattr(item, field, value.value if isinstance(value, (SessionType, DeliveryMode, ClassSessionStatus)) else value)
    _commit(session); session.refresh(item); return item


def delete_class_session(session: Session, *, class_session_id: UUID, institution_id: UUID) -> None:
    item = get_class_session(session, class_session_id=class_session_id, institution_id=institution_id); item.status = ClassSessionStatus.INACTIVE.value; _commit(session)


def _resolve_offering(session: Session, *, course_offering_id: UUID, institution_id: UUID) -> CourseOffering:
    item = session.scalar(select(CourseOffering).options(joinedload(CourseOffering.semester), joinedload(CourseOffering.academic_session)).where(CourseOffering.id == course_offering_id, CourseOffering.institution_id == institution_id))
    if item is None: raise ClassSessionOfferingNotFoundError()
    return item


def _resolve_assignment(session: Session, *, lecturer_assignment_id: UUID, institution_id: UUID) -> LecturerAssignment:
    item = session.scalar(select(LecturerAssignment).options(joinedload(LecturerAssignment.lecturer).joinedload(Lecturer.user)).where(LecturerAssignment.id == lecturer_assignment_id, LecturerAssignment.institution_id == institution_id))
    if item is None: raise ClassSessionAssignmentNotFoundError()
    return item


def _validate_parents(offering: CourseOffering, assignment: LecturerAssignment) -> None:
    if assignment.course_offering_id != offering.id: raise ClassSessionHierarchyError()
    if offering.status != "active" or assignment.status != "active" or assignment.lecturer.employment_status != "active" or not assignment.lecturer.user.is_active: raise ClassSessionParentUnavailableError()


def _validate_details(offering: CourseOffering, session_date: date, start_time: time, end_time: time, mode: DeliveryMode, venue: str | None) -> None:
    try: validate_session_state(start_time, end_time, mode, venue)
    except ValueError as error: raise InvalidClassSessionError() from error
    if not (offering.semester.start_date <= session_date <= offering.semester.end_date and offering.academic_session.start_date <= session_date <= offering.academic_session.end_date): raise InvalidClassSessionError()


def _check_conflicts(session: Session, offering_id: UUID, assignment_id: UUID, session_date: date, start_time: time, end_time: time, exclude_id: UUID | None = None) -> None:
    exact = select(ClassSession.id).where(ClassSession.course_offering_id == offering_id, ClassSession.session_date == session_date, ClassSession.start_time == start_time, ClassSession.end_time == end_time, ClassSession.status.in_(BLOCKING_STATUSES))
    overlap = select(ClassSession.id).where(ClassSession.lecturer_assignment_id == assignment_id, ClassSession.session_date == session_date, ClassSession.start_time < end_time, ClassSession.end_time > start_time, ClassSession.status.in_(BLOCKING_STATUSES))
    if exclude_id is not None: exact = exact.where(ClassSession.id != exclude_id); overlap = overlap.where(ClassSession.id != exclude_id)
    if session.scalar(exact) is not None: raise DuplicateClassSessionError()
    if session.scalar(overlap) is not None: raise OverlappingClassSessionError()


def _commit(session: Session) -> None:
    try: session.commit()
    except IntegrityError as error: session.rollback(); raise ClassSessionConflictError() from error
