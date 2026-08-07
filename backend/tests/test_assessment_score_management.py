from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Index
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import assessment_scores
from app.main import app
from app.models.assessment_component import AssessmentComponent
from app.models.assessment_score import AssessmentScore
from app.models.course_registration import CourseRegistration
from app.models.institution import Institution
from app.models.user import User
from app.schemas.assessment_score import (
    AssessmentScoreBulkCreate,
    AssessmentScoreCreate,
    AssessmentScoreStatus,
    AssessmentScoreUpdate,
)
from app.services import assessment_score_service as service
from app.services.authentication import AuthenticatedUserContext


class Result:
    def __init__(self, values: list[AssessmentScore]) -> None: self.values = values
    def all(self) -> list[AssessmentScore]: return self.values


class Session:
    def __init__(self, *results: object) -> None:
        self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.commits = 0; self.rollbacks = 0
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> Result:
        self.statements.append(statement); return Result(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def add_all(self, values: list[object]) -> None: self.added.extend(values)
    def commit(self) -> None:
        self.commits += 1; now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None: value.id = uuid4()
            if getattr(value, "created_at", None) is None: value.created_at = now
            if getattr(value, "updated_at", None) is None: value.updated_at = now
    def refresh(self, _: object) -> None: pass
    def rollback(self) -> None: self.rollbacks += 1


def context() -> AuthenticatedUserContext:
    institution = Institution(id=uuid4(), name="Test University", code=f"T-{uuid4()}", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email=f"{uuid4()}@test.edu", password_hash="x", first_name="Admin", last_name="User", is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=("administrator",))


def parents(ctx: AuthenticatedUserContext, *, component_status: str = "published", registration_status: str = "registered", record_status: str = "active", offering_match: bool = True) -> tuple[AssessmentComponent, CourseRegistration]:
    offering_id = uuid4(); now = datetime.now(UTC)
    component = AssessmentComponent(id=uuid4(), institution_id=ctx.institution.id, course_offering_id=offering_id, lecturer_assignment_id=uuid4(), title="Quiz 1", assessment_type="quiz", maximum_score=Decimal("20.00"), weight_percentage=Decimal("10.00"), status=component_status, created_at=now, updated_at=now)
    registration = CourseRegistration(id=uuid4(), institution_id=ctx.institution.id, student_id=uuid4(), course_offering_id=offering_id if offering_match else uuid4(), registration_status=registration_status, registered_at=now, status=record_status, created_at=now, updated_at=now)
    return component, registration


def score(ctx: AuthenticatedUserContext, component: AssessmentComponent, registration: CourseRegistration, *, value: str = "10.00", status: str = "active") -> AssessmentScore:
    now = datetime.now(UTC)
    return AssessmentScore(id=uuid4(), institution_id=ctx.institution.id, assessment_component_id=component.id, course_registration_id=registration.id, score=Decimal(value), graded_by_user_id=ctx.user.id, graded_at=now, remarks=None, status=status, created_at=now, updated_at=now)


def create(ctx: AuthenticatedUserContext, component: AssessmentComponent, registration: CourseRegistration, **changes: object) -> tuple[AssessmentScore, Session]:
    values: dict[str, object] = {"assessment_component_id": component.id, "course_registration_id": registration.id, "score": "10.00"}; values.update(changes)
    db = Session(component, registration, None)
    result = service.create_assessment_score(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, assessment_score_data=AssessmentScoreCreate(**values))  # type: ignore[arg-type]
    return result, db


def test_model_schema_security_and_partial_uniqueness() -> None:
    indexes = {item.name: item for item in AssessmentScore.__table__.indexes if isinstance(item, Index)}
    assert indexes["uq_assessment_scores_active_component_registration"].unique
    assert set(AssessmentScoreCreate.model_fields) == {"assessment_component_id", "course_registration_id", "score", "remarks"}
    assert set(AssessmentScoreUpdate.model_fields) == {"score", "remarks"}
    assert "student_id" not in AssessmentScore.__table__.columns


def test_successful_creation_derives_context_and_accepts_boundaries() -> None:
    ctx = context(); component, registration = parents(ctx)
    result, db = create(ctx, component, registration, score="0", remarks=" Good ")
    assert result.institution_id == ctx.institution.id and result.graded_by_user_id == ctx.user.id
    assert result.score == 0 and result.remarks == "Good" and db.commits == 1
    result, _ = create(ctx, component, registration, score="20.00")
    assert result.score == component.maximum_score


@pytest.mark.parametrize(("results", "error"), [([], service.ScoreAssessmentComponentNotFoundError), (["component"], service.ScoreCourseRegistrationNotFoundError)])
def test_missing_and_cross_institution_parents_rejected(results: list[object], error: type[Exception]) -> None:
    ctx = context(); component, registration = parents(ctx); mapping = {"component": component}
    with pytest.raises(error):
        service.create_assessment_score(Session(*(mapping[x] for x in results)), institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, assessment_score_data=AssessmentScoreCreate(assessment_component_id=component.id, course_registration_id=registration.id, score="10"))  # type: ignore[arg-type]


@pytest.mark.parametrize("component_status", ["draft", "closed", "cancelled", "inactive"])
def test_only_published_component_accepts_new_scores(component_status: str) -> None:
    ctx = context(); component, registration = parents(ctx, component_status=component_status)
    with pytest.raises(service.AssessmentComponentUnavailableForGradingError): create(ctx, component, registration)


@pytest.mark.parametrize(("registration_status", "record_status"), [("dropped", "active"), ("registered", "inactive")])
def test_dropped_and_inactive_registrations_rejected(registration_status: str, record_status: str) -> None:
    ctx = context(); component, registration = parents(ctx, registration_status=registration_status, record_status=record_status)
    with pytest.raises(service.ScoreCourseRegistrationUnavailableError): create(ctx, component, registration)


def test_offering_mismatch_duplicate_and_range_rejected() -> None:
    ctx = context(); component, registration = parents(ctx, offering_match=False)
    with pytest.raises(service.AssessmentScoreOfferingMismatchError): create(ctx, component, registration)
    registration.course_offering_id = component.course_offering_id
    with pytest.raises(service.DuplicateAssessmentScoreError):
        service.create_assessment_score(Session(component, registration, uuid4()), institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, assessment_score_data=AssessmentScoreCreate(assessment_component_id=component.id, course_registration_id=registration.id, score="10"))  # type: ignore[arg-type]
    with pytest.raises(service.InvalidAssessmentScoreError): create(ctx, component, registration, score="20.01")
    with pytest.raises(ValidationError): AssessmentScoreCreate(assessment_component_id=component.id, course_registration_id=registration.id, score="-0.01")


def test_bulk_success_validation_and_atomic_failures() -> None:
    ctx = context(); component, first = parents(ctx); _, second = parents(ctx); second.course_offering_id = component.course_offering_id
    payload = AssessmentScoreBulkCreate(assessment_component_id=component.id, scores=[{"course_registration_id": first.id, "score": "8"}, {"course_registration_id": second.id, "score": "12"}])
    db = Session(component, first, None, second, None)
    created = service.create_assessment_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, assessment_score_data=payload)  # type: ignore[arg-type]
    assert len(created) == 2 and db.commits == 1 and all(item.graded_by_user_id == ctx.user.id for item in created)
    with pytest.raises(ValidationError): AssessmentScoreBulkCreate(assessment_component_id=component.id, scores=[])
    with pytest.raises(ValidationError): AssessmentScoreBulkCreate(assessment_component_id=component.id, scores=[{"course_registration_id": first.id, "score": 1}, {"course_registration_id": first.id, "score": 2}])
    bad = AssessmentScoreBulkCreate(assessment_component_id=component.id, scores=[{"course_registration_id": first.id, "score": 8}, {"course_registration_id": second.id, "score": 21}])
    db = Session(component, first, None, second)
    with pytest.raises(service.InvalidAssessmentScoreError): service.create_assessment_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, assessment_score_data=bad)  # type: ignore[arg-type]
    assert db.added == [] and db.commits == 0


def test_list_filters_retrieve_update_immutability_and_preserve_graded_at() -> None:
    ctx = context(); component, registration = parents(ctx); item = score(ctx, component, registration); db = Session([item])
    assert service.list_assessment_scores(db, institution_id=ctx.institution.id, assessment_component_id=component.id, course_registration_id=registration.id, graded_by_user_id=ctx.user.id, status=AssessmentScoreStatus.ACTIVE) == [item]  # type: ignore[arg-type]
    sql = str(db.statements[0]); assert all(name in sql for name in ("institution_id", "assessment_component_id", "course_registration_id", "graded_by_user_id", "status"))
    original = (item.assessment_component_id, item.course_registration_id, item.graded_at)
    updated = service.update_assessment_score(Session(item, component), assessment_score_id=item.id, institution_id=ctx.institution.id, assessment_score_data=AssessmentScoreUpdate(score="15", remarks=" Revised "))  # type: ignore[arg-type]
    assert updated.score == 15 and updated.remarks == "Revised" and (updated.assessment_component_id, updated.course_registration_id, updated.graded_at) == original
    with pytest.raises(ValidationError): AssessmentScoreUpdate(assessment_component_id=uuid4())  # type: ignore[call-arg]
    with pytest.raises(service.InvalidAssessmentScoreError): service.update_assessment_score(Session(item, component), assessment_score_id=item.id, institution_id=ctx.institution.id, assessment_score_data=AssessmentScoreUpdate(score="21"))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"assessment_score_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(service.AssessmentScoreNotFoundError):
        if operation == "get": service.get_assessment_score(Session(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": service.update_assessment_score(Session(), assessment_score_data=AssessmentScoreUpdate(remarks="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: service.delete_assessment_score(Session(), **kwargs)  # type: ignore[arg-type]


def test_delete_hides_score_and_does_not_touch_parents() -> None:
    ctx = context(); component, registration = parents(ctx); item = score(ctx, component, registration); db = Session(item)
    service.delete_assessment_score(db, assessment_score_id=item.id, institution_id=ctx.institution.id)  # type: ignore[arg-type]
    assert item.status == "inactive" and component.status == "published" and registration.status == "active"
    with pytest.raises(service.AssessmentScoreNotFoundError): service.get_assessment_score(Session(), assessment_score_id=item.id, institution_id=ctx.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_route_order_and_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    paths = app.openapi()["paths"]
    assert "/api/v1/assessment-scores/bulk" in paths and "/api/v1/assessment-scores/{assessment_score_id}" in paths
    route_paths = [route.path for route in assessment_scores.router.routes]
    assert route_paths.index("/assessment-scores/bulk") < route_paths.index("/assessment-scores/{assessment_score_id}")
    monkeypatch.setattr(assessment_scores, "create_assessment_score", lambda *_, **__: (_ for _ in ()).throw(service.AssessmentScoreOfferingMismatchError()))
    ctx = context()
    with pytest.raises(HTTPException) as mapped: assessment_scores.create_endpoint(AssessmentScoreCreate(assessment_component_id=uuid4(), course_registration_id=uuid4(), score=1), Session(), ctx)  # type: ignore[arg-type]
    assert mapped.value.status_code == 409


def test_integrity_error_rolls_back() -> None:
    class FailingSession(Session):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    ctx = context(); component, registration = parents(ctx); db = FailingSession(component, registration, None)
    with pytest.raises(service.DuplicateAssessmentScoreError): create_service(db, ctx, component, registration)
    assert db.rollbacks == 1


def create_service(db: Session, ctx: AuthenticatedUserContext, component: AssessmentComponent, registration: CourseRegistration) -> AssessmentScore:
    return service.create_assessment_score(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, assessment_score_data=AssessmentScoreCreate(assessment_component_id=component.id, course_registration_id=registration.id, score=1))  # type: ignore[arg-type]
