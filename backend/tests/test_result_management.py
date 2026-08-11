from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.main import app
from app.models.course_registration import CourseRegistration
from app.models.result import Result
from app.schemas.result import ResultCreate, ResultRejectRequest, ResultUpdate
from app.schemas.result_computation import ComputedCourseResult
from app.services import result_service as service


class Values:
    def __init__(self, values: list[object]) -> None: self.values = values
    def all(self) -> list[object]: return self.values


class Session:
    def __init__(self, *values: object) -> None:
        self.values = list(values); self.added: list[object] = []; self.commits = 0; self.rollbacks = 0; self.statements: list[object] = []
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.values.pop(0) if self.values else None
    def scalars(self, statement: object) -> Values:
        self.statements.append(statement); return Values(self.values.pop(0) if self.values else [])  # type: ignore[arg-type]
    def add(self, item: object) -> None: self.added.append(item)
    def commit(self) -> None:
        self.commits += 1
        for item in self.added:
            if getattr(item, "id", None) is None: item.id = uuid4()
            if getattr(item, "created_at", None) is None: item.created_at = datetime.now(UTC)
            if getattr(item, "updated_at", None) is None: item.updated_at = datetime.now(UTC)
    def refresh(self, _: object) -> None: pass
    def rollback(self) -> None: self.rollbacks += 1


def registration() -> CourseRegistration:
    now = datetime.now(UTC)
    return CourseRegistration(id=uuid4(), institution_id=uuid4(), student_id=uuid4(), course_offering_id=uuid4(), registration_status="registered", registered_at=now, status="active", created_at=now, updated_at=now)


def computed(enrolled: CourseRegistration, *, complete: bool = True, score: str = "75") -> ComputedCourseResult:
    value = Decimal(score)
    return ComputedCourseResult(course_registration_id=enrolled.id, student_id=enrolled.student_id, course_offering_id=enrolled.course_offering_id, assessment_weight_total=Decimal("40"), examination_weight_total=Decimal("60"), configured_weight_total=Decimal("100"), continuous_assessment_score=Decimal("30"), examination_score=value - Decimal("30"), final_score=value, is_complete=complete, grade_letter="A" if complete else None, grade_point=Decimal("5") if complete else None, passed=True if complete else None, contributions=[], missing_components=[])


def official(enrolled: CourseRegistration, *, status: str = "draft") -> Result:
    now = datetime.now(UTC)
    return Result(id=uuid4(), institution_id=enrolled.institution_id, course_registration_id=enrolled.id, course_offering_id=enrolled.course_offering_id, student_id=enrolled.student_id, continuous_assessment_score=Decimal("30"), examination_score=Decimal("45"), final_score=Decimal("75"), grade_letter="A", grade_point=Decimal("5"), passed=True, status=status, computed_at=now, computed_by_user_id=uuid4(), created_at=now, updated_at=now)


def test_creation_derives_and_snapshots_complete_computation(monkeypatch: pytest.MonkeyPatch) -> None:
    enrolled = registration(); actor = uuid4(); snapshot = computed(enrolled)
    monkeypatch.setattr(service, "compute_course_registration_result", lambda *_, **__: snapshot)
    db = Session(enrolled, None)
    result = service.create_result(db, institution_id=enrolled.institution_id, computed_by_user_id=actor, result_data=ResultCreate(course_registration_id=enrolled.id, remarks=" official "))  # type: ignore[arg-type]
    assert (result.institution_id, result.student_id, result.course_offering_id) == (enrolled.institution_id, enrolled.student_id, enrolled.course_offering_id)
    assert (result.continuous_assessment_score, result.examination_score, result.final_score, result.grade_letter, result.grade_point, result.passed) == (Decimal("30"), Decimal("45"), Decimal("75"), "A", Decimal("5"), True)
    assert result.status == "draft" and result.computed_by_user_id == actor and result.remarks == "official" and db.commits == 1


def test_incomplete_and_duplicate_creation_rejected_without_write(monkeypatch: pytest.MonkeyPatch) -> None:
    enrolled = registration(); monkeypatch.setattr(service, "compute_course_registration_result", lambda *_, **__: computed(enrolled, complete=False))
    db = Session(enrolled, None)
    with pytest.raises(service.IncompleteResultComputationError): service.create_result(db, institution_id=enrolled.institution_id, computed_by_user_id=uuid4(), result_data=ResultCreate(course_registration_id=enrolled.id))  # type: ignore[arg-type]
    assert not db.added and db.commits == 0
    with pytest.raises(service.DuplicateResultError): service.create_result(Session(enrolled, uuid4()), institution_id=enrolled.institution_id, computed_by_user_id=uuid4(), result_data=ResultCreate(course_registration_id=enrolled.id))  # type: ignore[arg-type]


def test_refresh_replaces_snapshot_but_preserves_id(monkeypatch: pytest.MonkeyPatch) -> None:
    enrolled = registration(); result = official(enrolled); original_id = result.id; actor = uuid4()
    monkeypatch.setattr(service, "compute_course_registration_result", lambda *_, **__: computed(enrolled, score="60"))
    refreshed = service.refresh_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, computed_by_user_id=actor)  # type: ignore[arg-type]
    assert refreshed.id == original_id and refreshed.final_score == Decimal("60") and refreshed.computed_by_user_id == actor


@pytest.mark.parametrize("status", ["submitted", "approved", "published", "withheld"])
def test_non_draft_result_cannot_refresh_or_patch(status: str) -> None:
    enrolled = registration(); result = official(enrolled, status=status)
    with pytest.raises(service.ResultImmutableError): service.refresh_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, computed_by_user_id=uuid4())  # type: ignore[arg-type]
    with pytest.raises(service.ResultImmutableError): service.update_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, result_data=ResultUpdate(remarks="x"))  # type: ignore[arg-type]


def test_full_supported_workflow_and_actor_timestamps() -> None:
    enrolled = registration(); result = official(enrolled); actor = uuid4()
    assert service.submit_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=actor).submitted_at is not None  # type: ignore[arg-type]
    assert service.approve_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=actor).approved_by_user_id == actor  # type: ignore[arg-type]
    assert service.publish_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=actor).published_at is not None  # type: ignore[arg-type]
    assert service.withhold_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=actor).status == "withheld"  # type: ignore[arg-type]
    assert service.publish_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=actor).status == "published"  # type: ignore[arg-type]


def test_reject_and_return_to_draft_without_recomputation() -> None:
    enrolled = registration(); result = official(enrolled, status="submitted"); original = result.final_score
    rejected = service.reject_result(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=uuid4(), request=ResultRejectRequest(reason=" Verify score "))  # type: ignore[arg-type]
    assert rejected.status == "rejected" and rejected.remarks == "Verify score"
    returned = service.return_result_to_draft(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=uuid4())  # type: ignore[arg-type]
    assert returned.status == "draft" and returned.final_score == original


@pytest.mark.parametrize(("operation", "status"), [(service.approve_result, "draft"), (service.publish_result, "submitted"), (service.withhold_result, "draft"), (service.submit_result, "approved")])
def test_invalid_transitions_rejected(operation: object, status: str) -> None:
    enrolled = registration(); result = official(enrolled, status=status)
    with pytest.raises(service.InvalidResultTransitionError): operation(Session(result), institution_id=enrolled.institution_id, result_id=result.id, user_id=uuid4())  # type: ignore[operator,arg-type]


def test_schemas_forbid_client_control_and_rejection_reason_is_required() -> None:
    enrolled = registration()
    with pytest.raises(ValidationError): ResultCreate(course_registration_id=enrolled.id, final_score=90)  # type: ignore[call-arg]
    with pytest.raises(ValidationError): ResultUpdate(status="published")  # type: ignore[call-arg]
    with pytest.raises(ValidationError): ResultRejectRequest(reason="   ")
    assert not ({"gpa", "cgpa", "transcript"} & set(Result.__table__.columns))


def test_routes_registered_with_actions_before_identifier_route() -> None:
    paths = app.openapi()["paths"]
    expected = {"/api/v1/results", "/api/v1/results/{result_id}", "/api/v1/results/{result_id}/refresh", "/api/v1/results/{result_id}/submit", "/api/v1/results/{result_id}/approve", "/api/v1/results/{result_id}/reject", "/api/v1/results/{result_id}/return-to-draft", "/api/v1/results/{result_id}/publish", "/api/v1/results/{result_id}/withhold"}
    assert expected.issubset(paths)
