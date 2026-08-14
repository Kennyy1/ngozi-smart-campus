from copy import deepcopy
from datetime import UTC, datetime
from secrets import token_hex
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.academic_document import AcademicDocument
from app.models.graduation_record import GraduationRecord
from app.models.institution import Institution
from app.models.official_transcript import OfficialTranscript
from app.models.programme import Programme
from app.models.student import Student
from app.schemas.academic_document import (
    AcademicDocumentCreate, AcademicDocumentRevoke, AcademicDocumentStatus,
    AcademicDocumentType, AcademicDocumentUpdate, PublicAcademicDocumentVerification,
)
from app.services.transcript_service import compute_student_transcript


class AcademicDocumentNotFoundError(Exception): pass
class AcademicDocumentStudentNotFoundError(Exception): pass
class AcademicDocumentProgrammeNotFoundError(Exception): pass
class AcademicDocumentSourceNotFoundError(Exception): pass
class InvalidAcademicDocumentSourceError(Exception): pass
class DuplicateAcademicDocumentDraftError(Exception): pass
class AcademicDocumentIdentifierConflictError(Exception): pass
class InvalidAcademicDocumentTransitionError(Exception): pass


def create_academic_document(session: Session, *, institution_id: UUID, user_id: UUID, document_data: AcademicDocumentCreate) -> AcademicDocument:
    student = _resolve_student(session, institution_id=institution_id, student_id=document_data.student_id)
    now = datetime.now(UTC)
    graduation: GraduationRecord | None = None
    transcript: OfficialTranscript | None = None
    if document_data.document_type == AcademicDocumentType.CERTIFICATE:
        graduation = _resolve_graduation(session, institution_id=institution_id, graduation_record_id=document_data.graduation_record_id)
        _validate_certificate_source(graduation, student=student)
        programme = _resolve_programme(session, institution_id=institution_id, programme_id=graduation.programme_id)
        snapshot = _build_certificate_snapshot(session, institution_id=institution_id, student=student, programme=programme, graduation=graduation)
        title, prefix = "Certificate", "CERT"
    else:
        transcript = _resolve_optional_transcript(session, institution_id=institution_id, transcript_id=document_data.official_transcript_id)
        if transcript is not None:
            _validate_transcript_source(transcript, student=student)
        programme = _resolve_programme(session, institution_id=institution_id, programme_id=student.programme_id)
        snapshot = _build_statement_snapshot(session, institution_id=institution_id, student=student, transcript=transcript)
        title, prefix = "Statement of Result", "SOR"
    _require_no_duplicate_draft(session, institution_id=institution_id, student_id=student.id, document_type=document_data.document_type, graduation_record_id=graduation.id if graduation else None, official_transcript_id=transcript.id if transcript else None)
    document = AcademicDocument(
        institution_id=institution_id, student_id=student.id, programme_id=programme.id,
        graduation_record_id=graduation.id if graduation else None,
        official_transcript_id=transcript.id if transcript else None,
        document_type=document_data.document_type.value,
        document_reference=_generate_reference(session, prefix=prefix, now=now),
        verification_code=_generate_verification_code(session), status=AcademicDocumentStatus.DRAFT.value,
        title=title, snapshot_data=snapshot, generated_at=now,
        generated_by_user_id=user_id, remarks=document_data.remarks,
    )
    session.add(document)
    _commit(session)
    session.refresh(document)
    return document


def list_academic_documents(session: Session, *, institution_id: UUID, student_id: UUID | None = None, programme_id: UUID | None = None, document_type: AcademicDocumentType | None = None, status: AcademicDocumentStatus | None = None, document_reference: str | None = None, graduation_record_id: UUID | None = None, issued_by_user_id: UUID | None = None) -> list[AcademicDocument]:
    statement = select(AcademicDocument).where(AcademicDocument.institution_id == institution_id, AcademicDocument.status != AcademicDocumentStatus.INACTIVE.value)
    for column, value in (
        (AcademicDocument.student_id, student_id), (AcademicDocument.programme_id, programme_id),
        (AcademicDocument.document_type, document_type.value if document_type else None),
        (AcademicDocument.status, status.value if status else None),
        (AcademicDocument.document_reference, document_reference.strip() if document_reference else None),
        (AcademicDocument.graduation_record_id, graduation_record_id),
        (AcademicDocument.issued_by_user_id, issued_by_user_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    return list(session.scalars(statement.order_by(AcademicDocument.generated_at.desc(), AcademicDocument.id)).all())


def get_academic_document(session: Session, *, institution_id: UUID, document_id: UUID) -> AcademicDocument:
    return _resolve_document(session, institution_id=institution_id, document_id=document_id)


def get_academic_document_by_reference(session: Session, *, institution_id: UUID, document_reference: str) -> AcademicDocument:
    return _resolve_lookup(session, institution_id=institution_id, column=AcademicDocument.document_reference, value=document_reference.strip())


def get_academic_document_by_verification_code(session: Session, *, institution_id: UUID, verification_code: str) -> AcademicDocument:
    return _resolve_lookup(session, institution_id=institution_id, column=AcademicDocument.verification_code, value=verification_code.strip())


def update_academic_document(session: Session, *, institution_id: UUID, document_id: UUID, document_data: AcademicDocumentUpdate) -> AcademicDocument:
    document = _resolve_document(session, institution_id=institution_id, document_id=document_id)
    if "remarks" in document_data.model_fields_set:
        document.remarks = document_data.remarks
    session.commit(); session.refresh(document)
    return document


def refresh_academic_document(session: Session, *, institution_id: UUID, document_id: UUID, user_id: UUID) -> AcademicDocument:
    document = _resolve_document(session, institution_id=institution_id, document_id=document_id)
    _require_status(document, AcademicDocumentStatus.DRAFT)
    student = _resolve_student(session, institution_id=institution_id, student_id=document.student_id)
    if document.document_type == AcademicDocumentType.CERTIFICATE.value:
        graduation = _resolve_graduation(session, institution_id=institution_id, graduation_record_id=document.graduation_record_id)
        _validate_certificate_source(graduation, student=student)
        programme = _resolve_programme(session, institution_id=institution_id, programme_id=graduation.programme_id)
        document.snapshot_data = _build_certificate_snapshot(session, institution_id=institution_id, student=student, programme=programme, graduation=graduation)
    else:
        transcript = _resolve_optional_transcript(session, institution_id=institution_id, transcript_id=document.official_transcript_id)
        if transcript is not None:
            _validate_transcript_source(transcript, student=student)
        programme = _resolve_programme(session, institution_id=institution_id, programme_id=student.programme_id)
        document.snapshot_data = _build_statement_snapshot(session, institution_id=institution_id, student=student, transcript=transcript)
    document.programme_id = programme.id
    document.generated_at = datetime.now(UTC)
    document.generated_by_user_id = user_id
    session.commit(); session.refresh(document)
    return document


def issue_academic_document(session: Session, *, institution_id: UUID, document_id: UUID, user_id: UUID) -> AcademicDocument:
    document = _resolve_document(session, institution_id=institution_id, document_id=document_id)
    _require_status(document, AcademicDocumentStatus.DRAFT)
    student = _resolve_student(session, institution_id=institution_id, student_id=document.student_id)
    if document.document_type == AcademicDocumentType.CERTIFICATE.value:
        graduation = _resolve_graduation(session, institution_id=institution_id, graduation_record_id=document.graduation_record_id)
        _validate_certificate_source(graduation, student=student)
    elif document.official_transcript_id is not None:
        transcript = _resolve_optional_transcript(session, institution_id=institution_id, transcript_id=document.official_transcript_id)
        if transcript is None:
            raise AcademicDocumentSourceNotFoundError()
        _validate_transcript_source(transcript, student=student)
    else:
        compute_student_transcript(session, institution_id=institution_id, student_id=student.id)
    document.status = AcademicDocumentStatus.ISSUED.value
    document.issued_at = datetime.now(UTC)
    document.issued_by_user_id = user_id
    session.commit(); session.refresh(document)
    return document


def revoke_academic_document(session: Session, *, institution_id: UUID, document_id: UUID, user_id: UUID, request: AcademicDocumentRevoke) -> AcademicDocument:
    document = _resolve_document(session, institution_id=institution_id, document_id=document_id)
    _require_status(document, AcademicDocumentStatus.ISSUED)
    document.status = AcademicDocumentStatus.REVOKED.value
    document.revoked_at = datetime.now(UTC)
    document.revoked_by_user_id = user_id
    document.revocation_reason = request.reason
    session.commit(); session.refresh(document)
    return document


def verify_public_academic_document(session: Session, *, verification_code: str) -> PublicAcademicDocumentVerification:
    document = session.scalar(select(AcademicDocument).where(
        AcademicDocument.verification_code == verification_code.strip(),
        AcademicDocument.status.in_((AcademicDocumentStatus.ISSUED.value, AcademicDocumentStatus.REVOKED.value)),
    ))
    if document is None:
        raise AcademicDocumentNotFoundError()
    snapshot = document.snapshot_data
    return PublicAcademicDocumentVerification(
        valid=document.status == AcademicDocumentStatus.ISSUED.value,
        document_type=AcademicDocumentType(document.document_type), document_reference=document.document_reference,
        status=AcademicDocumentStatus(document.status), student_name=str(snapshot["student_name"]),
        programme_name=snapshot.get("programme_name"), award_title=snapshot.get("award_title"),
        degree_classification_label=snapshot.get("degree_classification_label"),
        graduation_date=snapshot.get("graduation_date"), issued_at=document.issued_at,
    )


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    item = session.scalar(select(Student).options(joinedload(Student.user)).where(Student.id == student_id, Student.institution_id == institution_id))
    if item is None: raise AcademicDocumentStudentNotFoundError()
    return item


def _resolve_programme(session: Session, *, institution_id: UUID, programme_id: UUID | None) -> Programme:
    item = session.scalar(select(Programme).where(Programme.id == programme_id, Programme.institution_id == institution_id))
    if item is None: raise AcademicDocumentProgrammeNotFoundError()
    return item


def _resolve_graduation(session: Session, *, institution_id: UUID, graduation_record_id: UUID | None) -> GraduationRecord:
    item = session.scalar(select(GraduationRecord).where(GraduationRecord.id == graduation_record_id, GraduationRecord.institution_id == institution_id))
    if item is None: raise AcademicDocumentSourceNotFoundError()
    return item


def _resolve_optional_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID | None) -> OfficialTranscript | None:
    if transcript_id is None: return None
    item = session.scalar(select(OfficialTranscript).where(OfficialTranscript.id == transcript_id, OfficialTranscript.institution_id == institution_id))
    if item is None: raise AcademicDocumentSourceNotFoundError()
    return item


def _resolve_document(session: Session, *, institution_id: UUID, document_id: UUID) -> AcademicDocument:
    item = session.scalar(select(AcademicDocument).where(AcademicDocument.id == document_id, AcademicDocument.institution_id == institution_id, AcademicDocument.status != AcademicDocumentStatus.INACTIVE.value))
    if item is None: raise AcademicDocumentNotFoundError()
    return item


def _resolve_lookup(session: Session, *, institution_id: UUID, column: object, value: str) -> AcademicDocument:
    item = session.scalar(select(AcademicDocument).where(AcademicDocument.institution_id == institution_id, column == value, AcademicDocument.status != AcademicDocumentStatus.INACTIVE.value))
    if item is None: raise AcademicDocumentNotFoundError()
    return item


def _validate_certificate_source(graduation: GraduationRecord, *, student: Student) -> None:
    if graduation.student_id != student.id or graduation.programme_id != student.programme_id or graduation.status != "confirmed" or not graduation.outcome_snapshot or graduation.degree_classification is None:
        raise InvalidAcademicDocumentSourceError()


def _validate_transcript_source(transcript: OfficialTranscript, *, student: Student) -> None:
    if transcript.student_id != student.id or transcript.programme_id != student.programme_id or transcript.status != "issued":
        raise InvalidAcademicDocumentSourceError()


def _student_name(student: Student) -> str:
    return " ".join((student.user.first_name.strip(), student.user.last_name.strip()))


def _institution_name(session: Session, institution_id: UUID) -> str:
    return str(session.scalar(select(Institution.name).where(Institution.id == institution_id)))


def _build_certificate_snapshot(session: Session, *, institution_id: UUID, student: Student, programme: Programme, graduation: GraduationRecord) -> dict[str, object]:
    return {
        "institution_name": _institution_name(session, institution_id), "student_id": str(student.id),
        "matriculation_number": student.matriculation_number, "student_name": _student_name(student),
        "programme_id": str(programme.id), "programme_name": programme.name, "programme_code": programme.code,
        "award_title": graduation.award_title, "graduation_reference": graduation.graduation_reference,
        "graduation_date": graduation.graduation_date.isoformat() if graduation.graduation_date else None,
        "final_cgpa": str(graduation.final_cgpa), "degree_classification": graduation.degree_classification,
        "degree_classification_label": graduation.degree_classification_label,
        "academic_standing": graduation.academic_standing, "confirmed_at": graduation.confirmed_at.isoformat() if graduation.confirmed_at else None,
    }


def _build_statement_snapshot(session: Session, *, institution_id: UUID, student: Student, transcript: OfficialTranscript | None) -> dict[str, object]:
    if transcript is not None:
        snapshot = deepcopy(transcript.snapshot_data)
        snapshot["official_transcript_reference"] = transcript.transcript_reference
    else:
        snapshot = compute_student_transcript(session, institution_id=institution_id, student_id=student.id).model_dump(mode="json")
    snapshot["institution_name"] = _institution_name(session, institution_id)
    return snapshot


def _require_no_duplicate_draft(session: Session, *, institution_id: UUID, student_id: UUID, document_type: AcademicDocumentType, graduation_record_id: UUID | None, official_transcript_id: UUID | None) -> None:
    statement = select(AcademicDocument.id).where(AcademicDocument.institution_id == institution_id, AcademicDocument.student_id == student_id, AcademicDocument.document_type == document_type.value, AcademicDocument.status == AcademicDocumentStatus.DRAFT.value)
    statement = statement.where(AcademicDocument.graduation_record_id == graduation_record_id, AcademicDocument.official_transcript_id == official_transcript_id)
    if session.scalar(statement) is not None: raise DuplicateAcademicDocumentDraftError()


def _generate_reference(session: Session, *, prefix: str, now: datetime) -> str:
    for _ in range(10):
        value = f"{prefix}-{now.year}-{uuid4().hex[:12].upper()}"
        if session.scalar(select(AcademicDocument.id).where(AcademicDocument.document_reference == value)) is None: return value
    raise AcademicDocumentIdentifierConflictError()


def _generate_verification_code(session: Session) -> str:
    for _ in range(10):
        value = token_hex(16).upper()
        if session.scalar(select(AcademicDocument.id).where(AcademicDocument.verification_code == value)) is None: return value
    raise AcademicDocumentIdentifierConflictError()


def _require_status(document: AcademicDocument, expected: AcademicDocumentStatus) -> None:
    if document.status != expected.value: raise InvalidAcademicDocumentTransitionError()


def _commit(session: Session) -> None:
    try: session.commit()
    except IntegrityError as error:
        session.rollback()
        raise AcademicDocumentIdentifierConflictError() from error
