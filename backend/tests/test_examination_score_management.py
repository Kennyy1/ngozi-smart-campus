from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Index
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import examination_scores
from app.main import app
from app.models.examination import Examination
from app.models.examination_score import ExaminationScore
from app.models.course_registration import CourseRegistration
from app.models.institution import Institution
from app.models.user import User
from app.schemas.examination_score import (
    ExaminationScoreBulkCreate,
    ExaminationScoreCreate,
    ExaminationScoreStatus,
    ExaminationScoreUpdate,
)
from app.services import examination_score_service as service
from app.services.authentication import AuthenticatedUserContext


class Result:
    def __init__(self, values: list[ExaminationScore]) -> None: self.values = values
    def all(self) -> list[ExaminationScore]: return self.values


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


def parents(ctx: AuthenticatedUserContext, *, examination_status: str = "completed", registration_status: str = "registered", record_status: str = "active", offering_match: bool = True) -> tuple[Examination, CourseRegistration]:
    offering_id = uuid4(); now = datetime.now(UTC)
    examination = Examination(id=uuid4(), institution_id=ctx.institution.id, course_offering_id=offering_id, lecturer_assignment_id=uuid4(), title="Final Examination", examination_type="written", maximum_score=Decimal("20.00"), weight_percentage=Decimal("10.00"), exam_date=date(2026, 5, 1), start_time=time(9), end_time=time(11), venue="Hall A", delivery_mode="physical", status=examination_status, created_at=now, updated_at=now)
    registration = CourseRegistration(id=uuid4(), institution_id=ctx.institution.id, student_id=uuid4(), course_offering_id=offering_id if offering_match else uuid4(), registration_status=registration_status, registered_at=now, status=record_status, created_at=now, updated_at=now)
    return examination, registration


def score(ctx: AuthenticatedUserContext, examination: Examination, registration: CourseRegistration, *, value: str = "10.00", status: str = "active") -> ExaminationScore:
    now = datetime.now(UTC)
    return ExaminationScore(id=uuid4(), institution_id=ctx.institution.id, examination_id=examination.id, course_registration_id=registration.id, score=Decimal(value), graded_by_user_id=ctx.user.id, graded_at=now, remarks=None, status=status, created_at=now, updated_at=now)


def create(ctx: AuthenticatedUserContext, examination: Examination, registration: CourseRegistration, **changes: object) -> tuple[ExaminationScore, Session]:
    values: dict[str, object] = {"examination_id": examination.id, "course_registration_id": registration.id, "score": "10.00"}; values.update(changes)
    db = Session(examination, registration, None)
    result = service.create_examination_score(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=ExaminationScoreCreate(**values))  # type: ignore[arg-type]
    return result, db


def test_model_schema_security_and_partial_uniqueness() -> None:
    indexes = {item.name: item for item in ExaminationScore.__table__.indexes if isinstance(item, Index)}
    assert indexes["uq_examination_scores_active_examination_registration"].unique
    assert set(ExaminationScoreCreate.model_fields) == {"examination_id", "course_registration_id", "score", "remarks"}
    assert set(ExaminationScoreUpdate.model_fields) == {"score", "remarks"}
    assert "student_id" not in ExaminationScore.__table__.columns


def test_successful_creation_derives_context_and_accepts_boundaries() -> None:
    ctx = context(); examination, registration = parents(ctx)
    result, db = create(ctx, examination, registration, score="0", remarks=" Good ")
    assert result.institution_id == ctx.institution.id and result.graded_by_user_id == ctx.user.id
    assert result.score == 0 and result.remarks == "Good" and db.commits == 1
    result, _ = create(ctx, examination, registration, score="20.00")
    assert result.score == examination.maximum_score


@pytest.mark.parametrize(("results", "error"), [([], service.ScoreExaminationNotFoundError), (["examination"], service.ExaminationScoreCourseRegistrationNotFoundError)])
def test_missing_and_cross_institution_parents_rejected(results: list[object], error: type[Exception]) -> None:
    ctx = context(); examination, registration = parents(ctx); mapping = {"examination": examination}
    with pytest.raises(error):
        service.create_examination_score(Session(*(mapping[x] for x in results)), institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=ExaminationScoreCreate(examination_id=examination.id, course_registration_id=registration.id, score="10"))  # type: ignore[arg-type]


@pytest.mark.parametrize("examination_status", ["draft", "scheduled", "cancelled", "postponed", "inactive"])
def test_only_completed_examination_accepts_new_scores(examination_status: str) -> None:
    ctx = context(); examination, registration = parents(ctx, examination_status=examination_status)
    with pytest.raises(service.ExaminationUnavailableForGradingError): create(ctx, examination, registration)


@pytest.mark.parametrize(("registration_status", "record_status"), [("dropped", "active"), ("registered", "inactive")])
def test_dropped_and_inactive_registrations_rejected(registration_status: str, record_status: str) -> None:
    ctx = context(); examination, registration = parents(ctx, registration_status=registration_status, record_status=record_status)
    with pytest.raises(service.ExaminationScoreCourseRegistrationUnavailableError): create(ctx, examination, registration)


def test_offering_mismatch_duplicate_and_range_rejected() -> None:
    ctx = context(); examination, registration = parents(ctx, offering_match=False)
    with pytest.raises(service.ExaminationScoreOfferingMismatchError): create(ctx, examination, registration)
    registration.course_offering_id = examination.course_offering_id
    with pytest.raises(service.DuplicateExaminationScoreError):
        service.create_examination_score(Session(examination, registration, uuid4()), institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=ExaminationScoreCreate(examination_id=examination.id, course_registration_id=registration.id, score="10"))  # type: ignore[arg-type]
    with pytest.raises(service.InvalidExaminationScoreError): create(ctx, examination, registration, score="20.01")
    with pytest.raises(ValidationError): ExaminationScoreCreate(examination_id=examination.id, course_registration_id=registration.id, score="-0.01")


def test_bulk_success_validation_and_atomic_failures() -> None:
    ctx = context(); examination, first = parents(ctx); _, second = parents(ctx); second.course_offering_id = examination.course_offering_id
    payload = ExaminationScoreBulkCreate(examination_id=examination.id, scores=[{"course_registration_id": first.id, "score": "8"}, {"course_registration_id": second.id, "score": "12"}])
    db = Session(examination, first, None, second, None)
    created = service.create_examination_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=payload)  # type: ignore[arg-type]
    assert len(created) == 2 and db.commits == 1 and all(item.graded_by_user_id == ctx.user.id for item in created)
    with pytest.raises(ValidationError): ExaminationScoreBulkCreate(examination_id=examination.id, scores=[])
    with pytest.raises(ValidationError): ExaminationScoreBulkCreate(examination_id=examination.id, scores=[{"course_registration_id": first.id, "score": 1}, {"course_registration_id": first.id, "score": 2}])
    bad = ExaminationScoreBulkCreate(examination_id=examination.id, scores=[{"course_registration_id": first.id, "score": 8}, {"course_registration_id": second.id, "score": 21}])
    db = Session(examination, first, None, second)
    with pytest.raises(service.InvalidExaminationScoreError): service.create_examination_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=bad)  # type: ignore[arg-type]
    assert db.added == [] and db.commits == 0


def test_bulk_hierarchy_registration_and_existing_score_failures_are_atomic() -> None:
    ctx = context(); examination, registration = parents(ctx, offering_match=False)
    payload = ExaminationScoreBulkCreate(examination_id=examination.id, scores=[{"course_registration_id": registration.id, "score": 8}])
    db = Session(examination, registration)
    with pytest.raises(service.ExaminationScoreOfferingMismatchError):
        service.create_examination_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=payload)  # type: ignore[arg-type]
    assert db.added == [] and db.commits == 0 and db.rollbacks == 1

    examination, registration = parents(ctx, registration_status="dropped")
    payload = ExaminationScoreBulkCreate(examination_id=examination.id, scores=[{"course_registration_id": registration.id, "score": 8}])
    db = Session(examination, registration)
    with pytest.raises(service.ExaminationScoreCourseRegistrationUnavailableError):
        service.create_examination_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=payload)  # type: ignore[arg-type]
    assert db.added == [] and db.commits == 0 and db.rollbacks == 1

    examination, registration = parents(ctx)
    payload = ExaminationScoreBulkCreate(examination_id=examination.id, scores=[{"course_registration_id": registration.id, "score": 8}])
    db = Session(examination, registration, uuid4())
    with pytest.raises(service.DuplicateExaminationScoreError):
        service.create_examination_scores_bulk(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=payload)  # type: ignore[arg-type]
    assert db.added == [] and db.commits == 0 and db.rollbacks == 1


def test_list_filters_retrieve_update_immutability_and_preserve_graded_at() -> None:
    ctx = context(); examination, registration = parents(ctx); item = score(ctx, examination, registration); db = Session([item])
    assert service.list_examination_scores(db, institution_id=ctx.institution.id, examination_id=examination.id, course_registration_id=registration.id, graded_by_user_id=ctx.user.id, status=ExaminationScoreStatus.ACTIVE) == [item]  # type: ignore[arg-type]
    sql = str(db.statements[0]); assert all(name in sql for name in ("institution_id", "examination_id", "course_registration_id", "graded_by_user_id", "status"))
    original = (item.examination_id, item.course_registration_id, item.graded_at)
    updated = service.update_examination_score(Session(item, examination), examination_score_id=item.id, institution_id=ctx.institution.id, examination_score_data=ExaminationScoreUpdate(score="15", remarks=" Revised "))  # type: ignore[arg-type]
    assert updated.score == 15 and updated.remarks == "Revised" and (updated.examination_id, updated.course_registration_id, updated.graded_at) == original
    with pytest.raises(ValidationError): ExaminationScoreUpdate(examination_id=uuid4())  # type: ignore[call-arg]
    with pytest.raises(service.InvalidExaminationScoreError): service.update_examination_score(Session(item, examination), examination_score_id=item.id, institution_id=ctx.institution.id, examination_score_data=ExaminationScoreUpdate(score="21"))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_operations_return_not_found(operation: str) -> None:
    kwargs = {"examination_score_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(service.ExaminationScoreNotFoundError):
        if operation == "get": service.get_examination_score(Session(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": service.update_examination_score(Session(), examination_score_data=ExaminationScoreUpdate(remarks="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: service.delete_examination_score(Session(), **kwargs)  # type: ignore[arg-type]


def test_delete_hides_score_and_does_not_touch_parents() -> None:
    ctx = context(); examination, registration = parents(ctx); item = score(ctx, examination, registration); db = Session(item)
    service.delete_examination_score(db, examination_score_id=item.id, institution_id=ctx.institution.id)  # type: ignore[arg-type]
    assert item.status == "inactive" and examination.status == "completed" and registration.status == "active"
    with pytest.raises(service.ExaminationScoreNotFoundError): service.get_examination_score(Session(), examination_score_id=item.id, institution_id=ctx.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_route_order_and_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    paths = app.openapi()["paths"]
    assert "/api/v1/examination-scores/bulk" in paths and "/api/v1/examination-scores/{examination_score_id}" in paths
    route_paths = [route.path for route in examination_scores.router.routes]
    assert route_paths.index("/examination-scores/bulk") < route_paths.index("/examination-scores/{examination_score_id}")
    monkeypatch.setattr(examination_scores, "create_examination_score", lambda *_, **__: (_ for _ in ()).throw(service.ExaminationScoreOfferingMismatchError()))
    ctx = context()
    with pytest.raises(HTTPException) as mapped: examination_scores.create_endpoint(ExaminationScoreCreate(examination_id=uuid4(), course_registration_id=uuid4(), score=1), Session(), ctx)  # type: ignore[arg-type]
    assert mapped.value.status_code == 409


def test_integrity_error_rolls_back() -> None:
    class FailingSession(Session):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    ctx = context(); examination, registration = parents(ctx); db = FailingSession(examination, registration, None)
    with pytest.raises(service.DuplicateExaminationScoreError): create_service(db, ctx, examination, registration)
    assert db.rollbacks == 1


def create_service(db: Session, ctx: AuthenticatedUserContext, examination: Examination, registration: CourseRegistration) -> ExaminationScore:
    return service.create_examination_score(db, institution_id=ctx.institution.id, graded_by_user_id=ctx.user.id, examination_score_data=ExaminationScoreCreate(examination_id=examination.id, course_registration_id=registration.id, score=1))  # type: ignore[arg-type]
