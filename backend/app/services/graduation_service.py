from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.graduation_record import GraduationRecord
from app.models.programme import Programme
from app.models.student import Student
from app.schemas.degree_classification import GraduationOutcomeEvaluation
from app.schemas.graduation_eligibility import GraduationEligibilityEvaluation
from app.schemas.graduation_record import (
    GraduationRecordConfirm, GraduationRecordCreate, GraduationRecordRevoke,
    GraduationRecordStatus, GraduationRecordUpdate,
)
from app.services.degree_classification_policy import GraduationOutcome
from app.services.degree_classification_service import evaluate_student_degree_classification
from app.services.graduation_eligibility_service import evaluate_student_graduation_eligibility


class GraduationRecordNotFoundError(Exception): pass
class GraduationStudentNotFoundError(Exception): pass
class GraduationProgrammeNotFoundError(Exception): pass
class GraduationStudentIneligibleError(Exception): pass
class GraduationOutcomeUnavailableError(Exception): pass
class DuplicateGraduationRecordError(Exception): pass
class GraduationReferenceConflictError(Exception): pass
class InvalidGraduationTransitionError(Exception): pass
class InvalidGraduationDateError(Exception): pass


def create_graduation_record(session: Session, *, institution_id: UUID, user_id: UUID, graduation_data: GraduationRecordCreate) -> GraduationRecord:
    student = _resolve_student(session, institution_id=institution_id, student_id=graduation_data.student_id)
    programme = _resolve_programme(session, institution_id=institution_id, programme_id=student.programme_id)
    _require_no_active_record(session, institution_id=institution_id, student_id=student.id, programme_id=programme.id)
    eligibility, outcome = _evaluate_academic_state(session, institution_id=institution_id, student_id=student.id)
    now = datetime.now(UTC)
    record = GraduationRecord(
        institution_id=institution_id, student_id=student.id, programme_id=programme.id,
        graduation_reference=_generate_graduation_reference(session, now=now),
        status=GraduationRecordStatus.DRAFT.value, award_title=_derive_award_title(programme),
        degree_classification=_enum_value(outcome.degree_classification),
        degree_classification_label=outcome.degree_classification_label,
        final_cgpa=outcome.cgpa, academic_standing=_enum_value(outcome.academic_standing),
        eligibility_snapshot=_serialize_snapshot(eligibility), outcome_snapshot=_serialize_snapshot(outcome),
        prepared_at=now, prepared_by_user_id=user_id, remarks=graduation_data.remarks,
    )
    session.add(record)
    _commit(session)
    session.refresh(record)
    return record


def list_graduation_records(session: Session, *, institution_id: UUID, student_id: UUID | None = None, programme_id: UUID | None = None, status: GraduationRecordStatus | None = None, graduation_reference: str | None = None, graduation_date: date | None = None, degree_classification: str | None = None) -> list[GraduationRecord]:
    statement = select(GraduationRecord).where(GraduationRecord.institution_id == institution_id, GraduationRecord.status != GraduationRecordStatus.INACTIVE.value)
    filters = (
        (GraduationRecord.student_id, student_id), (GraduationRecord.programme_id, programme_id),
        (GraduationRecord.status, status.value if status else None),
        (GraduationRecord.graduation_reference, graduation_reference.strip() if graduation_reference else None),
        (GraduationRecord.graduation_date, graduation_date),
        (GraduationRecord.degree_classification, degree_classification.strip() if degree_classification else None),
    )
    for column, value in filters:
        if value is not None:
            statement = statement.where(column == value)
    return list(session.scalars(statement.order_by(GraduationRecord.prepared_at.desc(), GraduationRecord.id)).all())


def get_graduation_record(session: Session, *, institution_id: UUID, graduation_id: UUID) -> GraduationRecord:
    return _resolve_record(session, institution_id=institution_id, graduation_id=graduation_id)


def get_graduation_record_by_reference(session: Session, *, institution_id: UUID, graduation_reference: str) -> GraduationRecord:
    item = session.scalar(select(GraduationRecord).where(
        GraduationRecord.institution_id == institution_id,
        GraduationRecord.graduation_reference == graduation_reference.strip(),
        GraduationRecord.status != GraduationRecordStatus.INACTIVE.value,
    ))
    if item is None:
        raise GraduationRecordNotFoundError()
    return item


def update_graduation_record(session: Session, *, institution_id: UUID, graduation_id: UUID, graduation_data: GraduationRecordUpdate) -> GraduationRecord:
    record = _resolve_record(session, institution_id=institution_id, graduation_id=graduation_id)
    if "remarks" in graduation_data.model_fields_set:
        record.remarks = graduation_data.remarks
    session.commit()
    session.refresh(record)
    return record


def refresh_graduation_record(session: Session, *, institution_id: UUID, graduation_id: UUID, user_id: UUID) -> GraduationRecord:
    record = _resolve_record(session, institution_id=institution_id, graduation_id=graduation_id)
    _require_status(record, GraduationRecordStatus.DRAFT)
    programme = _resolve_programme(session, institution_id=institution_id, programme_id=record.programme_id)
    eligibility, outcome = _evaluate_academic_state(session, institution_id=institution_id, student_id=record.student_id)
    _apply_academic_state(record, programme=programme, eligibility=eligibility, outcome=outcome)
    record.prepared_at = datetime.now(UTC)
    record.prepared_by_user_id = user_id
    session.commit()
    session.refresh(record)
    return record


def confirm_graduation(session: Session, *, institution_id: UUID, graduation_id: UUID, user_id: UUID, request: GraduationRecordConfirm) -> GraduationRecord:
    record = _resolve_record(session, institution_id=institution_id, graduation_id=graduation_id)
    _require_status(record, GraduationRecordStatus.DRAFT)
    student = _resolve_student(session, institution_id=institution_id, student_id=record.student_id)
    if request.graduation_date.year < student.admission_year:
        raise InvalidGraduationDateError()
    programme = _resolve_programme(session, institution_id=institution_id, programme_id=record.programme_id)
    eligibility, outcome = _evaluate_academic_state(session, institution_id=institution_id, student_id=student.id)
    _apply_academic_state(record, programme=programme, eligibility=eligibility, outcome=outcome)
    now = datetime.now(UTC)
    record.previous_student_enrollment_status = student.enrollment_status
    record.previous_student_graduation_date = student.graduation_date
    record.status = GraduationRecordStatus.CONFIRMED.value
    record.graduation_date = request.graduation_date
    record.confirmed_at = now
    record.confirmed_by_user_id = user_id
    student.enrollment_status = "graduated"
    student.graduation_date = request.graduation_date
    session.commit()
    session.refresh(record)
    return record


def revoke_graduation(session: Session, *, institution_id: UUID, graduation_id: UUID, user_id: UUID, request: GraduationRecordRevoke) -> GraduationRecord:
    record = _resolve_record(session, institution_id=institution_id, graduation_id=graduation_id)
    _require_status(record, GraduationRecordStatus.CONFIRMED)
    student = _resolve_student(session, institution_id=institution_id, student_id=record.student_id)
    record.status = GraduationRecordStatus.REVOKED.value
    record.revoked_at = datetime.now(UTC)
    record.revoked_by_user_id = user_id
    record.revocation_reason = request.reason
    student.enrollment_status = record.previous_student_enrollment_status
    student.graduation_date = record.previous_student_graduation_date
    session.commit()
    session.refresh(record)
    return record


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    item = session.scalar(select(Student).where(Student.id == student_id, Student.institution_id == institution_id))
    if item is None:
        raise GraduationStudentNotFoundError()
    return item


def _resolve_programme(session: Session, *, institution_id: UUID, programme_id: UUID | None) -> Programme:
    item = session.scalar(select(Programme).where(Programme.id == programme_id, Programme.institution_id == institution_id))
    if item is None:
        raise GraduationProgrammeNotFoundError()
    return item


def _resolve_record(session: Session, *, institution_id: UUID, graduation_id: UUID) -> GraduationRecord:
    item = session.scalar(select(GraduationRecord).where(
        GraduationRecord.id == graduation_id, GraduationRecord.institution_id == institution_id,
        GraduationRecord.status != GraduationRecordStatus.INACTIVE.value,
    ))
    if item is None:
        raise GraduationRecordNotFoundError()
    return item


def _require_no_active_record(session: Session, *, institution_id: UUID, student_id: UUID, programme_id: UUID) -> None:
    existing = session.scalar(select(GraduationRecord.id).where(
        GraduationRecord.institution_id == institution_id, GraduationRecord.student_id == student_id,
        GraduationRecord.programme_id == programme_id,
        GraduationRecord.status.in_((GraduationRecordStatus.DRAFT.value, GraduationRecordStatus.CONFIRMED.value)),
    ))
    if existing is not None:
        raise DuplicateGraduationRecordError()


def _evaluate_academic_state(session: Session, *, institution_id: UUID, student_id: UUID) -> tuple[GraduationEligibilityEvaluation, GraduationOutcomeEvaluation]:
    eligibility = evaluate_student_graduation_eligibility(session, institution_id=institution_id, student_id=student_id)
    if not eligibility.eligible_for_graduation:
        raise GraduationStudentIneligibleError()
    outcome = evaluate_student_degree_classification(session, institution_id=institution_id, student_id=student_id)
    if not outcome.eligible_for_graduation or outcome.graduation_outcome != GraduationOutcome.ELIGIBLE_WITH_CLASSIFICATION or outcome.degree_classification is None:
        raise GraduationOutcomeUnavailableError()
    return eligibility, outcome


def _apply_academic_state(record: GraduationRecord, *, programme: Programme, eligibility: GraduationEligibilityEvaluation, outcome: GraduationOutcomeEvaluation) -> None:
    record.award_title = _derive_award_title(programme)
    record.degree_classification = _enum_value(outcome.degree_classification)
    record.degree_classification_label = outcome.degree_classification_label
    record.final_cgpa = outcome.cgpa
    record.academic_standing = _enum_value(outcome.academic_standing)
    record.eligibility_snapshot = _serialize_snapshot(eligibility)
    record.outcome_snapshot = _serialize_snapshot(outcome)


def _generate_graduation_reference(session: Session, *, now: datetime) -> str:
    for _ in range(10):
        reference = f"GRAD-{now.year}-{uuid4().hex[:12].upper()}"
        if session.scalar(select(GraduationRecord.id).where(GraduationRecord.graduation_reference == reference)) is None:
            return reference
    raise GraduationReferenceConflictError()


def _derive_award_title(programme: Programme) -> str:
    return f"{programme.award.strip()} in {programme.name.strip()}"


def _serialize_snapshot(snapshot: GraduationEligibilityEvaluation | GraduationOutcomeEvaluation) -> dict[str, object]:
    return snapshot.model_dump(mode="json")


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _require_status(record: GraduationRecord, expected: GraduationRecordStatus) -> None:
    if record.status != expected.value:
        raise InvalidGraduationTransitionError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise GraduationReferenceConflictError() from error
