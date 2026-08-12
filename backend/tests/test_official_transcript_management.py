from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import dependencies
from app.api.v1.endpoints import official_transcripts
from app.main import app
from app.models.official_transcript import OfficialTranscript
from app.models.student import Student
from app.schemas.official_transcript import (
    OfficialTranscriptCreate, OfficialTranscriptStatus, OfficialTranscriptUpdate,
    TranscriptRevokeRequest,
)
from app.schemas.transcript import StudentTranscriptSummary
from app.services import official_transcript_service as service
from app.services.academic_progression_policy import AcademicStanding
from tests.test_academic_performance import Session as ReadSession


class Session(ReadSession):
    def add(self, value): self.added.append(value)
    def commit(self): self.commits += 1
    def refresh(self, value): return None
    def rollback(self): return None
    def scalars(self, statement): self.statements.append(statement); return Rows(self.values.pop(0) if self.values else [])


class Rows:
    def __init__(self, values): self.values = values
    def all(self): return self.values


def snapshot(student_id=None, programme_id=None, *, cgpa="4.00") -> StudentTranscriptSummary:
    return StudentTranscriptSummary(
        student_id=student_id or uuid4(), matriculation_number="NSC/1", student_name="Ada Lovelace",
        programme_id=programme_id or uuid4(), programme_name="Computer Science", programme_code="CSC",
        current_level="Year One", admission_year=2025, enrollment_status="active",
        cumulative_attempted_units=3, cumulative_earned_units=3,
        cumulative_quality_points=Decimal("12.00"), total_courses=1, passed_courses=1,
        failed_courses=0, cgpa=Decimal(cgpa), academic_standing=AcademicStanding.GOOD_STANDING,
        academic_sessions=[],
    )


def student(institution_id, programme_id) -> Student:
    return Student(id=uuid4(), institution_id=institution_id, user_id=uuid4(), programme_id=programme_id, matriculation_number="NSC/1", admission_year=2025, current_level="Year One", enrollment_status="active")


def transcript(institution_id, *, status="draft", data=None) -> OfficialTranscript:
    now = datetime.now(UTC)
    return OfficialTranscript(id=uuid4(), institution_id=institution_id, student_id=uuid4(), programme_id=uuid4(), transcript_reference="TRX-2026-ABCDEF123456", status=status, snapshot_data=data or snapshot().model_dump(mode="json"), generated_at=now, generated_by_user_id=uuid4(), created_at=now, updated_at=now)


def test_create_schema_rejects_server_managed_fields_and_revoke_normalizes() -> None:
    with pytest.raises(ValidationError): OfficialTranscriptCreate(student_id=uuid4(), transcript_reference="bad")  # type: ignore[call-arg]
    with pytest.raises(ValidationError): OfficialTranscriptUpdate(snapshot_data={})  # type: ignore[call-arg]
    assert TranscriptRevokeRequest(reason="  superseded  ").reason == "superseded"
    with pytest.raises(ValidationError): TranscriptRevokeRequest(reason="   ")


def test_create_draft_derives_scope_snapshot_reference_and_commits_once(monkeypatch: pytest.MonkeyPatch) -> None:
    institution_id = uuid4(); programme_id = uuid4(); item = student(institution_id, programme_id); computed = snapshot(item.id, programme_id)
    monkeypatch.setattr(service, "compute_student_transcript", lambda *_, **__: computed)
    db = Session(item, None)
    result = service.create_official_transcript(db, institution_id=institution_id, user_id=item.user_id, transcript_data=OfficialTranscriptCreate(student_id=item.id, remarks=" note "))  # type: ignore[arg-type]
    assert result.institution_id == institution_id and result.student_id == item.id and result.programme_id == programme_id
    assert result.status == "draft" and result.transcript_reference.startswith("TRX-2026-")
    assert result.snapshot_data["student_name"] == "Ada Lovelace" and result.snapshot_data["cgpa"] == "4.00"
    assert "assessment_score" not in str(result.snapshot_data).lower() and "examination_score" not in str(result.snapshot_data).lower()
    assert db.commits == 1 and db.added == [result]


def test_reference_generation_is_collision_checked_and_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    values = iter([type("U", (), {"hex": "a" * 32})(), type("U", (), {"hex": "b" * 32})()])
    monkeypatch.setattr(service, "uuid4", lambda: next(values))
    db = Session(object(), None)
    reference = service._generate_transcript_reference(db, institution_id=uuid4(), now=datetime(2026, 1, 1, tzinfo=UTC))  # type: ignore[arg-type]
    assert reference == "TRX-2026-BBBBBBBBBBBB" and len(db.statements) == 2


def test_list_filters_and_institution_scope() -> None:
    db = Session([])
    service.list_official_transcripts(db, institution_id=uuid4(), student_id=uuid4(), programme_id=uuid4(), status=OfficialTranscriptStatus.ISSUED, transcript_reference=" TRX-X ")  # type: ignore[arg-type]
    sql = str(db.statements[0]); params = tuple(db.statements[0].compile().params.values())
    assert all(name in sql for name in ("institution_id", "student_id", "programme_id", "status", "transcript_reference"))
    assert "issued" in params and "TRX-X" in params


def test_lookup_and_missing_records_are_institution_scoped() -> None:
    institution_id = uuid4(); item = transcript(institution_id)
    assert service.get_official_transcript_by_reference(Session(item), institution_id=institution_id, transcript_reference=item.transcript_reference) is item  # type: ignore[arg-type]
    with pytest.raises(service.OfficialTranscriptNotFoundError): service.get_official_transcript(Session(), institution_id=uuid4(), transcript_id=item.id)  # type: ignore[arg-type]
    with pytest.raises(service.OfficialTranscriptStudentNotFoundError): service.create_official_transcript(Session(), institution_id=uuid4(), user_id=uuid4(), transcript_data=OfficialTranscriptCreate(student_id=uuid4()))  # type: ignore[arg-type]


def test_remarks_are_only_patchable_field() -> None:
    item = transcript(uuid4(), status="issued"); original = dict(item.snapshot_data)
    db = Session(item)
    result = service.update_official_transcript(db, institution_id=item.institution_id, transcript_id=item.id, transcript_data=OfficialTranscriptUpdate(remarks=" admin note "))  # type: ignore[arg-type]
    assert result.remarks == "admin note" and result.snapshot_data == original and result.status == "issued"


def test_draft_refresh_changes_snapshot_actor_time_but_preserves_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    item = transcript(uuid4()); original_id = item.id; original_reference = item.transcript_reference; original_time = item.generated_at; actor = uuid4()
    refreshed = snapshot(item.student_id, item.programme_id, cgpa="3.00")
    monkeypatch.setattr(service, "compute_student_transcript", lambda *_, **__: refreshed)
    result = service.refresh_official_transcript(Session(item), institution_id=item.institution_id, transcript_id=item.id, user_id=actor)  # type: ignore[arg-type]
    assert result.id == original_id and result.transcript_reference == original_reference
    assert result.snapshot_data["cgpa"] == "3.00" and result.generated_by_user_id == actor and result.generated_at >= original_time


def test_issue_and_revoke_preserve_snapshot_and_record_audit_fields() -> None:
    item = transcript(uuid4()); original = dict(item.snapshot_data); issuer = uuid4()
    issued = service.issue_official_transcript(Session(item), institution_id=item.institution_id, transcript_id=item.id, user_id=issuer)  # type: ignore[arg-type]
    assert issued.status == "issued" and issued.issued_at and issued.issued_by_user_id == issuer and issued.snapshot_data == original
    revoker = uuid4()
    revoked = service.revoke_official_transcript(Session(item), institution_id=item.institution_id, transcript_id=item.id, user_id=revoker, request=TranscriptRevokeRequest(reason="Superseded"))  # type: ignore[arg-type]
    assert revoked.status == "revoked" and revoked.revoked_at and revoked.revoked_by_user_id == revoker
    assert revoked.revocation_reason == "Superseded" and revoked.snapshot_data == original


@pytest.mark.parametrize(("operation", "status"), [("issue", "issued"), ("refresh", "issued"), ("revoke", "draft"), ("revoke", "revoked")])
def test_invalid_lifecycle_transitions_return_domain_conflict(operation: str, status: str) -> None:
    item = transcript(uuid4(), status=status); db = Session(item)
    with pytest.raises(service.InvalidOfficialTranscriptTransitionError):
        if operation == "issue": service.issue_official_transcript(db, institution_id=item.institution_id, transcript_id=item.id, user_id=uuid4())  # type: ignore[arg-type]
        elif operation == "refresh": service.refresh_official_transcript(db, institution_id=item.institution_id, transcript_id=item.id, user_id=uuid4())  # type: ignore[arg-type]
        else: service.revoke_official_transcript(db, institution_id=item.institution_id, transcript_id=item.id, user_id=uuid4(), request=TranscriptRevokeRequest(reason="x"))  # type: ignore[arg-type]


def test_routes_static_order_authentication_and_mapping() -> None:
    paths = app.openapi()["paths"]
    expected = ("/api/v1/official-transcripts", "/api/v1/official-transcripts/by-reference/{transcript_reference}", "/api/v1/official-transcripts/{transcript_id}", "/api/v1/official-transcripts/{transcript_id}/refresh", "/api/v1/official-transcripts/{transcript_id}/issue", "/api/v1/official-transcripts/{transcript_id}/revoke")
    assert all(path in paths for path in expected)
    routes = [route.path for route in official_transcripts.router.routes]
    assert routes.index("/official-transcripts/by-reference/{transcript_reference}") < routes.index("/official-transcripts/{transcript_id}")
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    assert official_transcripts._map_error(service.InvalidOfficialTranscriptTransitionError()).status_code == 409
