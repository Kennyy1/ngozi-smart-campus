from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.main import app
from app.models.course_offering import CourseOffering
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.user import User
from app.schemas.lecturer_assignment import AssignmentRole, AssignmentStatus, LecturerAssignmentCreate, LecturerAssignmentUpdate
from app.services import lecturer_assignment_service as service


class Results:
    def __init__(self, values: list[LecturerAssignment]) -> None: self.values = values
    def all(self) -> list[LecturerAssignment]: return self.values


class Session:
    def __init__(self, *results: object) -> None: self.results = list(results); self.statements: list[object] = []; self.added: list[object] = []; self.commits = 0; self.rollbacks = 0
    def scalar(self, statement: object) -> object: self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> Results: self.statements.append(statement); return Results(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def commit(self) -> None:
        self.commits += 1; now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None: value.id = uuid4()
            if getattr(value, "created_at", None) is None: value.created_at = now
            if getattr(value, "updated_at", None) is None: value.updated_at = now
    def rollback(self) -> None: self.rollbacks += 1
    def refresh(self, value: object) -> None: pass


def _lecturer(institution_id: object, *, active: bool = True) -> Lecturer:
    user = User(id=uuid4(), institution_id=institution_id, email="l@test.edu", password_hash="x", first_name="L", last_name="T", is_active=active, is_verified=True)
    lecturer = Lecturer(id=uuid4(), institution_id=institution_id, user_id=user.id, department_id=uuid4(), staff_number="NSC/L/1", academic_rank="lecturer_i", employment_status="active", specialization=None, employment_date=None, office_location=None); lecturer.user = user; return lecturer  # type: ignore[arg-type]


def _offering(institution_id: object, *, status: str = "active") -> CourseOffering:
    return CourseOffering(id=uuid4(), institution_id=institution_id, course_id=uuid4(), academic_session_id=uuid4(), semester_id=uuid4(), status=status, registration_open=False)  # type: ignore[arg-type]


def _payload(lecturer: Lecturer, offering: CourseOffering, *, primary: bool = True) -> LecturerAssignmentCreate:
    return LecturerAssignmentCreate(lecturer_id=lecturer.id, course_offering_id=offering.id, assignment_role="primary" if primary else "co_instructor", is_primary=primary, notes=" Notes ")


def _record(institution_id: object, lecturer: Lecturer, offering: CourseOffering) -> LecturerAssignment:
    now = datetime.now(UTC); return LecturerAssignment(id=uuid4(), institution_id=institution_id, lecturer_id=lecturer.id, course_offering_id=offering.id, assignment_role="primary", is_primary=True, assigned_at=now, ended_at=None, status="active", notes=None, created_at=now, updated_at=now)  # type: ignore[arg-type]


def test_schema_rules_and_request_security() -> None:
    assert {"institution_id", "id", "created_at", "updated_at", "deleted_at"}.isdisjoint(LecturerAssignmentCreate.model_fields)
    with pytest.raises(ValidationError): LecturerAssignmentCreate(lecturer_id=uuid4(), course_offering_id=uuid4(), assignment_role="primary", is_primary=False)
    now = datetime.now(UTC)
    with pytest.raises(ValidationError): LecturerAssignmentCreate(lecturer_id=uuid4(), course_offering_id=uuid4(), assignment_role="co_instructor", is_primary=False, assigned_at=now, ended_at=now)


def test_successful_creation_derives_institution() -> None:
    institution_id = uuid4(); lecturer = _lecturer(institution_id); offering = _offering(institution_id); session = Session(lecturer, offering, None, None)
    result = service.create_lecturer_assignment(session, institution_id=institution_id, lecturer_assignment_data=_payload(lecturer, offering))  # type: ignore[arg-type]
    assert result.institution_id == institution_id and result.notes == "Notes" and session.commits == 1


@pytest.mark.parametrize(("results", "error"), [([], service.AssignmentLecturerNotFoundError), (["lecturer"], service.AssignmentCourseOfferingNotFoundError), (["lecturer", "offering", uuid4()], service.DuplicateLecturerAssignmentError), (["lecturer", "offering", None, uuid4()], service.DuplicatePrimaryLecturerError)])
def test_references_and_conflicts(results: list[object], error: type[Exception]) -> None:
    institution_id = uuid4(); lecturer = _lecturer(institution_id); offering = _offering(institution_id); values = [lecturer if x == "lecturer" else offering if x == "offering" else x for x in results]
    with pytest.raises(error): service.create_lecturer_assignment(Session(*values), institution_id=institution_id, lecturer_assignment_data=_payload(lecturer, offering))  # type: ignore[arg-type]


def test_inactive_lecturer_user_and_offering_rejected() -> None:
    institution_id = uuid4(); lecturer = _lecturer(institution_id, active=False); offering = _offering(institution_id)
    with pytest.raises(service.LecturerUnavailableError): service.create_lecturer_assignment(Session(lecturer, offering), institution_id=institution_id, lecturer_assignment_data=_payload(lecturer, offering))  # type: ignore[arg-type]
    lecturer.user.is_active = True; offering.status = "inactive"
    with pytest.raises(service.CourseOfferingUnavailableError): service.create_lecturer_assignment(Session(lecturer, offering), institution_id=institution_id, lecturer_assignment_data=_payload(lecturer, offering))  # type: ignore[arg-type]


def test_list_filters_retrieve_update_and_delete() -> None:
    institution_id = uuid4(); lecturer = _lecturer(institution_id); offering = _offering(institution_id); record = _record(institution_id, lecturer, offering)
    session = Session([record]); assert service.list_lecturer_assignments(session, institution_id=institution_id, lecturer_id=lecturer.id, course_offering_id=offering.id, assignment_role=AssignmentRole.PRIMARY, is_primary=True, status=AssignmentStatus.ACTIVE) == [record]  # type: ignore[arg-type]
    assert all(name in str(session.statements[0]) for name in ("institution_id", "lecturer_id", "course_offering_id", "assignment_role", "is_primary", "status"))
    assert service.get_lecturer_assignment(Session(record), lecturer_assignment_id=record.id, institution_id=institution_id) is record  # type: ignore[arg-type]
    updated = service.update_lecturer_assignment(Session(record, lecturer, offering, None), lecturer_assignment_id=record.id, institution_id=institution_id, lecturer_assignment_data=LecturerAssignmentUpdate(assignment_role="co_instructor", is_primary=False, ended_at=datetime.now(UTC) + timedelta(days=1)))  # type: ignore[arg-type]
    assert updated.assignment_role == "co_instructor" and not updated.is_primary
    deletion = Session(record); service.delete_lecturer_assignment(deletion, lecturer_assignment_id=record.id, institution_id=institution_id)  # type: ignore[arg-type]
    assert record.status == "inactive" and deletion.commits == 1


def test_cross_institution_operations_are_not_found_and_router_registered() -> None:
    with pytest.raises(service.LecturerAssignmentNotFoundError): service.get_lecturer_assignment(Session(), lecturer_assignment_id=uuid4(), institution_id=uuid4())  # type: ignore[arg-type]
    with pytest.raises(service.LecturerAssignmentNotFoundError): service.update_lecturer_assignment(Session(), lecturer_assignment_id=uuid4(), institution_id=uuid4(), lecturer_assignment_data=LecturerAssignmentUpdate(notes="x"))  # type: ignore[arg-type]
    with pytest.raises(service.LecturerAssignmentNotFoundError): service.delete_lecturer_assignment(Session(), lecturer_assignment_id=uuid4(), institution_id=uuid4())  # type: ignore[arg-type]
    assert "/api/v1/lecturer-assignments/{lecturer_assignment_id}" in app.openapi()["paths"]
