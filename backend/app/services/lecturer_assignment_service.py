from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.course_offering import CourseOffering
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.user import User
from app.schemas.lecturer_assignment import AssignmentRole, AssignmentStatus, LecturerAssignmentCreate, LecturerAssignmentUpdate, _validate_state


class LecturerAssignmentNotFoundError(Exception): pass
class AssignmentLecturerNotFoundError(Exception): pass
class AssignmentCourseOfferingNotFoundError(Exception): pass
class LecturerUnavailableError(Exception): pass
class CourseOfferingUnavailableError(Exception): pass
class DuplicateLecturerAssignmentError(Exception): pass
class DuplicatePrimaryLecturerError(Exception): pass
class InvalidLecturerAssignmentError(Exception): pass
class LecturerAssignmentConflictError(Exception): pass


def create_lecturer_assignment(session: Session, *, institution_id: UUID, lecturer_assignment_data: LecturerAssignmentCreate) -> LecturerAssignment:
    lecturer = _resolve_lecturer(session, lecturer_id=lecturer_assignment_data.lecturer_id, institution_id=institution_id)
    offering = _resolve_course_offering(session, course_offering_id=lecturer_assignment_data.course_offering_id, institution_id=institution_id)
    _validate_lecturer_availability(lecturer); _validate_course_offering_availability(offering)
    _validate_assignment_state(role=lecturer_assignment_data.assignment_role, is_primary=lecturer_assignment_data.is_primary, assigned_at=lecturer_assignment_data.assigned_at, ended_at=lecturer_assignment_data.ended_at)
    if lecturer_assignment_data.status == AssignmentStatus.ACTIVE:
        _ensure_assignment_available(session, lecturer_id=lecturer.id, course_offering_id=offering.id)
        if lecturer_assignment_data.is_primary: _ensure_primary_available(session, course_offering_id=offering.id)
    assignment = LecturerAssignment(institution_id=institution_id, **lecturer_assignment_data.model_dump(mode="python"))
    session.add(assignment); _commit(session); session.refresh(assignment); return assignment


def list_lecturer_assignments(session: Session, *, institution_id: UUID, lecturer_id: UUID | None = None, course_offering_id: UUID | None = None, assignment_role: AssignmentRole | None = None, is_primary: bool | None = None, status: AssignmentStatus | None = None) -> list[LecturerAssignment]:
    statement = select(LecturerAssignment).where(LecturerAssignment.institution_id == institution_id, LecturerAssignment.status == AssignmentStatus.ACTIVE.value)
    if lecturer_id is not None: statement = statement.where(LecturerAssignment.lecturer_id == lecturer_id)
    if course_offering_id is not None: statement = statement.where(LecturerAssignment.course_offering_id == course_offering_id)
    if assignment_role is not None: statement = statement.where(LecturerAssignment.assignment_role == assignment_role.value)
    if is_primary is not None: statement = statement.where(LecturerAssignment.is_primary == is_primary)
    if status is not None: statement = statement.where(LecturerAssignment.status == status.value)
    return list(session.scalars(statement.order_by(LecturerAssignment.assigned_at.desc(), LecturerAssignment.id)).all())


def get_lecturer_assignment(session: Session, *, lecturer_assignment_id: UUID, institution_id: UUID) -> LecturerAssignment:
    assignment = session.scalar(select(LecturerAssignment).where(LecturerAssignment.id == lecturer_assignment_id, LecturerAssignment.institution_id == institution_id, LecturerAssignment.status == AssignmentStatus.ACTIVE.value))
    if assignment is None: raise LecturerAssignmentNotFoundError()
    return assignment


def update_lecturer_assignment(session: Session, *, lecturer_assignment_id: UUID, institution_id: UUID, lecturer_assignment_data: LecturerAssignmentUpdate) -> LecturerAssignment:
    assignment = get_lecturer_assignment(session, lecturer_assignment_id=lecturer_assignment_id, institution_id=institution_id)
    changes = lecturer_assignment_data.model_dump(exclude_unset=True)
    lecturer_id = changes.get("lecturer_id", assignment.lecturer_id); offering_id = changes.get("course_offering_id", assignment.course_offering_id)
    lecturer = _resolve_lecturer(session, lecturer_id=lecturer_id, institution_id=institution_id); offering = _resolve_course_offering(session, course_offering_id=offering_id, institution_id=institution_id)
    _validate_lecturer_availability(lecturer); _validate_course_offering_availability(offering)
    role = changes.get("assignment_role", AssignmentRole(assignment.assignment_role)); is_primary = changes.get("is_primary", assignment.is_primary)
    assigned_at = changes.get("assigned_at", assignment.assigned_at); ended_at = changes.get("ended_at", assignment.ended_at)
    _validate_assignment_state(role=role, is_primary=is_primary, assigned_at=assigned_at, ended_at=ended_at)
    final_status = changes.get("status", AssignmentStatus(assignment.status))
    if final_status == AssignmentStatus.ACTIVE:
        _ensure_assignment_available(session, lecturer_id=lecturer_id, course_offering_id=offering_id, exclude_id=assignment.id)
        if is_primary: _ensure_primary_available(session, course_offering_id=offering_id, exclude_id=assignment.id)
    for field, value in changes.items(): setattr(assignment, field, value.value if isinstance(value, (AssignmentRole, AssignmentStatus)) else value)
    _commit(session); session.refresh(assignment); return assignment


def delete_lecturer_assignment(session: Session, *, lecturer_assignment_id: UUID, institution_id: UUID) -> None:
    assignment = get_lecturer_assignment(session, lecturer_assignment_id=lecturer_assignment_id, institution_id=institution_id)
    assignment.status = AssignmentStatus.INACTIVE.value; _commit(session)


def _resolve_lecturer(session: Session, *, lecturer_id: UUID, institution_id: UUID) -> Lecturer:
    lecturer = session.scalar(select(Lecturer).options(joinedload(Lecturer.user)).where(Lecturer.id == lecturer_id, Lecturer.institution_id == institution_id))
    if lecturer is None: raise AssignmentLecturerNotFoundError()
    return lecturer


def _resolve_course_offering(session: Session, *, course_offering_id: UUID, institution_id: UUID) -> CourseOffering:
    offering = session.scalar(select(CourseOffering).where(CourseOffering.id == course_offering_id, CourseOffering.institution_id == institution_id))
    if offering is None: raise AssignmentCourseOfferingNotFoundError()
    return offering


def _validate_lecturer_availability(lecturer: Lecturer) -> None:
    if lecturer.employment_status != "active" or not lecturer.user.is_active: raise LecturerUnavailableError()


def _validate_course_offering_availability(offering: CourseOffering) -> None:
    if offering.status != "active": raise CourseOfferingUnavailableError()


def _validate_assignment_state(*, role: AssignmentRole, is_primary: bool, assigned_at: datetime, ended_at: datetime | None) -> None:
    try: _validate_state(role, is_primary, assigned_at, ended_at)
    except ValueError as error: raise InvalidLecturerAssignmentError() from error


def _ensure_assignment_available(session: Session, *, lecturer_id: UUID, course_offering_id: UUID, exclude_id: UUID | None = None) -> None:
    statement = select(LecturerAssignment.id).where(LecturerAssignment.lecturer_id == lecturer_id, LecturerAssignment.course_offering_id == course_offering_id, LecturerAssignment.status == "active")
    if exclude_id is not None: statement = statement.where(LecturerAssignment.id != exclude_id)
    if session.scalar(statement) is not None: raise DuplicateLecturerAssignmentError()


def _ensure_primary_available(session: Session, *, course_offering_id: UUID, exclude_id: UUID | None = None) -> None:
    statement = select(LecturerAssignment.id).where(LecturerAssignment.course_offering_id == course_offering_id, LecturerAssignment.is_primary.is_(True), LecturerAssignment.status == "active")
    if exclude_id is not None: statement = statement.where(LecturerAssignment.id != exclude_id)
    if session.scalar(statement) is not None: raise DuplicatePrimaryLecturerError()


def _commit(session: Session) -> None:
    try: session.commit()
    except IntegrityError as error: session.rollback(); raise LecturerAssignmentConflictError() from error
