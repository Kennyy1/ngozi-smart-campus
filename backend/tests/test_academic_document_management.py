from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import dependencies
from app.api.v1.endpoints import academic_documents
from app.main import app
from app.models.academic_document import AcademicDocument
from app.models.graduation_record import GraduationRecord
from app.models.programme import Programme
from app.models.student import Student
from app.models.user import User
from app.schemas.academic_document import (
    AcademicDocumentCreate, AcademicDocumentRevoke, AcademicDocumentStatus,
    AcademicDocumentType, AcademicDocumentUpdate,
)
from app.services import academic_document_service as service
from tests.test_academic_performance import Session as ReadSession


class Rows:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class Session(ReadSession):
    def add(self, value): self.added.append(value)
    def commit(self): self.commits += 1
    def refresh(self, value): return None
    def rollback(self): return None
    def scalars(self, statement): self.statements.append(statement); return Rows(self.values.pop(0) if self.values else [])


def document(*, status="draft", document_type="certificate") -> AcademicDocument:
    now = datetime.now(UTC)
    return AcademicDocument(
        id=uuid4(), institution_id=uuid4(), student_id=uuid4(), programme_id=uuid4(),
        graduation_record_id=uuid4() if document_type == "certificate" else None,
        official_transcript_id=None, document_type=document_type,
        document_reference="CERT-2026-ABCDEF123456" if document_type == "certificate" else "SOR-2026-ABCDEF123456",
        verification_code="A" * 32, status=status, title="Certificate",
        snapshot_data={"student_name": "Ada Lovelace", "programme_name": "Computer Science", "award_title": "BSc in Computer Science", "degree_classification_label": "First Class", "graduation_date": "2026-07-01"},
        generated_at=now, generated_by_user_id=uuid4(), created_at=now, updated_at=now,
    )


def test_create_and_update_schemas_reject_server_managed_fields() -> None:
    with pytest.raises(ValidationError): AcademicDocumentCreate(student_id=uuid4(), document_type="certificate", graduation_record_id=uuid4(), document_reference="bad")  # type: ignore[call-arg]
    with pytest.raises(ValidationError): AcademicDocumentUpdate(snapshot_data={})  # type: ignore[call-arg]
    with pytest.raises(ValidationError): AcademicDocumentCreate(student_id=uuid4(), document_type="certificate")
    with pytest.raises(ValidationError): AcademicDocumentRevoke(reason="   ")
    assert AcademicDocumentRevoke(reason=" superseded ").reason == "superseded"


def test_reference_and_verification_formats_are_collision_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = type("U", (), {"hex": "a" * 32})()
    monkeypatch.setattr(service, "uuid4", lambda: fake)
    assert service._generate_reference(Session(None), prefix="CERT", now=datetime(2026, 1, 1, tzinfo=UTC)) == "CERT-2026-AAAAAAAAAAAA"  # type: ignore[arg-type]
    monkeypatch.setattr(service, "token_hex", lambda _: "b" * 32)
    assert service._generate_verification_code(Session(None)) == "B" * 32  # type: ignore[arg-type]


def test_certificate_snapshot_is_authoritative_and_excludes_raw_scores() -> None:
    institution_id = uuid4(); programme_id = uuid4(); now = datetime.now(UTC)
    user = User(id=uuid4(), institution_id=institution_id, email="ada@example.test", password_hash="secret", first_name="Ada", last_name="Lovelace", is_active=True, is_verified=True, created_at=now, updated_at=now)
    student = Student(id=uuid4(), institution_id=institution_id, user_id=user.id, programme_id=programme_id, matriculation_number="NSC/1", admission_year=2022, enrollment_status="graduated", created_at=now, updated_at=now); student.user = user
    programme = Programme(id=programme_id, institution_id=institution_id, faculty_id=uuid4(), department_id=uuid4(), name="Computer Science", code="CSC", award="BSc", duration_years=4, study_mode="FULL_TIME", status="active", created_at=now, updated_at=now)
    graduation = GraduationRecord(id=uuid4(), institution_id=institution_id, student_id=student.id, programme_id=programme_id, graduation_reference="GRAD-2026-X", status="confirmed", graduation_date=date(2026, 7, 1), award_title="BSc in Computer Science", degree_classification="first_class", degree_classification_label="First Class", final_cgpa=Decimal("4.80"), academic_standing="good_standing", eligibility_snapshot={"eligible": True}, outcome_snapshot={"classification": "first_class"}, prepared_at=now, prepared_by_user_id=user.id, confirmed_at=now, confirmed_by_user_id=user.id, created_at=now, updated_at=now)
    data = service._build_certificate_snapshot(Session("Ngozi University"), institution_id=institution_id, student=student, programme=programme, graduation=graduation)  # type: ignore[arg-type]
    assert data["student_name"] == "Ada Lovelace" and data["final_cgpa"] == "4.80" and data["graduation_reference"] == "GRAD-2026-X"
    assert "password" not in str(data).lower() and "assessment_score" not in str(data).lower() and "examination_score" not in str(data).lower()


def test_list_is_institution_scoped_and_supports_required_filters() -> None:
    db = Session([])
    service.list_academic_documents(db, institution_id=uuid4(), student_id=uuid4(), programme_id=uuid4(), document_type=AcademicDocumentType.CERTIFICATE, status=AcademicDocumentStatus.ISSUED, document_reference=" CERT-X ", graduation_record_id=uuid4())  # type: ignore[arg-type]
    sql = str(db.statements[0]); params = tuple(db.statements[0].compile().params.values())
    assert all(field in sql for field in ("institution_id", "student_id", "programme_id", "document_type", "status", "document_reference", "graduation_record_id"))
    assert "CERT-X" in params


def test_remarks_only_update_and_lifecycle_preserve_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    item = document(); original = dict(item.snapshot_data)
    result = service.update_academic_document(Session(item), institution_id=item.institution_id, document_id=item.id, document_data=AcademicDocumentUpdate(remarks=" note "))  # type: ignore[arg-type]
    assert result.remarks == "note" and result.snapshot_data == original
    student = object()
    db = Session(item, student)
    monkeypatch.setattr(service, "_resolve_student", lambda *_, **__: student)
    monkeypatch.setattr(service, "_resolve_graduation", lambda *_, **__: object())
    monkeypatch.setattr(service, "_validate_certificate_source", lambda *_, **__: None)
    issued = service.issue_academic_document(db, institution_id=item.institution_id, document_id=item.id, user_id=uuid4())  # type: ignore[arg-type]
    assert issued.status == "issued" and issued.issued_at and issued.snapshot_data == original
    revoked = service.revoke_academic_document(Session(item), institution_id=item.institution_id, document_id=item.id, user_id=uuid4(), request=AcademicDocumentRevoke(reason="Superseded"))  # type: ignore[arg-type]
    assert revoked.status == "revoked" and revoked.revocation_reason == "Superseded" and revoked.snapshot_data == original


def test_public_verification_is_minimal_and_draft_is_hidden() -> None:
    item = document(status="issued")
    result = service.verify_public_academic_document(Session(item), verification_code=item.verification_code)  # type: ignore[arg-type]
    payload = result.model_dump(mode="json")
    assert payload["valid"] is True and payload["student_name"] == "Ada Lovelace"
    assert not ({"student_id", "programme_id", "snapshot_data", "revocation_reason", "remarks"} & payload.keys())
    with pytest.raises(service.AcademicDocumentNotFoundError): service.verify_public_academic_document(Session(), verification_code="unknown")  # type: ignore[arg-type]


def test_routes_static_order_admin_auth_and_public_access_contract() -> None:
    paths = app.openapi()["paths"]
    expected = ("/api/v1/academic-documents", "/api/v1/academic-documents/by-reference/{document_reference}", "/api/v1/academic-documents/by-verification-code/{verification_code}", "/api/v1/academic-documents/{document_id}", "/api/v1/academic-documents/{document_id}/refresh", "/api/v1/academic-documents/{document_id}/issue", "/api/v1/academic-documents/{document_id}/revoke", "/api/v1/public/academic-document-verification/{verification_code}")
    assert all(path in paths for path in expected)
    routes = [route.path for route in academic_documents.router.routes]
    assert routes.index("/academic-documents/by-reference/{document_reference}") < routes.index("/academic-documents/{document_id}")
    assert routes.index("/academic-documents/by-verification-code/{verification_code}") < routes.index("/academic-documents/{document_id}")
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    public_route = next(route for route in academic_documents.public_router.routes if "verification" in route.path)
    assert not any(getattr(dependency.call, "__name__", "") == "dependency" for dependency in public_route.dependant.dependencies)
