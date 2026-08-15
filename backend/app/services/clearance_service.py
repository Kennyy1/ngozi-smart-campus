from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.clearance_requirement import ClearanceRequirement
from app.models.student import Student
from app.models.student_clearance import StudentClearance
from app.schemas.clearance import (
    ClearanceRequirementCreate, ClearanceRequirementStatus, ClearanceRequirementUpdate,
    GraduationClearanceEvaluation, StudentClearanceActionRequest, StudentClearanceCreate,
    StudentClearanceStatus, StudentClearanceSummary, StudentClearanceSummaryItem,
    StudentClearanceUpdate,
)
from app.services.attendance_analytics_service import _student_display_name
from app.services.graduation_eligibility_service import evaluate_student_graduation_eligibility


class ClearanceRequirementNotFoundError(Exception): pass
class StudentClearanceStudentNotFoundError(Exception): pass
class StudentClearanceNotFoundError(Exception): pass
class DuplicateClearanceRequirementCodeError(Exception): pass
class DuplicateStudentClearanceError(Exception): pass
class InvalidStudentClearanceTransitionError(Exception): pass
class StudentClearanceReasonRequiredError(Exception): pass


def create_clearance_requirement(session: Session, *, institution_id: UUID, requirement_data: ClearanceRequirementCreate) -> ClearanceRequirement:
    _ensure_requirement_code_available(session, institution_id=institution_id, code=requirement_data.code)
    item = ClearanceRequirement(institution_id=institution_id, **requirement_data.model_dump(mode="python"))
    session.add(item)
    _commit(session, DuplicateClearanceRequirementCodeError)
    session.refresh(item)
    return item


def list_clearance_requirements(session: Session, *, institution_id: UUID, status: ClearanceRequirementStatus | None = None, is_mandatory: bool | None = None, code: str | None = None) -> list[ClearanceRequirement]:
    statement = select(ClearanceRequirement).where(ClearanceRequirement.institution_id == institution_id)
    if status is None:
        statement = statement.where(ClearanceRequirement.status != ClearanceRequirementStatus.INACTIVE.value)
    else:
        statement = statement.where(ClearanceRequirement.status == status.value)
    if is_mandatory is not None:
        statement = statement.where(ClearanceRequirement.is_mandatory == is_mandatory)
    if code is not None:
        statement = statement.where(ClearanceRequirement.code == code.strip().upper())
    return list(session.scalars(statement.order_by(ClearanceRequirement.sequence_number, ClearanceRequirement.name, ClearanceRequirement.id)).all())


def get_clearance_requirement(session: Session, *, institution_id: UUID, requirement_id: UUID) -> ClearanceRequirement:
    return _resolve_requirement(session, institution_id=institution_id, requirement_id=requirement_id)


def update_clearance_requirement(session: Session, *, institution_id: UUID, requirement_id: UUID, requirement_data: ClearanceRequirementUpdate) -> ClearanceRequirement:
    item = _resolve_requirement(session, institution_id=institution_id, requirement_id=requirement_id)
    changes = requirement_data.model_dump(exclude_unset=True, mode="python")
    if "code" in changes and changes["code"] != item.code:
        _ensure_requirement_code_available(session, institution_id=institution_id, code=changes["code"], exclude_id=item.id)
    for field, value in changes.items():
        setattr(item, field, value)
    _commit(session, DuplicateClearanceRequirementCodeError)
    session.refresh(item)
    return item


def delete_clearance_requirement(session: Session, *, institution_id: UUID, requirement_id: UUID) -> ClearanceRequirement:
    item = _resolve_requirement(session, institution_id=institution_id, requirement_id=requirement_id)
    item.status = ClearanceRequirementStatus.INACTIVE.value
    session.commit()
    session.refresh(item)
    return item


def create_student_clearance(session: Session, *, institution_id: UUID, clearance_data: StudentClearanceCreate) -> StudentClearance:
    student = _resolve_student(session, institution_id=institution_id, student_id=clearance_data.student_id)
    requirement = _resolve_requirement(session, institution_id=institution_id, requirement_id=clearance_data.clearance_requirement_id)
    _ensure_no_active_student_clearance(session, student_id=student.id, requirement_id=requirement.id)
    item = StudentClearance(
        institution_id=institution_id, student_id=student.id,
        clearance_requirement_id=requirement.id, status=StudentClearanceStatus.PENDING.value,
        remarks=clearance_data.remarks, evidence_reference=clearance_data.evidence_reference,
    )
    session.add(item)
    _commit(session, DuplicateStudentClearanceError)
    session.refresh(item)
    return item


def list_student_clearances(session: Session, *, institution_id: UUID, student_id: UUID | None = None, clearance_requirement_id: UUID | None = None, status: StudentClearanceStatus | None = None, reviewed_by_user_id: UUID | None = None) -> list[StudentClearance]:
    statement = select(StudentClearance).where(StudentClearance.institution_id == institution_id)
    if status is None:
        statement = statement.where(StudentClearance.status != StudentClearanceStatus.INACTIVE.value)
    else:
        statement = statement.where(StudentClearance.status == status.value)
    for column, value in (
        (StudentClearance.student_id, student_id),
        (StudentClearance.clearance_requirement_id, clearance_requirement_id),
        (StudentClearance.reviewed_by_user_id, reviewed_by_user_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    return list(session.scalars(statement.order_by(StudentClearance.created_at.desc(), StudentClearance.id)).all())


def get_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID) -> StudentClearance:
    return _resolve_student_clearance(session, institution_id=institution_id, student_clearance_id=student_clearance_id)


def update_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID, clearance_data: StudentClearanceUpdate) -> StudentClearance:
    item = _resolve_student_clearance(session, institution_id=institution_id, student_clearance_id=student_clearance_id)
    for field, value in clearance_data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return item


def clear_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID, user_id: UUID) -> StudentClearance:
    return _review_clearance(
        session, institution_id=institution_id, student_clearance_id=student_clearance_id,
        user_id=user_id, target=StudentClearanceStatus.CLEARED,
        allowed={StudentClearanceStatus.PENDING, StudentClearanceStatus.REJECTED},
    )


def reject_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID, user_id: UUID, request: StudentClearanceActionRequest) -> StudentClearance:
    _require_reason(request)
    return _review_clearance(
        session, institution_id=institution_id, student_clearance_id=student_clearance_id,
        user_id=user_id, target=StudentClearanceStatus.REJECTED,
        allowed={StudentClearanceStatus.PENDING, StudentClearanceStatus.CLEARED}, remarks=request.reason,
    )


def waive_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID, user_id: UUID, request: StudentClearanceActionRequest) -> StudentClearance:
    _require_reason(request)
    return _review_clearance(
        session, institution_id=institution_id, student_clearance_id=student_clearance_id,
        user_id=user_id, target=StudentClearanceStatus.WAIVED,
        allowed={StudentClearanceStatus.PENDING, StudentClearanceStatus.REJECTED}, remarks=request.reason,
    )


def reset_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID) -> StudentClearance:
    item = _resolve_student_clearance(session, institution_id=institution_id, student_clearance_id=student_clearance_id)
    if item.status not in {StudentClearanceStatus.CLEARED.value, StudentClearanceStatus.REJECTED.value, StudentClearanceStatus.WAIVED.value}:
        raise InvalidStudentClearanceTransitionError()
    item.status = StudentClearanceStatus.PENDING.value
    item.reviewed_at = None
    item.reviewed_by_user_id = None
    session.commit()
    session.refresh(item)
    return item


def compute_student_clearance_summary(session: Session, *, institution_id: UUID, student_id: UUID) -> StudentClearanceSummary:
    student = _resolve_student(session, institution_id=institution_id, student_id=student_id)
    requirements = list(session.scalars(select(ClearanceRequirement).where(
        ClearanceRequirement.institution_id == institution_id,
        ClearanceRequirement.status == ClearanceRequirementStatus.ACTIVE.value,
    ).order_by(ClearanceRequirement.sequence_number, ClearanceRequirement.name, ClearanceRequirement.id)).all())
    clearances = list(session.scalars(select(StudentClearance).where(
        StudentClearance.institution_id == institution_id,
        StudentClearance.student_id == student.id,
        StudentClearance.status != StudentClearanceStatus.INACTIVE.value,
    )).all())
    by_requirement = {item.clearance_requirement_id: item for item in clearances}
    items: list[StudentClearanceSummaryItem] = []
    counts = {"cleared": 0, "waived": 0, "rejected": 0, "pending": 0, "missing": 0}
    fully_cleared = True
    for requirement in requirements:
        clearance = by_requirement.get(requirement.id)
        item_status = clearance.status if clearance is not None else "missing"
        counts[item_status] += 1
        if requirement.is_mandatory and item_status not in {StudentClearanceStatus.CLEARED.value, StudentClearanceStatus.WAIVED.value}:
            fully_cleared = False
        items.append(StudentClearanceSummaryItem(
            clearance_requirement_id=requirement.id, name=requirement.name, code=requirement.code,
            is_mandatory=requirement.is_mandatory, sequence_number=requirement.sequence_number,
            student_clearance_id=clearance.id if clearance else None, status=item_status,
            remarks=clearance.remarks if clearance else None,
            evidence_reference=clearance.evidence_reference if clearance else None,
            reviewed_at=clearance.reviewed_at if clearance else None,
            reviewed_by_user_id=clearance.reviewed_by_user_id if clearance else None,
        ))
    mandatory = sum(item.is_mandatory for item in requirements)
    return StudentClearanceSummary(
        student_id=student.id, matriculation_number=student.matriculation_number,
        student_name=_student_display_name(student), total_active_requirements=len(requirements),
        mandatory_requirements=mandatory, optional_requirements=len(requirements) - mandatory,
        cleared_count=counts["cleared"], waived_count=counts["waived"],
        rejected_count=counts["rejected"], pending_count=counts["pending"],
        missing_count=counts["missing"], is_fully_cleared=fully_cleared, requirements=items,
    )


def evaluate_graduation_clearance(session: Session, *, institution_id: UUID, student_id: UUID) -> GraduationClearanceEvaluation:
    academic = evaluate_student_graduation_eligibility(session, institution_id=institution_id, student_id=student_id)
    summary = compute_student_clearance_summary(session, institution_id=institution_id, student_id=student_id)
    blockers: list[str] = []
    if not academic.eligible_for_graduation:
        blockers.append("academic_ineligibility")
    mandatory_statuses = {item.status for item in summary.requirements if item.is_mandatory}
    for status, blocker in (
        ("missing", "missing_mandatory_clearance"),
        (StudentClearanceStatus.PENDING.value, "pending_clearance"),
        (StudentClearanceStatus.REJECTED.value, "rejected_clearance"),
    ):
        if status in mandatory_statuses:
            blockers.append(blocker)
    academic_reasons = [str(getattr(reason, "value", reason)) for reason in academic.eligibility_reasons]
    return GraduationClearanceEvaluation(
        student_id=student_id,
        academically_eligible_for_graduation=academic.eligible_for_graduation,
        academic_eligibility_reasons=academic_reasons,
        administratively_cleared=summary.is_fully_cleared,
        clearance_blockers=blockers,
        ready_for_final_graduation_processing=academic.eligible_for_graduation and summary.is_fully_cleared,
    )


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    item = session.scalar(select(Student).options(joinedload(Student.user)).where(Student.id == student_id, Student.institution_id == institution_id))
    if item is None:
        raise StudentClearanceStudentNotFoundError()
    return item


def _resolve_requirement(session: Session, *, institution_id: UUID, requirement_id: UUID) -> ClearanceRequirement:
    item = session.scalar(select(ClearanceRequirement).where(
        ClearanceRequirement.id == requirement_id,
        ClearanceRequirement.institution_id == institution_id,
        ClearanceRequirement.status != ClearanceRequirementStatus.INACTIVE.value,
    ))
    if item is None:
        raise ClearanceRequirementNotFoundError()
    return item


def _resolve_student_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID) -> StudentClearance:
    item = session.scalar(select(StudentClearance).where(
        StudentClearance.id == student_clearance_id,
        StudentClearance.institution_id == institution_id,
        StudentClearance.status != StudentClearanceStatus.INACTIVE.value,
    ))
    if item is None:
        raise StudentClearanceNotFoundError()
    return item


def _ensure_requirement_code_available(session: Session, *, institution_id: UUID, code: str, exclude_id: UUID | None = None) -> None:
    statement = select(ClearanceRequirement.id).where(ClearanceRequirement.institution_id == institution_id, ClearanceRequirement.code == code)
    if exclude_id is not None:
        statement = statement.where(ClearanceRequirement.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateClearanceRequirementCodeError()


def _ensure_no_active_student_clearance(session: Session, *, student_id: UUID, requirement_id: UUID) -> None:
    if session.scalar(select(StudentClearance.id).where(
        StudentClearance.student_id == student_id,
        StudentClearance.clearance_requirement_id == requirement_id,
        StudentClearance.status != StudentClearanceStatus.INACTIVE.value,
    )) is not None:
        raise DuplicateStudentClearanceError()


def _review_clearance(session: Session, *, institution_id: UUID, student_clearance_id: UUID, user_id: UUID, target: StudentClearanceStatus, allowed: set[StudentClearanceStatus], remarks: str | None = None) -> StudentClearance:
    item = _resolve_student_clearance(session, institution_id=institution_id, student_clearance_id=student_clearance_id)
    if item.status not in {status.value for status in allowed}:
        raise InvalidStudentClearanceTransitionError()
    item.status = target.value
    item.reviewed_at = datetime.now(UTC)
    item.reviewed_by_user_id = user_id
    if remarks is not None:
        item.remarks = remarks
    session.commit()
    session.refresh(item)
    return item


def _require_reason(request: StudentClearanceActionRequest) -> None:
    if not request.reason:
        raise StudentClearanceReasonRequiredError()


def _commit(session: Session, conflict: type[Exception]) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise conflict() from error
