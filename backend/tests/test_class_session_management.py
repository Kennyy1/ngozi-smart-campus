from datetime import UTC, date, datetime, time
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.main import app
from app.models.academic_session import AcademicSession
from app.models.class_session import ClassSession
from app.models.course_offering import CourseOffering
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.semester import Semester
from app.models.user import User
from app.schemas.class_session import ClassSessionCreate, ClassSessionStatus, ClassSessionUpdate, DeliveryMode, SessionType
from app.services import class_session_service as service

class Result:
    def __init__(self, values: list[ClassSession]) -> None: self.values = values
    def all(self) -> list[ClassSession]: return self.values
class Session:
    def __init__(self, *results: object) -> None: self.results=list(results); self.statements=[]; self.added=[]; self.commits=0
    def scalar(self, statement: object) -> object: self.statements.append(statement); return self.results.pop(0) if self.results else None
    def scalars(self, statement: object) -> Result: self.statements.append(statement); return Result(self.results.pop(0) if self.results else [])  # type: ignore[arg-type]
    def add(self, value: object) -> None: self.added.append(value)
    def commit(self) -> None:
        self.commits += 1; now=datetime.now(UTC)
        for value in self.added:
            if getattr(value,"id",None) is None: value.id=uuid4()
            if getattr(value,"created_at",None) is None: value.created_at=now
            if getattr(value,"updated_at",None) is None: value.updated_at=now
    def refresh(self, value: object) -> None: pass
    def rollback(self) -> None: pass

def parents() -> tuple[object, CourseOffering, LecturerAssignment]:
    institution_id=uuid4(); academic=AcademicSession(id=uuid4(),institution_id=institution_id,name="2026",start_date=date(2026,1,1),end_date=date(2026,12,31),is_current=True,status="active")
    semester=Semester(id=uuid4(),institution_id=institution_id,academic_session_id=academic.id,name="First",sequence_number=1,start_date=date(2026,1,1),end_date=date(2026,6,30),is_current=True,status="active")
    offering=CourseOffering(id=uuid4(),institution_id=institution_id,course_id=uuid4(),academic_session_id=academic.id,semester_id=semester.id,registration_open=False,status="active"); offering.academic_session=academic; offering.semester=semester
    user=User(id=uuid4(),institution_id=institution_id,email="l@test.edu",password_hash="x",first_name="L",last_name="T",is_active=True,is_verified=True)
    lecturer=Lecturer(id=uuid4(),institution_id=institution_id,user_id=user.id,department_id=uuid4(),staff_number="L1",academic_rank="lecturer_i",employment_status="active"); lecturer.user=user
    assignment=LecturerAssignment(id=uuid4(),institution_id=institution_id,lecturer_id=lecturer.id,course_offering_id=offering.id,assignment_role="primary",is_primary=True,assigned_at=datetime.now(UTC),status="active"); assignment.lecturer=lecturer
    return institution_id,offering,assignment
def payload(offering: CourseOffering, assignment: LecturerAssignment, **changes: object) -> ClassSessionCreate:
    values=dict(course_offering_id=offering.id,lecturer_assignment_id=assignment.id,session_date=date(2026,3,3),start_time=time(9),end_time=time(10),session_type="lecture",topic=" Introduction ",venue=" A1 ")
    values.update(changes); return ClassSessionCreate(**values)  # type: ignore[arg-type]
def record(institution_id: object, offering: CourseOffering, assignment: LecturerAssignment) -> ClassSession:
    now=datetime.now(UTC); return ClassSession(id=uuid4(),institution_id=institution_id,course_offering_id=offering.id,lecturer_assignment_id=assignment.id,session_date=date(2026,3,3),start_time=time(9),end_time=time(10),session_type="lecture",topic="Introduction",venue="A1",delivery_mode="physical",status="scheduled",created_at=now,updated_at=now)  # type: ignore[arg-type]

def test_schema_time_venue_and_security() -> None:
    _,offering,assignment=parents(); assert payload(offering,assignment).topic=="Introduction"
    assert {"institution_id","lecturer_id","course_id","academic_session_id","semester_id","id"}.isdisjoint(ClassSessionCreate.model_fields)
    with pytest.raises(ValidationError): payload(offering,assignment,start_time=time(10),end_time=time(10))
    with pytest.raises(ValidationError): payload(offering,assignment,delivery_mode="hybrid",venue=" ")
    assert payload(offering,assignment,delivery_mode="online",venue=None).venue is None

def test_creation_scoping_dates_conflicts_and_adjacent() -> None:
    institution_id,offering,assignment=parents(); session=Session(offering,assignment,None,None)
    item=service.create_class_session(session,institution_id=institution_id,class_session_data=payload(offering,assignment))  # type: ignore[arg-type]
    assert item.institution_id==institution_id and session.commits==1
    with pytest.raises(service.InvalidClassSessionError): service.create_class_session(Session(offering,assignment),institution_id=institution_id,class_session_data=payload(offering,assignment,session_date=date(2025,12,31)))  # type: ignore[arg-type]
    with pytest.raises(service.DuplicateClassSessionError): service.create_class_session(Session(offering,assignment,uuid4()),institution_id=institution_id,class_session_data=payload(offering,assignment))  # type: ignore[arg-type]
    with pytest.raises(service.OverlappingClassSessionError): service.create_class_session(Session(offering,assignment,None,uuid4()),institution_id=institution_id,class_session_data=payload(offering,assignment))  # type: ignore[arg-type]
    assert service.create_class_session(Session(offering,assignment,None,None),institution_id=institution_id,class_session_data=payload(offering,assignment,start_time=time(10),end_time=time(11))).start_time==time(10)  # type: ignore[arg-type]

@pytest.mark.parametrize(("results","error"),[([],service.ClassSessionOfferingNotFoundError),(["offering"],service.ClassSessionAssignmentNotFoundError)])
def test_missing_parents(results: list[object], error: type[Exception]) -> None:
    institution_id,offering,assignment=parents(); values=[offering if x=="offering" else x for x in results]
    with pytest.raises(error): service.create_class_session(Session(*values),institution_id=institution_id,class_session_data=payload(offering,assignment))  # type: ignore[arg-type]

def test_list_update_delete_cross_institution_and_routes() -> None:
    institution_id,offering,assignment=parents(); item=record(institution_id,offering,assignment); session=Session([item])
    assert service.list_class_sessions(session,institution_id=institution_id,course_offering_id=offering.id,lecturer_assignment_id=assignment.id,session_date=item.session_date,session_type=SessionType.LECTURE,delivery_mode=DeliveryMode.PHYSICAL,status=ClassSessionStatus.SCHEDULED)==[item]  # type: ignore[arg-type]
    updated=service.update_class_session(Session(item,offering,assignment,None,None),class_session_id=item.id,institution_id=institution_id,class_session_data=ClassSessionUpdate(topic="Updated",start_time=time(10),end_time=time(11)))  # type: ignore[arg-type]
    assert updated.topic=="Updated"
    deletion=Session(item); service.delete_class_session(deletion,class_session_id=item.id,institution_id=institution_id); assert item.status=="inactive"  # type: ignore[arg-type]
    with pytest.raises(service.ClassSessionNotFoundError): service.get_class_session(Session(),class_session_id=uuid4(),institution_id=uuid4())  # type: ignore[arg-type]
    assert "/api/v1/class-sessions/{class_session_id}" in app.openapi()["paths"]
