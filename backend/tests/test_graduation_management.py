from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import dependencies
from app.api.v1.endpoints import graduations
from app.main import app
from app.models.graduation_record import GraduationRecord
from app.models.programme import Programme
from app.models.student import Student
from app.schemas.degree_classification import GraduationOutcomeEvaluation
from app.schemas.graduation_eligibility import GraduationEligibilityEvaluation
from app.schemas.graduation_record import (
    GraduationRecordConfirm, GraduationRecordCreate, GraduationRecordRevoke,
    GraduationRecordStatus, GraduationRecordUpdate,
)
from app.services import graduation_service as service
from app.services.academic_progression_policy import AcademicStanding
from app.services.degree_classification_policy import DegreeClassification, GraduationOutcome
from app.services.graduation_policy import GraduationEligibilityReason
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


def context():
    institution_id = uuid4(); programme_id = uuid4()
    student = Student(id=uuid4(), institution_id=institution_id, user_id=uuid4(), programme_id=programme_id, matriculation_number="NSC/1", admission_year=2022, current_level="Final Year", enrollment_status="active")
    programme = Programme(id=programme_id, institution_id=institution_id, faculty_id=uuid4(), department_id=uuid4(), name="Computer Science", code="CSC", award="BSc", duration_years=4, study_mode="FULL_TIME", status="active")
    return student, programme


def eligibility(student: Student, programme: Programme, *, eligible=True) -> GraduationEligibilityEvaluation:
    return GraduationEligibilityEvaluation(
        student_id=student.id, matriculation_number=student.matriculation_number, student_name="Ada Lovelace",
        programme_id=programme.id, programme_name=programme.name, programme_code=programme.code,
        current_academic_level_id=uuid4(), current_level="Final Year", current_level_sequence=4,
        final_academic_level_id=uuid4(), final_level="Final Year", final_level_sequence=4,
        cumulative_attempted_units=120, cumulative_earned_units=120, minimum_required_units=None,
        credit_requirement_configured=False, curriculum_completion_verified=False, cgpa=Decimal("4.50"),
        minimum_graduation_cgpa=Decimal("1.00"), academic_standing=AcademicStanding.GOOD_STANDING,
        total_published_courses=40, passed_course_count=40, outstanding_failed_course_count=0,
        outstanding_failed_credit_units=0, outstanding_courses=[], final_level_reached=True,
        meets_cgpa_requirement=True, meets_credit_requirement=None, has_published_results=True,
        eligible_for_graduation=eligible,
        eligibility_reasons=[GraduationEligibilityReason.ELIGIBLE if eligible else GraduationEligibilityReason.FINAL_LEVEL_NOT_REACHED],
    )


def outcome(student: Student, programme: Programme) -> GraduationOutcomeEvaluation:
    return GraduationOutcomeEvaluation(
        student_id=student.id, matriculation_number=student.matriculation_number, student_name="Ada Lovelace",
        programme_id=programme.id, programme_name=programme.name, programme_code=programme.code,
        current_level="Final Year", cgpa=Decimal("4.50"), academic_standing=AcademicStanding.GOOD_STANDING,
        eligible_for_graduation=True, graduation_eligibility_reasons=[GraduationEligibilityReason.ELIGIBLE],
        graduation_outcome=GraduationOutcome.ELIGIBLE_WITH_CLASSIFICATION,
        degree_classification=DegreeClassification.FIRST_CLASS, degree_classification_label="First Class Honours",
        classification_policy="default_5_point", outstanding_failed_course_count=0,
        cumulative_attempted_units=120, cumulative_earned_units=120, evaluated_at=datetime.now(UTC),
    )


def record(student: Student, programme: Programme, *, status="draft") -> GraduationRecord:
    now = datetime.now(UTC); e = eligibility(student, programme); o = outcome(student, programme)
    return GraduationRecord(
        id=uuid4(), institution_id=student.institution_id, student_id=student.id, programme_id=programme.id,
        graduation_reference="GRAD-2026-ABCDEF123456", status=status, award_title="BSc in Computer Science",
        degree_classification="first_class", degree_classification_label="First Class Honours",
        final_cgpa=Decimal("4.50"), academic_standing="good_standing",
        eligibility_snapshot=e.model_dump(mode="json"), outcome_snapshot=o.model_dump(mode="json"),
        prepared_at=now, prepared_by_user_id=uuid4(), created_at=now, updated_at=now,
    )


def patch_evaluations(monkeypatch, student, programme, *, eligible=True):
    calls = {"eligibility": 0, "outcome": 0}
    def get_eligibility(*args, **kwargs): calls["eligibility"] += 1; return eligibility(student, programme, eligible=eligible)
    def get_outcome(*args, **kwargs): calls["outcome"] += 1; return outcome(student, programme)
    monkeypatch.setattr(service, "evaluate_student_graduation_eligibility", get_eligibility)
    monkeypatch.setattr(service, "evaluate_student_degree_classification", get_outcome)
    return calls


def test_schemas_reject_server_fields_and_validate_actions():
    with pytest.raises(ValidationError): GraduationRecordCreate(student_id=uuid4(), graduation_reference="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError): GraduationRecordUpdate(final_cgpa="5.00")  # type: ignore[call-arg]
    with pytest.raises(ValidationError): GraduationRecordConfirm()
    assert GraduationRecordRevoke(reason="  administrative error ").reason == "administrative error"
    with pytest.raises(ValidationError): GraduationRecordRevoke(reason=" ")


def test_create_eligible_draft_derives_everything_and_commits_once(monkeypatch):
    student, programme = context(); calls = patch_evaluations(monkeypatch, student, programme)
    db = Session(student, programme, None, None)
    result = service.create_graduation_record(db, institution_id=student.institution_id, user_id=student.user_id, graduation_data=GraduationRecordCreate(student_id=student.id, remarks=" note "))  # type: ignore[arg-type]
    assert result.institution_id == student.institution_id and result.student_id == student.id and result.programme_id == programme.id
    assert result.status == "draft" and result.graduation_reference.startswith("GRAD-2026-") and result.award_title == "BSc in Computer Science"
    assert result.final_cgpa == Decimal("4.50") and result.degree_classification == "first_class" and result.academic_standing == "good_standing"
    assert result.eligibility_snapshot["eligible_for_graduation"] and result.outcome_snapshot["graduation_outcome"] == "eligible_with_classification"
    assert calls == {"eligibility": 1, "outcome": 1} and db.commits == 1 and db.added == [result]


def test_ineligible_and_duplicate_creation_are_rejected(monkeypatch):
    student, programme = context(); patch_evaluations(monkeypatch, student, programme, eligible=False)
    with pytest.raises(service.GraduationStudentIneligibleError):
        service.create_graduation_record(Session(student, programme, None), institution_id=student.institution_id, user_id=student.user_id, graduation_data=GraduationRecordCreate(student_id=student.id))  # type: ignore[arg-type]
    with pytest.raises(service.DuplicateGraduationRecordError):
        service.create_graduation_record(Session(student, programme, uuid4()), institution_id=student.institution_id, user_id=student.user_id, graduation_data=GraduationRecordCreate(student_id=student.id))  # type: ignore[arg-type]


def test_reference_collision_check_and_list_filters(monkeypatch):
    values = iter([type("U", (), {"hex": "a" * 32})(), type("U", (), {"hex": "b" * 32})()])
    monkeypatch.setattr(service, "uuid4", lambda: next(values))
    db = Session(uuid4(), None)
    assert service._generate_graduation_reference(db, now=datetime(2026, 1, 1, tzinfo=UTC)) == "GRAD-2026-BBBBBBBBBBBB"  # type: ignore[arg-type]
    db = Session([])
    service.list_graduation_records(db, institution_id=uuid4(), student_id=uuid4(), programme_id=uuid4(), status=GraduationRecordStatus.CONFIRMED, graduation_reference=" GRAD-X ", graduation_date=date(2026, 7, 1), degree_classification=" first_class ")  # type: ignore[arg-type]
    sql = str(db.statements[0]); params = tuple(db.statements[0].compile().params.values())
    assert all(name in sql for name in ("institution_id", "student_id", "programme_id", "status", "graduation_reference", "graduation_date", "degree_classification"))
    assert "confirmed" in params and "GRAD-X" in params and "first_class" in params


def test_lookup_scope_remarks_and_refresh_immutability(monkeypatch):
    student, programme = context(); item = record(student, programme); original_id = item.id; original_reference = item.graduation_reference
    assert service.get_graduation_record_by_reference(Session(item), institution_id=item.institution_id, graduation_reference=item.graduation_reference) is item  # type: ignore[arg-type]
    with pytest.raises(service.GraduationRecordNotFoundError): service.get_graduation_record(Session(), institution_id=uuid4(), graduation_id=item.id)  # type: ignore[arg-type]
    service.update_graduation_record(Session(item), institution_id=item.institution_id, graduation_id=item.id, graduation_data=GraduationRecordUpdate(remarks=" changed "))  # type: ignore[arg-type]
    assert item.remarks == "changed"
    calls = patch_evaluations(monkeypatch, student, programme)
    result = service.refresh_graduation_record(Session(item, programme), institution_id=item.institution_id, graduation_id=item.id, user_id=uuid4())  # type: ignore[arg-type]
    assert result.id == original_id and result.graduation_reference == original_reference and calls == {"eligibility": 1, "outcome": 1}
    item.status = "confirmed"
    with pytest.raises(service.InvalidGraduationTransitionError): service.refresh_graduation_record(Session(item), institution_id=item.institution_id, graduation_id=item.id, user_id=uuid4())  # type: ignore[arg-type]


def test_confirm_revalidates_atomically_and_revoke_restores_exact_state(monkeypatch):
    student, programme = context(); student.graduation_date = date(2020, 1, 1); item = record(student, programme); original_snapshot = dict(item.outcome_snapshot)
    calls = patch_evaluations(monkeypatch, student, programme); actor = uuid4()
    db = Session(item, student, programme)
    confirmed = service.confirm_graduation(db, institution_id=item.institution_id, graduation_id=item.id, user_id=actor, request=GraduationRecordConfirm(graduation_date=date(2026, 7, 1)))  # type: ignore[arg-type]
    assert confirmed.status == "confirmed" and confirmed.confirmed_at and confirmed.confirmed_by_user_id == actor
    assert confirmed.graduation_date == date(2026, 7, 1) and student.enrollment_status == "graduated" and student.graduation_date == date(2026, 7, 1)
    assert confirmed.previous_student_enrollment_status == "active" and confirmed.previous_student_graduation_date == date(2020, 1, 1)
    assert calls == {"eligibility": 1, "outcome": 1} and db.commits == 1
    snapshot_at_confirmation = dict(item.outcome_snapshot); actor2 = uuid4()
    revoked = service.revoke_graduation(Session(item, student), institution_id=item.institution_id, graduation_id=item.id, user_id=actor2, request=GraduationRecordRevoke(reason="Invalid award"))  # type: ignore[arg-type]
    assert revoked.status == "revoked" and revoked.revocation_reason == "Invalid award" and revoked.revoked_at and revoked.revoked_by_user_id == actor2
    assert student.enrollment_status == "active" and student.graduation_date == date(2020, 1, 1)
    assert revoked.outcome_snapshot == snapshot_at_confirmation
    assert original_snapshot["student_id"] == snapshot_at_confirmation["student_id"]


@pytest.mark.parametrize(("operation", "status"), [("confirm", "confirmed"), ("revoke", "draft"), ("revoke", "revoked")])
def test_invalid_transitions(operation, status):
    student, programme = context(); item = record(student, programme, status=status)
    with pytest.raises(service.InvalidGraduationTransitionError):
        if operation == "confirm": service.confirm_graduation(Session(item), institution_id=item.institution_id, graduation_id=item.id, user_id=uuid4(), request=GraduationRecordConfirm(graduation_date=date(2026, 1, 1)))  # type: ignore[arg-type]
        else: service.revoke_graduation(Session(item), institution_id=item.institution_id, graduation_id=item.id, user_id=uuid4(), request=GraduationRecordRevoke(reason="x"))  # type: ignore[arg-type]


def test_routes_static_order_authentication_and_error_mapping():
    paths = app.openapi()["paths"]
    expected = ("/api/v1/graduations", "/api/v1/graduations/by-reference/{graduation_reference}", "/api/v1/graduations/{graduation_id}", "/api/v1/graduations/{graduation_id}/refresh", "/api/v1/graduations/{graduation_id}/confirm", "/api/v1/graduations/{graduation_id}/revoke")
    assert all(path in paths for path in expected)
    routes = [route.path for route in graduations.router.routes]
    assert routes.index("/graduations/by-reference/{graduation_reference}") < routes.index("/graduations/{graduation_id}")
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    assert graduations._map_error(service.GraduationStudentIneligibleError()).status_code == 409
