from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.assessment_component import AssessmentComponent
from app.models.assessment_score import AssessmentScore
from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.examination import Examination
from app.models.examination_score import ExaminationScore
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.result import Result
from app.models.student import Student
from app.models.user import User
from app.schemas.attendance_record import AttendanceRecordCreate, AttendanceRecordUpdate
from app.schemas.assessment_score import AssessmentScoreCreate, AssessmentScoreUpdate
from app.schemas.examination_score import ExaminationScoreCreate, ExaminationScoreUpdate
from app.services.attendance_record_service import create_attendance_record, update_attendance_record
from app.services.assessment_score_service import create_assessment_score, update_assessment_score
from app.services.examination_score_service import create_examination_score, update_examination_score
from app.schemas.lecturer_portal import *


class LecturerPortalProfileNotFoundError(Exception): pass
class LecturerPortalOfferingNotFoundError(Exception): pass


def resolve_lecturer(session: Session, *, institution_id: UUID, user_id: UUID) -> Lecturer:
    item = session.scalar(select(Lecturer).options(joinedload(Lecturer.user), joinedload(Lecturer.department)).where(
        Lecturer.user_id == user_id, Lecturer.institution_id == institution_id))
    if item is None: raise LecturerPortalProfileNotFoundError()
    return item


def resolve_assignment(session: Session, *, institution_id: UUID, lecturer_id: UUID, course_offering_id: UUID) -> LecturerAssignment:
    item = session.scalar(select(LecturerAssignment).where(LecturerAssignment.institution_id == institution_id,
        LecturerAssignment.lecturer_id == lecturer_id, LecturerAssignment.course_offering_id == course_offering_id,
        LecturerAssignment.status == "active"))
    if item is None: raise LecturerPortalOfferingNotFoundError()
    return item


def list_courses(session: Session, *, institution_id: UUID, user_id: UUID, academic_session_id: UUID | None = None,
                 semester_id: UUID | None = None, status: str | None = None) -> list[LecturerCourse]:
    lecturer = resolve_lecturer(session, institution_id=institution_id, user_id=user_id)
    registrations = select(CourseRegistration.course_offering_id, func.count(CourseRegistration.id).label("n")).where(
        CourseRegistration.institution_id == institution_id, CourseRegistration.status == "active",
        CourseRegistration.registration_status == "registered").group_by(CourseRegistration.course_offering_id).subquery()
    from app.models.academic_session import AcademicSession
    from app.models.semester import Semester
    statement = (select(LecturerAssignment, CourseOffering, Course, AcademicSession, Semester, func.coalesce(registrations.c.n, 0))
        .join(CourseOffering, LecturerAssignment.course_offering_id == CourseOffering.id).join(Course, CourseOffering.course_id == Course.id)
        .join(AcademicSession, CourseOffering.academic_session_id == AcademicSession.id).join(Semester, CourseOffering.semester_id == Semester.id)
        .outerjoin(registrations, registrations.c.course_offering_id == CourseOffering.id)
        .where(LecturerAssignment.institution_id == institution_id, LecturerAssignment.lecturer_id == lecturer.id,
               LecturerAssignment.status == "active"))
    if academic_session_id: statement = statement.where(CourseOffering.academic_session_id == academic_session_id)
    if semester_id: statement = statement.where(CourseOffering.semester_id == semester_id)
    if status: statement = statement.where(LecturerAssignment.status == status)
    return [LecturerCourse(lecturer_assignment_id=a.id, course_offering_id=o.id, course_id=c.id, course_code=c.code,
        course_title=c.title, credit_units=c.credit_units, academic_session_id=ac.id, academic_session=ac.name,
        semester_id=sem.id, semester=sem.name, status=a.status, registered_student_count=n)
        for a, o, c, ac, sem, n in session.execute(statement).all()]


def list_students(session: Session, *, institution_id: UUID, user_id: UUID, course_offering_id: UUID) -> list[LecturerCourseStudent]:
    lecturer = resolve_lecturer(session, institution_id=institution_id, user_id=user_id)
    resolve_assignment(session, institution_id=institution_id, lecturer_id=lecturer.id, course_offering_id=course_offering_id)
    rows = session.execute(select(CourseRegistration, Student, User).join(Student, CourseRegistration.student_id == Student.id)
        .join(User, Student.user_id == User.id).where(CourseRegistration.institution_id == institution_id,
        CourseRegistration.course_offering_id == course_offering_id, CourseRegistration.status == "active",
        CourseRegistration.registration_status == "registered")).all()
    return [LecturerCourseStudent(course_registration_id=r.id, student_id=s.id, matriculation_number=s.matriculation_number,
        student_name=f"{u.first_name} {u.last_name}".strip(), current_level=s.current_level,
        registration_status=r.registration_status) for r, s, u in rows]


def attendance(session: Session, *, institution_id: UUID, user_id: UUID, course_offering_id: UUID) -> list[LecturerAttendance]:
    students = list_students(session, institution_id=institution_id, user_id=user_id, course_offering_id=course_offering_id)
    counts = {row[0]: row[1:] for row in session.execute(select(AttendanceRecord.course_registration_id, func.count(AttendanceRecord.id),
        func.sum(case((AttendanceRecord.attendance_status == "present", 1), else_=0)),
        func.sum(case((AttendanceRecord.attendance_status == "absent", 1), else_=0)),
        func.sum(case((AttendanceRecord.attendance_status == "late", 1), else_=0))).where(
        AttendanceRecord.institution_id == institution_id, AttendanceRecord.status == "active",
        AttendanceRecord.course_registration_id.in_([x.course_registration_id for x in students] or [UUID(int=0)]))
        .group_by(AttendanceRecord.course_registration_id)).all()}
    output=[]
    for s in students:
        total, present, absent, late = counts.get(s.course_registration_id, (0, 0, 0, 0)); total=total or 0; present=present or 0; absent=absent or 0; late=late or 0
        pct=(Decimal(present+late)*100/Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total else Decimal("0.00")
        output.append(LecturerAttendance(**s.model_dump(), total_sessions=total, present_count=present, absent_count=absent, late_count=late, attendance_percentage=pct))
    return output


def assessments(session: Session, *, institution_id: UUID, user_id: UUID, course_offering_id: UUID) -> list[LecturerAssessment]:
    lecturer=resolve_lecturer(session,institution_id=institution_id,user_id=user_id); assignment=resolve_assignment(session,institution_id=institution_id,lecturer_id=lecturer.id,course_offering_id=course_offering_id)
    registered=session.scalar(select(func.count()).select_from(CourseRegistration).where(CourseRegistration.institution_id==institution_id,CourseRegistration.course_offering_id==course_offering_id,CourseRegistration.status=="active",CourseRegistration.registration_status=="registered")) or 0
    rows=session.execute(select(AssessmentComponent,func.count(AssessmentScore.id)).outerjoin(AssessmentScore,(AssessmentScore.assessment_component_id==AssessmentComponent.id)&(AssessmentScore.status=="active")).where(AssessmentComponent.institution_id==institution_id,AssessmentComponent.course_offering_id==course_offering_id,AssessmentComponent.lecturer_assignment_id==assignment.id,AssessmentComponent.status!="inactive").group_by(AssessmentComponent.id)).all()
    return [LecturerAssessment(component_id=x.id,title=x.title,type=x.assessment_type,maximum_score=x.maximum_score,weight=x.weight_percentage,status=x.status,scheduled_date=x.scheduled_date,due_date=x.due_at.date() if x.due_at else None,registered_student_count=registered,scored_student_count=n,unscored_student_count=max(registered-n,0)) for x,n in rows]


def examinations(session: Session, *, institution_id: UUID, user_id: UUID, course_offering_id: UUID) -> list[LecturerExamination]:
    lecturer=resolve_lecturer(session,institution_id=institution_id,user_id=user_id); assignment=resolve_assignment(session,institution_id=institution_id,lecturer_id=lecturer.id,course_offering_id=course_offering_id)
    registered=session.scalar(select(func.count()).select_from(CourseRegistration).where(CourseRegistration.institution_id==institution_id,CourseRegistration.course_offering_id==course_offering_id,CourseRegistration.status=="active",CourseRegistration.registration_status=="registered")) or 0
    rows=session.execute(select(Examination,func.count(ExaminationScore.id)).outerjoin(ExaminationScore,(ExaminationScore.examination_id==Examination.id)&(ExaminationScore.status=="active")).where(Examination.institution_id==institution_id,Examination.course_offering_id==course_offering_id,Examination.lecturer_assignment_id==assignment.id,Examination.status!="inactive").group_by(Examination.id)).all()
    return [LecturerExamination(examination_id=x.id,title=x.title,type=x.examination_type,maximum_score=x.maximum_score,weight=x.weight_percentage,examination_date=x.exam_date,start_time=x.start_time,end_time=x.end_time,status=x.status,registered_student_count=registered,scored_student_count=n,unscored_student_count=max(registered-n,0)) for x,n in rows]


def results(session: Session, *, institution_id: UUID, user_id: UUID, course_offering_id: UUID) -> LecturerResultOverview:
    lecturer=resolve_lecturer(session,institution_id=institution_id,user_id=user_id); resolve_assignment(session,institution_id=institution_id,lecturer_id=lecturer.id,course_offering_id=course_offering_id)
    registered=session.scalar(select(func.count()).select_from(CourseRegistration).where(CourseRegistration.institution_id==institution_id,CourseRegistration.course_offering_id==course_offering_id,CourseRegistration.status=="active",CourseRegistration.registration_status=="registered")) or 0
    rows=session.execute(select(Result,Student,User).join(Student,Result.student_id==Student.id).join(User,Student.user_id==User.id).where(Result.institution_id==institution_id,Result.course_offering_id==course_offering_id,Result.status=="published")).all()
    items=[{"result_id":r.id,"student_id":s.id,"matriculation_number":s.matriculation_number,"student_name":f"{u.first_name} {u.last_name}".strip(),"final_score":r.final_score,"grade":r.grade_letter,"grade_point":r.grade_point,"passed":r.passed} for r,s,u in rows]
    return LecturerResultOverview(course_offering_id=course_offering_id,registered_student_count=registered,published_result_count=len(items),missing_published_result_count=max(registered-len(items),0),results=items)


def dashboard(session: Session, *, institution_id: UUID, user_id: UUID) -> LecturerDashboard:
    lecturer=resolve_lecturer(session,institution_id=institution_id,user_id=user_id); courses=list_courses(session,institution_id=institution_id,user_id=user_id)
    assignment_ids=[c.lecturer_assignment_id for c in courses]
    upcoming=session.scalar(select(func.count()).select_from(ClassSession).where(ClassSession.institution_id==institution_id,ClassSession.lecturer_assignment_id.in_(assignment_ids or [UUID(int=0)]),ClassSession.session_date>=date.today(),ClassSession.status=="scheduled")) or 0
    pending=session.scalar(select(func.count()).select_from(AssessmentComponent).where(AssessmentComponent.institution_id==institution_id,AssessmentComponent.lecturer_assignment_id.in_(assignment_ids or [UUID(int=0)]),AssessmentComponent.status=="draft")) or 0
    completed=session.scalar(select(func.count()).select_from(Examination).where(Examination.institution_id==institution_id,Examination.lecturer_assignment_id.in_(assignment_ids or [UUID(int=0)]),Examination.status=="completed")) or 0
    return LecturerDashboard(lecturer_id=lecturer.id,staff_number=lecturer.staff_number,name=f"{lecturer.user.first_name} {lecturer.user.last_name}".strip(),department=lecturer.department.name,employment_status=lecturer.employment_status,active_course_assignment_count=len(courses),current_course_offering_count=sum(1 for c in courses),upcoming_class_session_count=upcoming,total_registered_students=sum(c.registered_student_count for c in courses),pending_assessment_component_count=pending,completed_examination_count=completed)


def class_sessions(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID):
    lecturer=resolve_lecturer(session,institution_id=institution_id,user_id=user_id);assignment=resolve_assignment(session,institution_id=institution_id,lecturer_id=lecturer.id,course_offering_id=course_offering_id)
    return list(session.scalars(select(ClassSession).where(ClassSession.institution_id==institution_id,ClassSession.course_offering_id==course_offering_id,ClassSession.lecturer_assignment_id==assignment.id,ClassSession.status.in_(("scheduled","completed"))).order_by(ClassSession.session_date.desc(),ClassSession.start_time)).all())


def attendance_sheet(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID,class_session_id:UUID):
    sessions=class_sessions(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id)
    if class_session_id not in {x.id for x in sessions}:raise LecturerPortalOfferingNotFoundError()
    students=list_students(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id)
    existing={x.course_registration_id:x for x in session.scalars(select(AttendanceRecord).where(AttendanceRecord.institution_id==institution_id,AttendanceRecord.class_session_id==class_session_id,AttendanceRecord.status=="active")).all()}
    return [{**x.model_dump(),"attendance_record_id":existing[x.course_registration_id].id if x.course_registration_id in existing else None,"attendance_status":existing[x.course_registration_id].attendance_status if x.course_registration_id in existing else None} for x in students]


def save_attendance(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID,class_session_id:UUID,records:list[dict]):
    allowed={x["course_registration_id"] for x in attendance_sheet(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id,class_session_id=class_session_id)}
    existing={x.course_registration_id:x for x in session.scalars(select(AttendanceRecord).where(AttendanceRecord.institution_id==institution_id,AttendanceRecord.class_session_id==class_session_id,AttendanceRecord.status=="active")).all()};output=[]
    for row in records:
        registration_id=UUID(str(row["course_registration_id"]));status=row["attendance_status"]
        if registration_id not in allowed:raise LecturerPortalOfferingNotFoundError()
        check_in=datetime.now().astimezone() if status=="late" else None
        if registration_id in existing:output.append(update_attendance_record(session,attendance_record_id=existing[registration_id].id,institution_id=institution_id,attendance_data=AttendanceRecordUpdate(attendance_status=status,check_in_time=check_in)))
        else:output.append(create_attendance_record(session,institution_id=institution_id,recorded_by_user_id=user_id,attendance_data=AttendanceRecordCreate(class_session_id=class_session_id,course_registration_id=registration_id,attendance_status=status,check_in_time=check_in)))
    return output


def assessment_sheet(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID,component_id:UUID):
    component=next((x for x in assessments(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id) if x.component_id==component_id),None)
    if component is None:raise LecturerPortalOfferingNotFoundError()
    students=list_students(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id);existing={x.course_registration_id:x for x in session.scalars(select(AssessmentScore).where(AssessmentScore.institution_id==institution_id,AssessmentScore.assessment_component_id==component_id,AssessmentScore.status=="active")).all()}
    return {"item":component.model_dump(),"students":[{**x.model_dump(),"score_id":existing[x.course_registration_id].id if x.course_registration_id in existing else None,"score":existing[x.course_registration_id].score if x.course_registration_id in existing else None} for x in students]}


def save_assessment_scores(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID,component_id:UUID,scores:list[dict]):
    sheet=assessment_sheet(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id,component_id=component_id);allowed={str(x["course_registration_id"]) for x in sheet["students"]};existing={str(x["course_registration_id"]):x.get("score_id") for x in sheet["students"]};out=[]
    for row in scores:
        rid=str(row["course_registration_id"])
        if rid not in allowed:raise LecturerPortalOfferingNotFoundError()
        if existing[rid]:out.append(update_assessment_score(session,assessment_score_id=existing[rid],institution_id=institution_id,assessment_score_data=AssessmentScoreUpdate(score=row["score"])))
        else:out.append(create_assessment_score(session,institution_id=institution_id,graded_by_user_id=user_id,assessment_score_data=AssessmentScoreCreate(assessment_component_id=component_id,course_registration_id=UUID(rid),score=row["score"])))
    return out


def examination_sheet(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID,examination_id:UUID):
    exam=next((x for x in examinations(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id) if x.examination_id==examination_id),None)
    if exam is None:raise LecturerPortalOfferingNotFoundError()
    students=list_students(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id);existing={x.course_registration_id:x for x in session.scalars(select(ExaminationScore).where(ExaminationScore.institution_id==institution_id,ExaminationScore.examination_id==examination_id,ExaminationScore.status=="active")).all()}
    return {"item":exam.model_dump(),"students":[{**x.model_dump(),"score_id":existing[x.course_registration_id].id if x.course_registration_id in existing else None,"score":existing[x.course_registration_id].score if x.course_registration_id in existing else None} for x in students]}


def save_examination_scores(session:Session,*,institution_id:UUID,user_id:UUID,course_offering_id:UUID,examination_id:UUID,scores:list[dict]):
    sheet=examination_sheet(session,institution_id=institution_id,user_id=user_id,course_offering_id=course_offering_id,examination_id=examination_id);allowed={str(x["course_registration_id"]) for x in sheet["students"]};existing={str(x["course_registration_id"]):x.get("score_id") for x in sheet["students"]};out=[]
    for row in scores:
        rid=str(row["course_registration_id"])
        if rid not in allowed:raise LecturerPortalOfferingNotFoundError()
        if existing[rid]:out.append(update_examination_score(session,examination_score_id=existing[rid],institution_id=institution_id,examination_score_data=ExaminationScoreUpdate(score=row["score"])))
        else:out.append(create_examination_score(session,institution_id=institution_id,graded_by_user_id=user_id,examination_score_data=ExaminationScoreCreate(examination_id=examination_id,course_registration_id=UUID(rid),score=row["score"])))
    return out
