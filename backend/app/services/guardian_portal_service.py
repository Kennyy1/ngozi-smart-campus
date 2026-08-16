from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.guardian import Guardian
from app.models.guardian_student import GuardianStudent
from app.models.student import Student
from app.schemas.guardian import ChildOverview, GuardianChild, GuardianClearance, GuardianClearanceItem, GuardianDashboard
from app.services import student_portal_service


class GuardianPortalNotFoundError(Exception): pass

def resolve_guardian(session: Session, *, institution_id: UUID, user_id: UUID) -> Guardian:
    item=session.scalar(select(Guardian).where(Guardian.user_id==user_id,Guardian.institution_id==institution_id,Guardian.is_active.is_(True)))
    if item is None: raise GuardianPortalNotFoundError()
    return item

def _relationship(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID, permission: str | None=None) -> tuple[GuardianStudent,Student]:
    guardian=resolve_guardian(session,institution_id=institution_id,user_id=user_id)
    item=session.scalar(select(GuardianStudent).options(joinedload(GuardianStudent.student).joinedload(Student.user),joinedload(GuardianStudent.student).joinedload(Student.programme)).where(GuardianStudent.institution_id==institution_id,GuardianStudent.guardian_id==guardian.id,GuardianStudent.student_id==student_id,GuardianStudent.status=="verified"))
    if item is None or item.student.institution_id!=institution_id or (permission and not getattr(item,permission)): raise GuardianPortalNotFoundError()
    return item,item.student

def _child(item: GuardianStudent) -> GuardianChild:
    student=item.student
    return GuardianChild(student_id=student.id,matriculation_number=student.matriculation_number,student_name=f"{student.user.first_name} {student.user.last_name}".strip(),programme_name=student.programme.name if student.programme else None,current_level=student.current_level,enrollment_status=student.enrollment_status,relationship_type=item.relationship_type,is_primary=item.is_primary,can_view_results=item.can_view_results,can_view_attendance=item.can_view_attendance,can_view_academic_performance=item.can_view_academic_performance,can_view_transcript=item.can_view_transcript,can_view_clearance=item.can_view_clearance)

def list_children(session: Session, *, institution_id: UUID, user_id: UUID) -> list[GuardianChild]:
    guardian=resolve_guardian(session,institution_id=institution_id,user_id=user_id)
    items=session.scalars(select(GuardianStudent).options(joinedload(GuardianStudent.student).joinedload(Student.user),joinedload(GuardianStudent.student).joinedload(Student.programme)).where(GuardianStudent.institution_id==institution_id,GuardianStudent.guardian_id==guardian.id,GuardianStudent.status=="verified").order_by(GuardianStudent.is_primary.desc(),GuardianStudent.created_at)).all()
    return [_child(x) for x in items]

def dashboard(session: Session, *, institution_id: UUID, user_id: UUID) -> GuardianDashboard:
    guardian=resolve_guardian(session,institution_id=institution_id,user_id=user_id); children=list_children(session,institution_id=institution_id,user_id=user_id)
    return GuardianDashboard(guardian_id=guardian.id,guardian_name=f"{guardian.user.first_name} {guardian.user.last_name}".strip(),child_count=len(children),children=children)

def results(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID):
    _,student=_relationship(session,institution_id=institution_id,user_id=user_id,student_id=student_id,permission="can_view_results")
    return student_portal_service.list_results(session,institution_id=institution_id,user_id=student.user_id)

def attendance(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID):
    _,student=_relationship(session,institution_id=institution_id,user_id=user_id,student_id=student_id,permission="can_view_attendance")
    return student_portal_service.list_attendance(session,institution_id=institution_id,user_id=student.user_id)

def performance(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID):
    _,student=_relationship(session,institution_id=institution_id,user_id=user_id,student_id=student_id,permission="can_view_academic_performance")
    return student_portal_service.get_academic_performance(session,institution_id=institution_id,user_id=student.user_id)

def transcript(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID):
    _relationship(session,institution_id=institution_id,user_id=user_id,student_id=student_id,permission="can_view_transcript")
    return student_portal_service.get_transcript(session,institution_id=institution_id,student_id=student_id)

def clearance(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID) -> GuardianClearance:
    _relationship(session,institution_id=institution_id,user_id=user_id,student_id=student_id,permission="can_view_clearance")
    value=student_portal_service.get_clearance(session,institution_id=institution_id,student_id=student_id)
    return GuardianClearance(student_id=value.student_id,matriculation_number=value.matriculation_number,student_name=value.student_name,is_fully_cleared=value.is_fully_cleared,pending_count=value.pending_count,requirements=[GuardianClearanceItem(clearance_requirement_id=x.clearance_requirement_id,name=x.name,code=x.code,is_mandatory=x.is_mandatory,status=x.status) for x in value.requirements])

def overview(session: Session, *, institution_id: UUID, user_id: UUID, student_id: UUID) -> ChildOverview:
    item,_=_relationship(session,institution_id=institution_id,user_id=user_id,student_id=student_id)
    kwargs={}
    if item.can_view_results: kwargs["result_count"]=len(results(session,institution_id=institution_id,user_id=user_id,student_id=student_id))
    if item.can_view_attendance:
        rows=attendance(session,institution_id=institution_id,user_id=user_id,student_id=student_id); total=sum(x.total_sessions for x in rows); present=sum(x.present_count+x.late_count for x in rows)
        kwargs["attendance_percentage"]=str((Decimal(present)*100/Decimal(total)).quantize(Decimal("0.01"))) if total else "0.00"
    if item.can_view_academic_performance:
        value=performance(session,institution_id=institution_id,user_id=user_id,student_id=student_id); kwargs.update(current_gpa=str(value.current_gpa) if value.current_gpa is not None else None,cgpa=str(value.cgpa),academic_standing=value.academic_standing)
    if item.can_view_clearance:
        value=clearance(session,institution_id=institution_id,user_id=user_id,student_id=student_id); kwargs["clearance"]={"is_fully_cleared":value.is_fully_cleared,"pending_count":value.pending_count}
    return ChildOverview(child=_child(item),**kwargs)
