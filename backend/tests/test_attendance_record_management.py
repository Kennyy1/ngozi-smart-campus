from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Index
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import attendance_records
from app.main import app
from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.course_registration import CourseRegistration
from app.models.institution import Institution
from app.models.user import User
from app.schemas.attendance_record import (
    AttendanceBulkCreate,
    AttendanceRecordCreate,
    AttendanceRecordStatus,
    AttendanceRecordUpdate,
    AttendanceStatus,
)
from app.services import attendance_record_service as service
from app.services.authentication import AuthenticatedUserContext


class Result:
    def __init__(self, values: list[AttendanceRecord]) -> None: self.values = values
    def all(self) -> list[AttendanceRecord]: return self.values


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


def parents(ctx: AuthenticatedUserContext, *, session_status: str = "scheduled", registration_status: str = "registered", record_status: str = "active", offering_match: bool = True, future: bool = False) -> tuple[ClassSession, CourseRegistration]:
    offering_id = uuid4(); now = datetime.now(UTC)
    class_session = ClassSession(id=uuid4(), institution_id=ctx.institution.id, course_offering_id=offering_id, lecturer_assignment_id=uuid4(), session_date=date.today() + timedelta(days=1 if future else -1), start_time=time(9), end_time=time(10), session_type="lecture", topic="Topic", venue="A1", delivery_mode="physical", status=session_status, created_at=now, updated_at=now)
    registration = CourseRegistration(id=uuid4(), institution_id=ctx.institution.id, student_id=uuid4(), course_offering_id=offering_id if offering_match else uuid4(), registration_status=registration_status, registered_at=now, dropped_at=now if registration_status == "dropped" else None, notes=None, status=record_status, created_at=now, updated_at=now)
    return class_session, registration


def record(ctx: AuthenticatedUserContext, class_session: ClassSession, registration: CourseRegistration, *, attendance_status: str = "present", check_in_time: datetime | None = None, status: str = "active") -> AttendanceRecord:
    now = datetime.now(UTC)
    return AttendanceRecord(id=uuid4(), institution_id=ctx.institution.id, class_session_id=class_session.id, course_registration_id=registration.id, attendance_status=attendance_status, check_in_time=check_in_time, recorded_by_user_id=ctx.user.id, remarks=None, status=status, created_at=now, updated_at=now)


def create(ctx: AuthenticatedUserContext, class_session: ClassSession, registration: CourseRegistration, **changes: object) -> tuple[AttendanceRecord, Session]:
    values: dict[str, object] = {"class_session_id": class_session.id, "course_registration_id": registration.id, "attendance_status": "present"}; values.update(changes)
    session = Session(class_session, registration, None)
    result = service.create_attendance_record(session, institution_id=ctx.institution.id, recorded_by_user_id=ctx.user.id, attendance_data=AttendanceRecordCreate(**values))  # type: ignore[arg-type]
    return result, session


def test_model_schema_security_and_partial_uniqueness() -> None:
    indexes = {item.name: item for item in AttendanceRecord.__table__.indexes if isinstance(item, Index)}
    assert indexes["uq_attendance_records_active_session_registration"].unique
    assert set(AttendanceRecordCreate.model_fields) == {"class_session_id", "course_registration_id", "attendance_status", "check_in_time", "remarks"}
    assert set(AttendanceRecordUpdate.model_fields) == {"attendance_status", "check_in_time", "remarks"}
    assert "student_id" not in AttendanceRecord.__table__.columns


def test_successful_creation_derives_context_values_and_trims_remarks() -> None:
    ctx = context(); class_session, registration = parents(ctx)
    result, db = create(ctx, class_session, registration, remarks=" Recorded manually ")
    assert result.institution_id == ctx.institution.id and result.recorded_by_user_id == ctx.user.id
    assert result.remarks == "Recorded manually" and db.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], service.AttendanceClassSessionNotFoundError), (["session"], service.AttendanceCourseRegistrationNotFoundError)])
def test_missing_and_cross_institution_parents_return_not_found(results: list[object], error: type[Exception]) -> None:
    ctx = context(); class_session, registration = parents(ctx); mapping = {"session": class_session}
    with pytest.raises(error):
        service.create_attendance_record(Session(*(mapping[x] for x in results)), institution_id=ctx.institution.id, recorded_by_user_id=ctx.user.id, attendance_data=AttendanceRecordCreate(class_session_id=class_session.id, course_registration_id=registration.id, attendance_status="present"))  # type: ignore[arg-type]


def test_offering_mismatch_and_duplicate_rejected() -> None:
    ctx = context(); class_session, registration = parents(ctx, offering_match=False)
    with pytest.raises(service.AttendanceOfferingMismatchError): create(ctx, class_session, registration)
    registration.course_offering_id = class_session.course_offering_id
    with pytest.raises(service.DuplicateAttendanceRecordError):
        service.create_attendance_record(Session(class_session, registration, uuid4()), institution_id=ctx.institution.id, recorded_by_user_id=ctx.user.id, attendance_data=AttendanceRecordCreate(class_session_id=class_session.id, course_registration_id=registration.id, attendance_status="present"))  # type: ignore[arg-type]


@pytest.mark.parametrize(("registration_status", "record_status"), [("dropped", "active"), ("registered", "inactive")])
def test_dropped_and_inactive_registrations_rejected(registration_status: str, record_status: str) -> None:
    ctx = context(); class_session, registration = parents(ctx, registration_status=registration_status, record_status=record_status)
    with pytest.raises(service.AttendanceRegistrationUnavailableError): create(ctx, class_session, registration)


@pytest.mark.parametrize("session_status", ["cancelled", "postponed", "inactive"])
def test_unavailable_sessions_rejected(session_status: str) -> None:
    ctx = context(); class_session, registration = parents(ctx, session_status=session_status)
    with pytest.raises(service.AttendanceSessionUnavailableError): create(ctx, class_session, registration)


def test_scheduled_future_session_is_explicitly_accepted() -> None:
    ctx = context(); class_session, registration = parents(ctx, future=True)
    result, _ = create(ctx, class_session, registration)
    assert result.class_session_id == class_session.id


@pytest.mark.parametrize(("attendance_status", "check_in", "valid"), [
    ("present", None, True), ("present", datetime.now(UTC), True), ("late", None, False),
    ("late", datetime.now(UTC), True), ("absent", datetime.now(UTC), False),
    ("excused", datetime.now(UTC), False), ("absent", None, True), ("excused", None, True),
])
def test_attendance_check_in_validation(attendance_status: str, check_in: datetime | None, valid: bool) -> None:
    kwargs = {"class_session_id": uuid4(), "course_registration_id": uuid4(), "attendance_status": attendance_status, "check_in_time": check_in}
    if valid: assert AttendanceRecordCreate(**kwargs).attendance_status.value == attendance_status  # type: ignore[arg-type]
    else:
        with pytest.raises(ValidationError): AttendanceRecordCreate(**kwargs)  # type: ignore[arg-type]


def test_blank_remarks_invalid_status_and_bad_time_rejected() -> None:
    base = {"class_session_id": uuid4(), "course_registration_id": uuid4(), "attendance_status": "present"}
    for changes in ({"remarks": " "}, {"attendance_status": "unknown"}, {"check_in_time": "not-a-time"}):
        with pytest.raises(ValidationError): AttendanceRecordCreate(**(base | changes))  # type: ignore[arg-type]


def test_bulk_success_is_atomic_and_derives_context() -> None:
    ctx = context(); class_session, first = parents(ctx); _, second = parents(ctx); second.course_offering_id = class_session.course_offering_id
    payload = AttendanceBulkCreate(class_session_id=class_session.id, records=[{"course_registration_id": first.id, "attendance_status": "present"}, {"course_registration_id": second.id, "attendance_status": "late", "check_in_time": datetime.now(UTC)}])
    db = Session(class_session, first, None, second, None)
    records = service.create_attendance_records_bulk(db, institution_id=ctx.institution.id, recorded_by_user_id=ctx.user.id, attendance_data=payload)  # type: ignore[arg-type]
    assert len(records) == 2 and db.commits == 1 and all(item.recorded_by_user_id == ctx.user.id for item in records)


def test_bulk_empty_and_duplicate_payloads_rejected() -> None:
    registration_id = uuid4()
    with pytest.raises(ValidationError): AttendanceBulkCreate(class_session_id=uuid4(), records=[])
    with pytest.raises(ValidationError): AttendanceBulkCreate(class_session_id=uuid4(), records=[{"course_registration_id": registration_id, "attendance_status": "present"}, {"course_registration_id": registration_id, "attendance_status": "absent"}])


def test_invalid_or_existing_bulk_item_adds_nothing_and_does_not_commit() -> None:
    ctx = context(); class_session, first = parents(ctx); _, second = parents(ctx); second.course_offering_id = class_session.course_offering_id
    payload = AttendanceBulkCreate(class_session_id=class_session.id, records=[{"course_registration_id": first.id, "attendance_status": "present"}, {"course_registration_id": second.id, "attendance_status": "absent"}])
    db = Session(class_session, first, None, second, uuid4())
    with pytest.raises(service.DuplicateAttendanceRecordError): service.create_attendance_records_bulk(db, institution_id=ctx.institution.id, recorded_by_user_id=ctx.user.id, attendance_data=payload)  # type: ignore[arg-type]
    assert db.added == [] and db.commits == 0


def test_list_is_institution_scoped_and_supports_all_filters() -> None:
    ctx = context(); class_session, registration = parents(ctx); expected = [record(ctx, class_session, registration)]; db = Session(expected)
    assert service.list_attendance_records(db, institution_id=ctx.institution.id, class_session_id=class_session.id, course_registration_id=registration.id, attendance_status=AttendanceStatus.PRESENT, recorded_by_user_id=ctx.user.id, status=AttendanceRecordStatus.ACTIVE) == expected  # type: ignore[arg-type]
    sql = str(db.statements[0]); assert all(name in sql for name in ("institution_id", "class_session_id", "course_registration_id", "attendance_status", "recorded_by_user_id", "status"))


def test_retrieve_update_final_state_and_parent_immutability() -> None:
    ctx = context(); class_session, registration = parents(ctx); item = record(ctx, class_session, registration); original = (item.class_session_id, item.course_registration_id, item.recorded_by_user_id)
    updated = service.update_attendance_record(Session(item), attendance_record_id=item.id, institution_id=ctx.institution.id, attendance_data=AttendanceRecordUpdate(attendance_status="late", check_in_time=datetime.now(UTC), remarks=" Arrived late "))  # type: ignore[arg-type]
    assert updated.attendance_status == "late" and updated.remarks == "Arrived late" and (updated.class_session_id, updated.course_registration_id, updated.recorded_by_user_id) == original
    with pytest.raises(ValidationError): AttendanceRecordUpdate(class_session_id=uuid4())  # type: ignore[call-arg]
    with pytest.raises(service.InvalidAttendanceStateError): service.update_attendance_record(Session(updated), attendance_record_id=updated.id, institution_id=ctx.institution.id, attendance_data=AttendanceRecordUpdate(attendance_status="absent"))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_cross_institution_record_operations_return_not_found(operation: str) -> None:
    kwargs = {"attendance_record_id": uuid4(), "institution_id": uuid4()}
    with pytest.raises(service.AttendanceRecordNotFoundError):
        if operation == "get": service.get_attendance_record(Session(), **kwargs)  # type: ignore[arg-type]
        elif operation == "update": service.update_attendance_record(Session(), attendance_data=AttendanceRecordUpdate(remarks="Hidden"), **kwargs)  # type: ignore[arg-type]
        else: service.delete_attendance_record(Session(), **kwargs)  # type: ignore[arg-type]


def test_delete_soft_deactivates_and_hides_record() -> None:
    ctx = context(); class_session, registration = parents(ctx); item = record(ctx, class_session, registration); db = Session(item)
    service.delete_attendance_record(db, attendance_record_id=item.id, institution_id=ctx.institution.id)  # type: ignore[arg-type]
    assert item.status == "inactive" and db.commits == 1
    with pytest.raises(service.AttendanceRecordNotFoundError): service.get_attendance_record(Session(), attendance_record_id=item.id, institution_id=ctx.institution.id)  # type: ignore[arg-type]


def test_unauthenticated_routes_static_order_and_safe_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as raised: dependencies.get_current_user(None, Session())  # type: ignore[arg-type]
    assert raised.value.status_code == 401
    paths = app.openapi()["paths"]
    assert "/api/v1/attendance-records/bulk" in paths and "/api/v1/attendance-records/{attendance_record_id}" in paths
    route_paths = [route.path for route in attendance_records.router.routes]; assert route_paths.index("/attendance-records/bulk") < route_paths.index("/attendance-records/{attendance_record_id}")
    monkeypatch.setattr(attendance_records, "create_attendance_record", lambda *_, **__: (_ for _ in ()).throw(service.AttendanceOfferingMismatchError()))
    ctx = context()
    with pytest.raises(HTTPException) as mapped: attendance_records.create_endpoint(AttendanceRecordCreate(class_session_id=uuid4(), course_registration_id=uuid4(), attendance_status="present"), Session(), ctx)  # type: ignore[arg-type]
    assert mapped.value.status_code == 409


def test_integrity_error_rolls_back() -> None:
    class FailingSession(Session):
        def commit(self) -> None: raise IntegrityError("insert", {}, Exception("constraint"))
    ctx = context(); class_session, registration = parents(ctx); db = FailingSession(class_session, registration, None)
    with pytest.raises(service.DuplicateAttendanceRecordError): service.create_attendance_record(db, institution_id=ctx.institution.id, recorded_by_user_id=ctx.user.id, attendance_data=AttendanceRecordCreate(class_session_id=class_session.id, course_registration_id=registration.id, attendance_status="present"))  # type: ignore[arg-type]
    assert db.rollbacks == 1
