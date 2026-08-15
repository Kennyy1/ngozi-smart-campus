from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import dependencies
from app.api.v1.endpoints import student_clearances
from app.main import app
from app.models.clearance_requirement import ClearanceRequirement
from app.models.student import Student
from app.models.student_clearance import StudentClearance
from app.models.user import User
from app.schemas.clearance import (
    ClearanceRequirementCreate, ClearanceRequirementUpdate, StudentClearanceActionRequest,
    StudentClearanceCreate, StudentClearanceUpdate,
)
from app.services import clearance_service as service
from app.services.graduation_policy import GraduationEligibilityReason


class Rows:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class Session:
    def __init__(self, *scalar_values, rows=()):
        self.scalar_values = list(scalar_values); self.row_values = list(rows)
        self.added = []; self.statements = []; self.commits = 0; self.rollbacks = 0
    def scalar(self, statement): self.statements.append(statement); return self.scalar_values.pop(0) if self.scalar_values else None
    def scalars(self, statement): self.statements.append(statement); return Rows(self.row_values.pop(0) if self.row_values else [])
    def add(self, value): self.added.append(value)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def refresh(self, value): return None


def context():
    institution_id = uuid4()
    user = User(id=uuid4(), institution_id=institution_id, email="student@example.edu", password_hash="x", first_name="Ada", last_name="Lovelace", is_active=True, is_verified=True)
    student = Student(id=uuid4(), institution_id=institution_id, user_id=user.id, matriculation_number="NSC/2026/1", admission_year=2022, enrollment_status="active")
    student.user = user
    requirement = ClearanceRequirement(id=uuid4(), institution_id=institution_id, name="Registry", code="REG", sequence_number=1, is_mandatory=True, status="active")
    return student, requirement


def clearance(student, requirement, *, status="pending"):
    now = datetime.now(UTC)
    return StudentClearance(id=uuid4(), institution_id=student.institution_id, student_id=student.id, clearance_requirement_id=requirement.id, status=status, created_at=now, updated_at=now)


def test_requirement_schemas_normalize_validate_and_reject_server_fields():
    item = ClearanceRequirementCreate(name="  Student   Affairs ", code=" sa ", sequence_number=1, is_mandatory=False)
    assert item.name == "Student Affairs" and item.code == "SA" and item.status == "active"
    with pytest.raises(ValidationError): ClearanceRequirementCreate(name="x", code="x", sequence_number=0, is_mandatory=True)
    with pytest.raises(ValidationError): ClearanceRequirementCreate(name="x", code="x", sequence_number=1, is_mandatory=True, institution_id=uuid4())  # type: ignore[call-arg]
    with pytest.raises(ValidationError): ClearanceRequirementUpdate(code=None)


def test_requirement_crud_is_scoped_filters_and_soft_deletes():
    student, requirement = context()
    db = Session(None)
    created = service.create_clearance_requirement(db, institution_id=student.institution_id, requirement_data=ClearanceRequirementCreate(name=" Library ", code=" lib ", sequence_number=2, is_mandatory=True))  # type: ignore[arg-type]
    assert created.institution_id == student.institution_id and created.code == "LIB" and db.commits == 1
    db = Session(rows=[[]])
    service.list_clearance_requirements(db, institution_id=student.institution_id, status=None, is_mandatory=True, code=" reg ")  # type: ignore[arg-type]
    sql = str(db.statements[0]); params = tuple(db.statements[0].compile().params.values())
    assert "institution_id" in sql and "is_mandatory" in sql and "REG" in params
    service.update_clearance_requirement(Session(requirement, None), institution_id=student.institution_id, requirement_id=requirement.id, requirement_data=ClearanceRequirementUpdate(name=" Registry Office "))  # type: ignore[arg-type]
    assert requirement.name == "Registry Office"
    service.delete_clearance_requirement(Session(requirement), institution_id=student.institution_id, requirement_id=requirement.id)  # type: ignore[arg-type]
    assert requirement.status == "inactive"


def test_requirement_duplicate_and_cross_institution_are_hidden():
    student, requirement = context()
    with pytest.raises(service.DuplicateClearanceRequirementCodeError):
        service.create_clearance_requirement(Session(requirement.id), institution_id=student.institution_id, requirement_data=ClearanceRequirementCreate(name="Other", code="REG", sequence_number=2, is_mandatory=True))  # type: ignore[arg-type]
    with pytest.raises(service.ClearanceRequirementNotFoundError):
        service.get_clearance_requirement(Session(None), institution_id=uuid4(), requirement_id=requirement.id)  # type: ignore[arg-type]


def test_student_clearance_create_defaults_pending_and_forbids_review_fields():
    student, requirement = context()
    data = StudentClearanceCreate(student_id=student.id, clearance_requirement_id=requirement.id, evidence_reference=" REF-42 ")
    db = Session(student, requirement, None)
    item = service.create_student_clearance(db, institution_id=student.institution_id, clearance_data=data)  # type: ignore[arg-type]
    assert item.status == "pending" and item.evidence_reference == "REF-42" and item.reviewed_by_user_id is None
    with pytest.raises(ValidationError): StudentClearanceCreate(student_id=student.id, clearance_requirement_id=requirement.id, reviewed_by_user_id=uuid4())  # type: ignore[call-arg]
    with pytest.raises(service.DuplicateStudentClearanceError):
        service.create_student_clearance(Session(student, requirement, uuid4()), institution_id=student.institution_id, clearance_data=data)  # type: ignore[arg-type]


def test_student_clearance_list_filters_get_update_and_scope():
    student, requirement = context(); item = clearance(student, requirement)
    db = Session(rows=[[]]); actor = uuid4()
    service.list_student_clearances(db, institution_id=student.institution_id, student_id=student.id, clearance_requirement_id=requirement.id, status=None, reviewed_by_user_id=actor)  # type: ignore[arg-type]
    sql = str(db.statements[0])
    assert all(field in sql for field in ("institution_id", "student_id", "clearance_requirement_id", "reviewed_by_user_id", "status"))
    assert service.get_student_clearance(Session(item), institution_id=student.institution_id, student_clearance_id=item.id) is item  # type: ignore[arg-type]
    service.update_student_clearance(Session(item), institution_id=student.institution_id, student_clearance_id=item.id, clearance_data=StudentClearanceUpdate(remarks=" note ", evidence_reference=" ref "))  # type: ignore[arg-type]
    assert item.remarks == "note" and item.evidence_reference == "ref"
    with pytest.raises(service.StudentClearanceNotFoundError): service.get_student_clearance(Session(None), institution_id=uuid4(), student_clearance_id=item.id)  # type: ignore[arg-type]


@pytest.mark.parametrize(("initial", "action", "target"), [
    ("pending", "clear", "cleared"), ("rejected", "clear", "cleared"),
    ("pending", "reject", "rejected"), ("cleared", "reject", "rejected"),
    ("pending", "waive", "waived"), ("rejected", "waive", "waived"),
])
def test_review_transitions_set_actor_and_timestamp(initial, action, target):
    student, requirement = context(); item = clearance(student, requirement, status=initial); actor = uuid4(); db = Session(item)
    if action == "clear": result = service.clear_student_clearance(db, institution_id=student.institution_id, student_clearance_id=item.id, user_id=actor)  # type: ignore[arg-type]
    elif action == "reject": result = service.reject_student_clearance(db, institution_id=student.institution_id, student_clearance_id=item.id, user_id=actor, request=StudentClearanceActionRequest(reason=" not satisfied "))  # type: ignore[arg-type]
    else: result = service.waive_student_clearance(db, institution_id=student.institution_id, student_clearance_id=item.id, user_id=actor, request=StudentClearanceActionRequest(reason=" approved exception "))  # type: ignore[arg-type]
    assert result.status == target and result.reviewed_at is not None and result.reviewed_by_user_id == actor
    if action != "clear": assert result.remarks


def test_invalid_transitions_reasons_and_resets():
    student, requirement = context(); item = clearance(student, requirement, status="cleared")
    with pytest.raises(service.InvalidStudentClearanceTransitionError): service.clear_student_clearance(Session(item), institution_id=student.institution_id, student_clearance_id=item.id, user_id=uuid4())  # type: ignore[arg-type]
    with pytest.raises(ValidationError): StudentClearanceActionRequest(reason=" ")
    for state in ("cleared", "rejected", "waived"):
        item.status = state; item.reviewed_at = datetime.now(UTC); item.reviewed_by_user_id = uuid4(); item.remarks = "preserved"
        service.reset_student_clearance(Session(item), institution_id=student.institution_id, student_clearance_id=item.id)  # type: ignore[arg-type]
        assert item.status == "pending" and item.reviewed_at is None and item.reviewed_by_user_id is None and item.remarks == "preserved"


def test_summary_is_read_only_counts_and_mandatory_optional_logic():
    student, mandatory = context()
    optional = ClearanceRequirement(id=uuid4(), institution_id=student.institution_id, name="Alumni", code="ALU", sequence_number=2, is_mandatory=False, status="active")
    optional_clearance = clearance(student, optional, status="pending")
    db = Session(student, rows=[[mandatory, optional], [optional_clearance]])
    summary = service.compute_student_clearance_summary(db, institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert summary.total_active_requirements == 2 and summary.mandatory_requirements == 1 and summary.optional_requirements == 1
    assert summary.missing_count == 1 and summary.pending_count == 1 and not summary.is_fully_cleared
    assert summary.requirements[0].status == "missing" and db.added == [] and db.commits == 0
    for status in ("cleared", "waived"):
        mandatory_clearance = clearance(student, mandatory, status=status)
        summary = service.compute_student_clearance_summary(Session(student, rows=[[mandatory, optional], [mandatory_clearance, optional_clearance]]), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
        assert summary.is_fully_cleared


def test_inactive_requirements_are_excluded_by_summary_query():
    student, _ = context(); db = Session(student, rows=[[], []])
    summary = service.compute_student_clearance_summary(db, institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert summary.total_active_requirements == 0 and summary.is_fully_cleared
    assert "clearance_requirements.status" in str(db.statements[1])


def test_graduation_clearance_reuses_9r1_and_reports_blockers(monkeypatch):
    student, requirement = context()
    calls = []
    academic = type("Academic", (), {"eligible_for_graduation": False, "eligibility_reasons": [GraduationEligibilityReason.FINAL_LEVEL_NOT_REACHED]})()
    monkeypatch.setattr(service, "evaluate_student_graduation_eligibility", lambda *args, **kwargs: calls.append(kwargs) or academic)
    summary = service.compute_student_clearance_summary(Session(student, rows=[[requirement], []]), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "compute_student_clearance_summary", lambda *args, **kwargs: summary)
    result = service.evaluate_graduation_clearance(Session(), institution_id=student.institution_id, student_id=student.id)  # type: ignore[arg-type]
    assert len(calls) == 1 and not result.ready_for_final_graduation_processing
    assert result.clearance_blockers == ["academic_ineligibility", "missing_mandatory_clearance"]


def test_routes_authentication_order_and_scope_contract():
    paths = app.openapi()["paths"]
    expected = (
        "/api/v1/clearance-requirements", "/api/v1/student-clearances",
        "/api/v1/student-clearances/{student_clearance_id}/clear",
        "/api/v1/student-clearances/{student_clearance_id}/reject",
        "/api/v1/student-clearances/{student_clearance_id}/waive",
        "/api/v1/student-clearances/{student_clearance_id}/reset",
        "/api/v1/students/{student_id}/clearance-summary",
        "/api/v1/students/{student_id}/graduation-clearance",
    )
    assert all(path in paths for path in expected)
    routes = [route.path for route in student_clearances.router.routes]
    assert routes.index("/student-clearances/{student_clearance_id}") < routes.index("/student-clearances/{student_clearance_id}/clear")
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401


def test_migration_and_scope_exclusions_are_phase_specific():
    backend = Path(__file__).resolve().parents[1]
    migration = (backend / "alembic/versions/b7e3c9a1d524_create_clearance_management.py").read_text()
    assert 'revision: str = "b7e3c9a1d524"' in migration and 'down_revision: str | Sequence[str] | None = "a9c4e7f2b816"' in migration
    source = (backend / "app/services/clearance_service.py").read_text().lower()
    for excluded in ("payment transaction", "inventory", "library circulation", "hostel management", "notification", "disciplinary case"):
        assert excluded not in source
