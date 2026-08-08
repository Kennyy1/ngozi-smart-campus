from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.main import app
from app.models.academic_session import AcademicSession
from app.models.course_offering import CourseOffering
from app.models.examination import Examination
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.semester import Semester
from app.models.user import User
from app.schemas.examination import DeliveryMode, ExaminationCreate, ExaminationStatus, ExaminationType, ExaminationUpdate
from app.services import examination_service as service


class Results:
    def __init__(self, values: list[Examination]) -> None: self.values = values
    def all(self) -> list[Examination]: return self.values


class Session:
    def __init__(self, *results: object) -> None:
        self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.commits = 0; self.rollbacks = 0
    def scalar(self, statement: object) -> object:
        self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> Results:
        self.statements.append(statement); return Results(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def commit(self) -> None:
        self.commits += 1; now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None: value.id = uuid4()
            if getattr(value, "created_at", None) is None: value.created_at = now
            if getattr(value, "updated_at", None) is None: value.updated_at = now
    def rollback(self) -> None: self.rollbacks += 1
    def refresh(self, value: object) -> None: pass


def _parents(*, offering_status: str = "active", assignment_status: str = "active", employment_status: str = "active", user_active: bool = True) -> tuple[object, CourseOffering, LecturerAssignment]:
    institution_id = uuid4()
    academic_session = AcademicSession(id=uuid4(), institution_id=institution_id, name="2026/2027", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_current=True, status="active")
    semester = Semester(id=uuid4(), institution_id=institution_id, academic_session_id=academic_session.id, name="First", sequence_number=1, start_date=date(2026, 2, 1), end_date=date(2026, 6, 30), is_current=True, status="active")
    offering = CourseOffering(id=uuid4(), institution_id=institution_id, course_id=uuid4(), academic_session_id=academic_session.id, semester_id=semester.id, status=offering_status, registration_open=False)
    offering.academic_session = academic_session; offering.semester = semester
    user = User(id=uuid4(), institution_id=institution_id, email="lecturer@test.edu", password_hash="x", first_name="Ada", last_name="N", is_active=user_active, is_verified=True)
    lecturer = Lecturer(id=uuid4(), institution_id=institution_id, user_id=user.id, department_id=uuid4(), staff_number="L1", academic_rank="lecturer_i", employment_status=employment_status); lecturer.user = user
    assignment = LecturerAssignment(id=uuid4(), institution_id=institution_id, lecturer_id=lecturer.id, course_offering_id=offering.id, assignment_role="primary", is_primary=True, assigned_at=datetime.now(UTC), status=assignment_status); assignment.lecturer = lecturer
    return institution_id, offering, assignment


def _payload(offering: CourseOffering, assignment: LecturerAssignment, **changes: object) -> ExaminationCreate:
    values: dict[str, object] = {"course_offering_id": offering.id, "lecturer_assignment_id": assignment.id, "title": "  Final   Examination ", "examination_type": "written", "maximum_score": "100", "weight_percentage": "60", "exam_date": "2026-05-10", "start_time": "09:00", "end_time": "12:00", "venue": " Hall A ", "delivery_mode": "physical"}
    values.update(changes); return ExaminationCreate(**values)  # type: ignore[arg-type]


def _examination(institution_id: object, offering: CourseOffering, assignment: LecturerAssignment, **changes: object) -> Examination:
    now = datetime.now(UTC); values = dict(id=uuid4(), institution_id=institution_id, course_offering_id=offering.id, lecturer_assignment_id=assignment.id, title="Final Examination", examination_type="written", maximum_score=Decimal("100"), weight_percentage=Decimal("60"), exam_date=date(2026, 5, 10), start_time=time(9), end_time=time(12), venue="Hall A", delivery_mode="physical", status="draft", instructions=None, created_at=now, updated_at=now); values.update(changes)
    return Examination(**values)  # type: ignore[arg-type]


def test_schema_security_normalization_types_and_validation() -> None:
    _, offering, assignment = _parents(); payload = _payload(offering, assignment)
    assert payload.title == "Final Examination" and payload.venue == "Hall A" and payload.status == ExaminationStatus.DRAFT
    assert {item.value for item in ExaminationType} == {"written", "practical", "oral", "project_defense", "clinical", "other"}
    assert {item.value for item in DeliveryMode} == {"physical", "online", "hybrid"}
    assert {"institution_id", "lecturer_id", "course_id", "id", "created_at", "updated_at", "deleted_at"}.isdisjoint(ExaminationCreate.model_fields)
    for changes in ({"maximum_score": 0}, {"maximum_score": -1}, {"weight_percentage": 0}, {"weight_percentage": 101}, {"start_time": "09:00", "end_time": "09:00"}, {"start_time": "10:00", "end_time": "09:00"}, {"venue": "  "}, {"delivery_mode": "hybrid", "venue": None}):
        with pytest.raises(ValidationError): _payload(offering, assignment, **changes)
    assert _payload(offering, assignment, delivery_mode="online", venue=None).venue is None


@pytest.mark.parametrize("examination_type", list(ExaminationType))
def test_all_flexible_examination_types_are_accepted(examination_type: ExaminationType) -> None:
    _, offering, assignment = _parents(); assert _payload(offering, assignment, examination_type=examination_type).examination_type == examination_type


def test_creation_derives_institution_and_weight_boundaries() -> None:
    institution_id, offering, assignment = _parents()
    result = service.create_examination(Session(offering, assignment, None, Decimal("40")), institution_id=institution_id, examination_data=_payload(offering, assignment))  # type: ignore[arg-type]
    assert result.institution_id == institution_id and result.title == "Final Examination"
    with pytest.raises(service.ExaminationWeightConflictError): service.create_examination(Session(offering, assignment, None, Decimal("41")), institution_id=institution_id, examination_data=_payload(offering, assignment))  # type: ignore[arg-type]
    assert service.create_examination(Session(offering, assignment, None, Decimal("0")), institution_id=institution_id, examination_data=_payload(offering, assignment, weight_percentage="20"))


@pytest.mark.parametrize("status", ["cancelled", "postponed", "inactive"])
def test_non_active_statuses_are_excluded_from_weight(status: str) -> None:
    institution_id, offering, assignment = _parents(); session = Session(offering, assignment, None)
    assert service.create_examination(session, institution_id=institution_id, examination_data=_payload(offering, assignment, weight_percentage="100", status=status)).status == status  # type: ignore[arg-type]
    assert len(session.statements) == 3


@pytest.mark.parametrize(("changes", "error"), [({"offering_status": "inactive"}, service.ExaminationCourseOfferingUnavailableError), ({"assignment_status": "inactive"}, service.ExaminationLecturerAssignmentUnavailableError), ({"employment_status": "inactive"}, service.ExaminationLecturerUnavailableError), ({"user_active": False}, service.ExaminationLecturerUnavailableError)])
def test_inactive_parent_chain_rejected(changes: dict[str, object], error: type[Exception]) -> None:
    institution_id, offering, assignment = _parents(**changes)  # type: ignore[arg-type]
    with pytest.raises(error): service.create_examination(Session(offering, assignment), institution_id=institution_id, examination_data=_payload(offering, assignment))  # type: ignore[arg-type]


def test_missing_cross_institution_hierarchy_duplicate_and_dates_rejected() -> None:
    institution_id, offering, assignment = _parents()
    with pytest.raises(service.ExaminationCourseOfferingNotFoundError): service.create_examination(Session(), institution_id=institution_id, examination_data=_payload(offering, assignment))
    with pytest.raises(service.ExaminationLecturerAssignmentNotFoundError): service.create_examination(Session(offering), institution_id=institution_id, examination_data=_payload(offering, assignment))
    assignment.course_offering_id = uuid4()
    with pytest.raises(service.ExaminationHierarchyMismatchError): service.create_examination(Session(offering, assignment), institution_id=institution_id, examination_data=_payload(offering, assignment))
    assignment.course_offering_id = offering.id
    with pytest.raises(service.DuplicateExaminationError): service.create_examination(Session(offering, assignment, uuid4()), institution_id=institution_id, examination_data=_payload(offering, assignment, title=" final examination "))
    for exam_date in ("2026-01-31", "2026-07-01"):
        with pytest.raises(service.ExaminationDateRangeError): service.create_examination(Session(offering, assignment), institution_id=institution_id, examination_data=_payload(offering, assignment, exam_date=exam_date))


def test_list_retrieve_update_filters_and_soft_delete() -> None:
    institution_id, offering, assignment = _parents(); examination = _examination(institution_id, offering, assignment)
    listing = Session([examination]); assert service.list_examinations(listing, institution_id=institution_id, course_offering_id=offering.id, lecturer_assignment_id=assignment.id, examination_type=ExaminationType.WRITTEN, exam_date=date(2026, 5, 10), delivery_mode=DeliveryMode.PHYSICAL, status=ExaminationStatus.DRAFT) == [examination]  # type: ignore[arg-type]
    assert all(name in str(listing.statements[0]) for name in ("institution_id", "course_offering_id", "lecturer_assignment_id", "examination_type", "exam_date", "delivery_mode", "status"))
    updated = service.update_examination(Session(examination, offering, assignment, None, Decimal("50")), examination_id=examination.id, institution_id=institution_id, examination_data=ExaminationUpdate(title=" Practical ", examination_type="practical", maximum_score="50", weight_percentage="30", delivery_mode="online", venue=None))  # type: ignore[arg-type]
    assert updated.title == "Practical" and updated.venue is None and updated.examination_type == "practical"
    deletion = Session(examination); service.delete_examination(deletion, examination_id=examination.id, institution_id=institution_id)  # type: ignore[arg-type]
    assert examination.status == "inactive" and offering.status == "active" and assignment.status == "active"
    with pytest.raises(service.ExaminationNotFoundError): service.get_examination(Session(), examination_id=examination.id, institution_id=institution_id)  # type: ignore[arg-type]


def test_cross_institution_operations_router_registration_and_auth_security() -> None:
    for operation in (lambda: service.get_examination(Session(), examination_id=uuid4(), institution_id=uuid4()), lambda: service.update_examination(Session(), examination_id=uuid4(), institution_id=uuid4(), examination_data=ExaminationUpdate(instructions="x")), lambda: service.delete_examination(Session(), examination_id=uuid4(), institution_id=uuid4())):
        with pytest.raises(service.ExaminationNotFoundError): operation()
    paths = app.openapi()["paths"]
    assert "/api/v1/examinations" in paths and "/api/v1/examinations/{examination_id}" in paths
    assert paths["/api/v1/examinations"]["post"].get("security")
