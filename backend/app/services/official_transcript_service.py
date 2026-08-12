from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.official_transcript import OfficialTranscript
from app.models.student import Student
from app.schemas.official_transcript import (
    OfficialTranscriptCreate, OfficialTranscriptStatus, OfficialTranscriptUpdate,
    TranscriptRevokeRequest,
)
from app.schemas.transcript import StudentTranscriptSummary
from app.services.transcript_service import compute_student_transcript


class OfficialTranscriptNotFoundError(Exception): pass
class OfficialTranscriptStudentNotFoundError(Exception): pass
class DuplicateTranscriptReferenceError(Exception): pass
class InvalidOfficialTranscriptTransitionError(Exception): pass
class OfficialTranscriptImmutableError(Exception): pass


def create_official_transcript(session: Session, *, institution_id: UUID, user_id: UUID, transcript_data: OfficialTranscriptCreate) -> OfficialTranscript:
    student = _resolve_student(session, institution_id=institution_id, student_id=transcript_data.student_id)
    snapshot = compute_student_transcript(session, institution_id=institution_id, student_id=student.id)
    now = datetime.now(UTC)
    transcript = OfficialTranscript(
        institution_id=institution_id, student_id=student.id, programme_id=snapshot.programme_id,
        transcript_reference=_generate_transcript_reference(session, institution_id=institution_id, now=now),
        status=OfficialTranscriptStatus.DRAFT.value, snapshot_data=_serialize_snapshot(snapshot),
        generated_at=now, generated_by_user_id=user_id, remarks=transcript_data.remarks,
    )
    session.add(transcript)
    _commit(session)
    session.refresh(transcript)
    return transcript


def list_official_transcripts(session: Session, *, institution_id: UUID, student_id: UUID | None = None, programme_id: UUID | None = None, status: OfficialTranscriptStatus | None = None, transcript_reference: str | None = None) -> list[OfficialTranscript]:
    statement = select(OfficialTranscript).where(OfficialTranscript.institution_id == institution_id, OfficialTranscript.status != OfficialTranscriptStatus.INACTIVE.value)
    for column, value in (
        (OfficialTranscript.student_id, student_id), (OfficialTranscript.programme_id, programme_id),
        (OfficialTranscript.status, status.value if status else None),
        (OfficialTranscript.transcript_reference, transcript_reference.strip() if transcript_reference else None),
    ):
        if value is not None:
            statement = statement.where(column == value)
    return list(session.scalars(statement.order_by(OfficialTranscript.generated_at.desc(), OfficialTranscript.id)).all())


def get_official_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID) -> OfficialTranscript:
    return _resolve_transcript(session, institution_id=institution_id, transcript_id=transcript_id)


def get_official_transcript_by_reference(session: Session, *, institution_id: UUID, transcript_reference: str) -> OfficialTranscript:
    item = session.scalar(select(OfficialTranscript).where(
        OfficialTranscript.institution_id == institution_id,
        OfficialTranscript.transcript_reference == transcript_reference.strip(),
        OfficialTranscript.status != OfficialTranscriptStatus.INACTIVE.value,
    ))
    if item is None:
        raise OfficialTranscriptNotFoundError()
    return item


def update_official_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID, transcript_data: OfficialTranscriptUpdate) -> OfficialTranscript:
    transcript = _resolve_transcript(session, institution_id=institution_id, transcript_id=transcript_id)
    if "remarks" in transcript_data.model_fields_set:
        transcript.remarks = transcript_data.remarks
    session.commit(); session.refresh(transcript)
    return transcript


def refresh_official_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID, user_id: UUID) -> OfficialTranscript:
    transcript = _resolve_transcript(session, institution_id=institution_id, transcript_id=transcript_id)
    _require_status(transcript, OfficialTranscriptStatus.DRAFT)
    snapshot = compute_student_transcript(session, institution_id=institution_id, student_id=transcript.student_id)
    transcript.snapshot_data = _serialize_snapshot(snapshot)
    transcript.programme_id = snapshot.programme_id
    transcript.generated_at = datetime.now(UTC)
    transcript.generated_by_user_id = user_id
    session.commit(); session.refresh(transcript)
    return transcript


def issue_official_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID, user_id: UUID) -> OfficialTranscript:
    transcript = _resolve_transcript(session, institution_id=institution_id, transcript_id=transcript_id)
    _require_status(transcript, OfficialTranscriptStatus.DRAFT)
    transcript.status = OfficialTranscriptStatus.ISSUED.value
    transcript.issued_at = datetime.now(UTC)
    transcript.issued_by_user_id = user_id
    session.commit(); session.refresh(transcript)
    return transcript


def revoke_official_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID, user_id: UUID, request: TranscriptRevokeRequest) -> OfficialTranscript:
    transcript = _resolve_transcript(session, institution_id=institution_id, transcript_id=transcript_id)
    _require_status(transcript, OfficialTranscriptStatus.ISSUED)
    transcript.status = OfficialTranscriptStatus.REVOKED.value
    transcript.revoked_at = datetime.now(UTC)
    transcript.revoked_by_user_id = user_id
    transcript.revocation_reason = request.reason
    session.commit(); session.refresh(transcript)
    return transcript


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    item = session.scalar(select(Student).where(Student.id == student_id, Student.institution_id == institution_id))
    if item is None:
        raise OfficialTranscriptStudentNotFoundError()
    return item


def _resolve_transcript(session: Session, *, institution_id: UUID, transcript_id: UUID) -> OfficialTranscript:
    item = session.scalar(select(OfficialTranscript).where(
        OfficialTranscript.id == transcript_id, OfficialTranscript.institution_id == institution_id,
        OfficialTranscript.status != OfficialTranscriptStatus.INACTIVE.value,
    ))
    if item is None:
        raise OfficialTranscriptNotFoundError()
    return item


def _generate_transcript_reference(session: Session, *, institution_id: UUID, now: datetime) -> str:
    for _ in range(10):
        reference = f"TRX-{now.year}-{uuid4().hex[:12].upper()}"
        exists = session.scalar(select(OfficialTranscript.id).where(
            OfficialTranscript.institution_id == institution_id,
            OfficialTranscript.transcript_reference == reference,
        ))
        if exists is None:
            return reference
    raise DuplicateTranscriptReferenceError()


def _serialize_snapshot(snapshot: StudentTranscriptSummary) -> dict[str, object]:
    return snapshot.model_dump(mode="json")


def _require_status(transcript: OfficialTranscript, expected: OfficialTranscriptStatus) -> None:
    if transcript.status != expected.value:
        raise InvalidOfficialTranscriptTransitionError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateTranscriptReferenceError() from error
