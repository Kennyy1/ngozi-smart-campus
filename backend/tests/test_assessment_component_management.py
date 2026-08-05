from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.main import app
from app.models.academic_session import AcademicSession
from app.models.assessment_component import AssessmentComponent
from app.models.course_offering import CourseOffering
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.semester import Semester
from app.models.user import User
from app.schemas.assessment_component import AssessmentComponentCreate, AssessmentComponentStatus, AssessmentComponentUpdate, AssessmentType
from app.services import assessment_component_service as service


class Results:
    def __init__(self, values: list[AssessmentComponent]) -> None: self.values = values
    def all(self) -> list[AssessmentComponent]: return self.values


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
    lecturer = Lecturer(id=uuid4(), institution_id=institution_id, user_id=user.id, department_id=uuid4(), staff_number="L1", academic_rank="lecturer_i", employment_status=employment_status)
    lecturer.user = user
    assignment = LecturerAssignment(id=uuid4(), institution_id=institution_id, lecturer_id=lecturer.id, course_offering_id=offering.id, assignment_role="primary", is_primary=True, assigned_at=datetime.now(UTC), status=assignment_status)
    assignment.lecturer = lecturer
    return institution_id, offering, assignment


def _payload(offering: CourseOffering, assignment: LecturerAssignment, **changes: object) -> AssessmentComponentCreate:
    values: dict[str, object] = {"course_offering_id": offering.id, "lecturer_assignment_id": assignment.id, "title": "  Assignment   1  ", "assessment_type": "assignment", "maximum_score": "20.00", "weight_percentage": "15.00", "scheduled_date": "2026-03-01", "due_at": "2026-03-10T12:00:00Z"}
    values.update(changes)
    return AssessmentComponentCreate(**values)  # type: ignore[arg-type]


def _component(institution_id: object, offering: CourseOffering, assignment: LecturerAssignment, **changes: object) -> AssessmentComponent:
    now = datetime.now(UTC)
    values = dict(id=uuid4(), institution_id=institution_id, course_offering_id=offering.id, lecturer_assignment_id=assignment.id, title="Assignment 1", assessment_type="assignment", maximum_score=Decimal("20"), weight_percentage=Decimal("15"), scheduled_date=date(2026, 3, 1), due_at=datetime(2026, 3, 10, tzinfo=UTC), status="draft", description=None, created_at=now, updated_at=now)
    values.update(changes)
    return AssessmentComponent(**values)  # type: ignore[arg-type]


def test_schema_security_normalization_types_and_bounds() -> None:
    institution_id, offering, assignment = _parents()
    payload = _payload(offering, assignment)
    assert payload.title == "Assignment 1" and payload.status == AssessmentComponentStatus.DRAFT
    assert {"institution_id", "lecturer_id", "course_id", "id", "created_at", "updated_at", "deleted_at"}.isdisjoint(AssessmentComponentCreate.model_fields)
    assert {item.value for item in AssessmentType} == {"attendance", "quiz", "assignment", "test", "project", "presentation", "laboratory", "practical", "mid_semester", "other"}
    for changes in ({"maximum_score": 0}, {"maximum_score": -1}, {"weight_percentage": 0}, {"weight_percentage": 101}, {"title": "   "}, {"scheduled_date": "2026-04-02", "due_at": "2026-04-01T00:00:00Z"}):
        with pytest.raises(ValidationError): _payload(offering, assignment, **changes)
    assert institution_id is not None


def test_creation_derives_institution_and_allows_totals_below_or_equal_100() -> None:
    institution_id, offering, assignment = _parents()
    session = Session(offering, assignment, None, Decimal("80"))
    result = service.create_assessment_component(session, institution_id=institution_id, assessment_component_data=_payload(offering, assignment, weight_percentage="20"))  # type: ignore[arg-type]
    assert result.institution_id == institution_id and result.title == "Assignment 1" and session.commits == 1
    session = Session(offering, assignment, None, Decimal("0"))
    assert service.create_assessment_component(session, institution_id=institution_id, assessment_component_data=_payload(offering, assignment, weight_percentage="40"))  # type: ignore[arg-type]


def test_active_total_above_100_rejected_but_cancelled_and_inactive_are_excluded() -> None:
    institution_id, offering, assignment = _parents()
    with pytest.raises(service.AssessmentWeightConflictError):
        service.create_assessment_component(Session(offering, assignment, None, Decimal("90")), institution_id=institution_id, assessment_component_data=_payload(offering, assignment, weight_percentage="11"))  # type: ignore[arg-type]
    for status in ("cancelled", "inactive"):
        session = Session(offering, assignment, None)
        result = service.create_assessment_component(session, institution_id=institution_id, assessment_component_data=_payload(offering, assignment, weight_percentage="100", status=status))  # type: ignore[arg-type]
        assert result.status == status and len(session.statements) == 3


@pytest.mark.parametrize(("result_index", "error"), [(0, service.AssessmentCourseOfferingNotFoundError), (1, service.AssessmentLecturerAssignmentNotFoundError)])
def test_missing_and_cross_institution_references_are_not_found(result_index: int, error: type[Exception]) -> None:
    institution_id, offering, assignment = _parents()
    results: list[object] = [] if result_index == 0 else [offering]
    with pytest.raises(error): service.create_assessment_component(Session(*results), institution_id=institution_id, assessment_component_data=_payload(offering, assignment))  # type: ignore[arg-type]


@pytest.mark.parametrize(("parent_changes", "error"), [({"offering_status": "inactive"}, service.AssessmentCourseOfferingUnavailableError), ({"assignment_status": "inactive"}, service.AssessmentLecturerAssignmentUnavailableError), ({"employment_status": "inactive"}, service.AssessmentLecturerUnavailableError), ({"user_active": False}, service.AssessmentLecturerUnavailableError)])
def test_inactive_parent_chain_is_rejected(parent_changes: dict[str, object], error: type[Exception]) -> None:
    institution_id, offering, assignment = _parents(**parent_changes)  # type: ignore[arg-type]
    with pytest.raises(error): service.create_assessment_component(Session(offering, assignment), institution_id=institution_id, assessment_component_data=_payload(offering, assignment))  # type: ignore[arg-type]


def test_hierarchy_duplicates_and_date_boundaries_are_revalidated() -> None:
    institution_id, offering, assignment = _parents(); assignment.course_offering_id = uuid4()
    with pytest.raises(service.AssessmentHierarchyMismatchError): service.create_assessment_component(Session(offering, assignment), institution_id=institution_id, assessment_component_data=_payload(offering, assignment))  # type: ignore[arg-type]
    assignment.course_offering_id = offering.id
    with pytest.raises(service.DuplicateAssessmentComponentError): service.create_assessment_component(Session(offering, assignment, uuid4()), institution_id=institution_id, assessment_component_data=_payload(offering, assignment, title=" assignment  1 "))  # type: ignore[arg-type]
    for changes in ({"scheduled_date": "2026-01-31", "due_at": None}, {"scheduled_date": "2026-07-01", "due_at": None}, {"scheduled_date": None, "due_at": "2026-01-31T12:00:00Z"}, {"scheduled_date": None, "due_at": "2027-01-01T12:00:00Z"}):
        with pytest.raises(service.AssessmentDateRangeError): service.create_assessment_component(Session(offering, assignment), institution_id=institution_id, assessment_component_data=_payload(offering, assignment, **changes))  # type: ignore[arg-type]


def test_list_filters_retrieve_update_structural_edit_and_soft_delete() -> None:
    institution_id, offering, assignment = _parents(); component = _component(institution_id, offering, assignment)
    session = Session([component])
    assert service.list_assessment_components(session, institution_id=institution_id, course_offering_id=offering.id, lecturer_assignment_id=assignment.id, assessment_type=AssessmentType.ASSIGNMENT, status=AssessmentComponentStatus.DRAFT, scheduled_date=date(2026, 3, 1)) == [component]  # type: ignore[arg-type]
    statement = str(session.statements[0]); assert all(name in statement for name in ("institution_id", "course_offering_id", "lecturer_assignment_id", "assessment_type", "status", "scheduled_date"))
    updated = service.update_assessment_component(Session(component, offering, assignment, None, Decimal("70")), assessment_component_id=component.id, institution_id=institution_id, assessment_component_data=AssessmentComponentUpdate(title=" Project ", assessment_type="project", maximum_score="50", weight_percentage="25"))  # type: ignore[arg-type]
    assert updated.title == "Project" and updated.assessment_type == "project" and updated.maximum_score == Decimal("50")
    deletion = Session(component); service.delete_assessment_component(deletion, assessment_component_id=component.id, institution_id=institution_id)  # type: ignore[arg-type]
    assert component.status == "inactive" and deletion.commits == 1 and offering.status == "active" and assignment.status == "active"


def test_cross_institution_operations_router_registration_and_auth_security() -> None:
    for operation in (
        lambda: service.get_assessment_component(Session(), assessment_component_id=uuid4(), institution_id=uuid4()),
        lambda: service.update_assessment_component(Session(), assessment_component_id=uuid4(), institution_id=uuid4(), assessment_component_data=AssessmentComponentUpdate(description="x")),
        lambda: service.delete_assessment_component(Session(), assessment_component_id=uuid4(), institution_id=uuid4()),
    ):
        with pytest.raises(service.AssessmentComponentNotFoundError): operation()
    paths = app.openapi()["paths"]
    assert "/api/v1/assessment-components" in paths and "/api/v1/assessment-components/{assessment_component_id}" in paths
    assert paths["/api/v1/assessment-components"]["post"].get("security")
