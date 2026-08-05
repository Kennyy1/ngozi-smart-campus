from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.assessment_component import AssessmentComponent
from app.models.course_offering import CourseOffering
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.schemas.assessment_component import (
    AssessmentComponentCreate,
    AssessmentComponentStatus,
    AssessmentComponentUpdate,
    AssessmentType,
)


ACTIVE_WEIGHT_STATUSES = (
    AssessmentComponentStatus.DRAFT.value,
    AssessmentComponentStatus.PUBLISHED.value,
    AssessmentComponentStatus.CLOSED.value,
)


class AssessmentComponentNotFoundError(Exception): pass
class AssessmentCourseOfferingNotFoundError(Exception): pass
class AssessmentLecturerAssignmentNotFoundError(Exception): pass
class AssessmentCourseOfferingUnavailableError(Exception): pass
class AssessmentLecturerAssignmentUnavailableError(Exception): pass
class AssessmentLecturerUnavailableError(Exception): pass
class AssessmentHierarchyMismatchError(Exception): pass
class AssessmentDateRangeError(Exception): pass
class DuplicateAssessmentComponentError(Exception): pass
class AssessmentWeightConflictError(Exception): pass
class AssessmentComponentConflictError(Exception): pass


def create_assessment_component(
    session: Session,
    *,
    institution_id: UUID,
    assessment_component_data: AssessmentComponentCreate,
) -> AssessmentComponent:
    offering = _resolve_course_offering(session, course_offering_id=assessment_component_data.course_offering_id, institution_id=institution_id)
    assignment = _resolve_lecturer_assignment(session, lecturer_assignment_id=assessment_component_data.lecturer_assignment_id, institution_id=institution_id)
    _validate_parents(offering, assignment)
    _validate_dates(offering, assessment_component_data.scheduled_date, assessment_component_data.due_at)
    _ensure_title_available(session, course_offering_id=offering.id, title=assessment_component_data.title)
    _validate_active_weight(session, course_offering_id=offering.id, status=assessment_component_data.status, weight=assessment_component_data.weight_percentage)
    component = AssessmentComponent(
        institution_id=institution_id,
        **assessment_component_data.model_dump(mode="python"),
    )
    session.add(component)
    _commit(session)
    session.refresh(component)
    return component


def list_assessment_components(
    session: Session,
    *,
    institution_id: UUID,
    course_offering_id: UUID | None = None,
    lecturer_assignment_id: UUID | None = None,
    assessment_type: AssessmentType | None = None,
    status: AssessmentComponentStatus | None = None,
    scheduled_date: date | None = None,
) -> list[AssessmentComponent]:
    statement = select(AssessmentComponent).where(AssessmentComponent.institution_id == institution_id)
    if status is None:
        statement = statement.where(AssessmentComponent.status != AssessmentComponentStatus.INACTIVE.value)
    else:
        statement = statement.where(AssessmentComponent.status == status.value)
    if course_offering_id is not None:
        statement = statement.where(AssessmentComponent.course_offering_id == course_offering_id)
    if lecturer_assignment_id is not None:
        statement = statement.where(AssessmentComponent.lecturer_assignment_id == lecturer_assignment_id)
    if assessment_type is not None:
        statement = statement.where(AssessmentComponent.assessment_type == assessment_type.value)
    if scheduled_date is not None:
        statement = statement.where(AssessmentComponent.scheduled_date == scheduled_date)
    return list(session.scalars(statement.order_by(AssessmentComponent.scheduled_date, AssessmentComponent.created_at, AssessmentComponent.id)).all())


def get_assessment_component(session: Session, *, assessment_component_id: UUID, institution_id: UUID) -> AssessmentComponent:
    component = session.scalar(select(AssessmentComponent).where(
        AssessmentComponent.id == assessment_component_id,
        AssessmentComponent.institution_id == institution_id,
        AssessmentComponent.status != AssessmentComponentStatus.INACTIVE.value,
    ))
    if component is None:
        raise AssessmentComponentNotFoundError()
    return component


def update_assessment_component(
    session: Session,
    *,
    assessment_component_id: UUID,
    institution_id: UUID,
    assessment_component_data: AssessmentComponentUpdate,
) -> AssessmentComponent:
    component = get_assessment_component(session, assessment_component_id=assessment_component_id, institution_id=institution_id)
    changes = assessment_component_data.model_dump(exclude_unset=True, mode="python")
    offering_id = changes.get("course_offering_id", component.course_offering_id)
    assignment_id = changes.get("lecturer_assignment_id", component.lecturer_assignment_id)
    offering = _resolve_course_offering(session, course_offering_id=offering_id, institution_id=institution_id)
    assignment = _resolve_lecturer_assignment(session, lecturer_assignment_id=assignment_id, institution_id=institution_id)
    _validate_parents(offering, assignment)
    title = changes.get("title", component.title)
    scheduled_date = changes.get("scheduled_date", component.scheduled_date)
    due_at = changes.get("due_at", component.due_at)
    final_status = changes.get("status", AssessmentComponentStatus(component.status))
    weight = changes.get("weight_percentage", component.weight_percentage)
    _validate_dates(offering, scheduled_date, due_at)
    _ensure_title_available(session, course_offering_id=offering.id, title=title, exclude_id=component.id)
    _validate_active_weight(session, course_offering_id=offering.id, status=final_status, weight=weight, exclude_id=component.id)
    for field, value in changes.items():
        setattr(component, field, value.value if isinstance(value, (AssessmentType, AssessmentComponentStatus)) else value)
    _commit(session)
    session.refresh(component)
    return component


def delete_assessment_component(session: Session, *, assessment_component_id: UUID, institution_id: UUID) -> None:
    component = get_assessment_component(session, assessment_component_id=assessment_component_id, institution_id=institution_id)
    component.status = AssessmentComponentStatus.INACTIVE.value
    _commit(session)


def _resolve_course_offering(session: Session, *, course_offering_id: UUID, institution_id: UUID) -> CourseOffering:
    offering = session.scalar(select(CourseOffering).options(
        joinedload(CourseOffering.semester), joinedload(CourseOffering.academic_session)
    ).where(CourseOffering.id == course_offering_id, CourseOffering.institution_id == institution_id))
    if offering is None:
        raise AssessmentCourseOfferingNotFoundError()
    return offering


def _resolve_lecturer_assignment(session: Session, *, lecturer_assignment_id: UUID, institution_id: UUID) -> LecturerAssignment:
    assignment = session.scalar(select(LecturerAssignment).options(
        joinedload(LecturerAssignment.lecturer).joinedload(Lecturer.user)
    ).where(LecturerAssignment.id == lecturer_assignment_id, LecturerAssignment.institution_id == institution_id))
    if assignment is None:
        raise AssessmentLecturerAssignmentNotFoundError()
    return assignment


def _validate_parents(offering: CourseOffering, assignment: LecturerAssignment) -> None:
    if assignment.course_offering_id != offering.id:
        raise AssessmentHierarchyMismatchError()
    if offering.status != "active":
        raise AssessmentCourseOfferingUnavailableError()
    if assignment.status != "active":
        raise AssessmentLecturerAssignmentUnavailableError()
    if assignment.lecturer.employment_status != "active" or not assignment.lecturer.user.is_active:
        raise AssessmentLecturerUnavailableError()


def _validate_dates(offering: CourseOffering, scheduled_date: date | None, due_at: datetime | None) -> None:
    semester = offering.semester
    academic_session = offering.academic_session
    if scheduled_date is not None and not semester.start_date <= scheduled_date <= semester.end_date:
        raise AssessmentDateRangeError()
    if due_at is not None:
        due_date = due_at.date()
        if not semester.start_date <= due_date <= semester.end_date:
            raise AssessmentDateRangeError()
        if not academic_session.start_date <= due_date <= academic_session.end_date:
            raise AssessmentDateRangeError()
    if scheduled_date is not None and due_at is not None and scheduled_date > due_at.date():
        raise AssessmentDateRangeError()


def _ensure_title_available(session: Session, *, course_offering_id: UUID, title: str, exclude_id: UUID | None = None) -> None:
    normalized = " ".join(title.split()).casefold()
    statement = select(AssessmentComponent.id).where(
        AssessmentComponent.course_offering_id == course_offering_id,
        AssessmentComponent.status != AssessmentComponentStatus.INACTIVE.value,
        func.lower(AssessmentComponent.title) == normalized,
    )
    if exclude_id is not None:
        statement = statement.where(AssessmentComponent.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateAssessmentComponentError()


def _validate_active_weight(
    session: Session,
    *,
    course_offering_id: UUID,
    status: AssessmentComponentStatus,
    weight: Decimal,
    exclude_id: UUID | None = None,
) -> None:
    if status.value not in ACTIVE_WEIGHT_STATUSES:
        return
    statement = select(func.coalesce(func.sum(AssessmentComponent.weight_percentage), 0)).where(
        AssessmentComponent.course_offering_id == course_offering_id,
        AssessmentComponent.status.in_(ACTIVE_WEIGHT_STATUSES),
    )
    if exclude_id is not None:
        statement = statement.where(AssessmentComponent.id != exclude_id)
    current = Decimal(session.scalar(statement) or 0)
    if current + weight > Decimal("100"):
        raise AssessmentWeightConflictError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise AssessmentComponentConflictError() from error
