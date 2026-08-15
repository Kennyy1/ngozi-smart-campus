from collections import Counter
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.academic_document import AcademicDocument
from app.models.academic_session import AcademicSession
from app.models.assessment_component import AssessmentComponent
from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.clearance_requirement import ClearanceRequirement
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.examination import Examination
from app.models.graduation_record import GraduationRecord
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.official_transcript import OfficialTranscript
from app.models.programme import Programme
from app.models.result import Result
from app.models.semester import Semester
from app.models.student import Student
from app.models.student_clearance import StudentClearance
from app.models.user import User
from app.schemas.admin_portal import AdminCourseOfferingSummary, AdminDashboard, AdminStudentSummary
from app.services.academic_progression_service import get_student_academic_progress
from app.services.clearance_service import compute_student_clearance_summary
from app.services.graduation_eligibility_service import evaluate_student_graduation_eligibility


class AdminPortalStudentNotFoundError(Exception): pass
class AdminPortalOfferingNotFoundError(Exception): pass


def _count(session: Session, model: type, institution_id: UUID, *conditions: object) -> int:
    return session.scalar(select(func.count()).select_from(model).where(model.institution_id == institution_id, *conditions)) or 0


def dashboard(session: Session, *, institution_id: UUID, institution_name: str) -> AdminDashboard:
    current_session=session.scalar(select(AcademicSession).where(AcademicSession.institution_id==institution_id,AcademicSession.is_current.is_(True)))
    current_semester=session.scalar(select(Semester).where(Semester.institution_id==institution_id,Semester.is_current.is_(True)))
    pending_clearances=session.scalar(select(func.count()).select_from(StudentClearance).join(ClearanceRequirement,StudentClearance.clearance_requirement_id==ClearanceRequirement.id).where(StudentClearance.institution_id==institution_id,ClearanceRequirement.institution_id==institution_id,ClearanceRequirement.is_mandatory.is_(True),ClearanceRequirement.status=="active",StudentClearance.status.in_(("pending","rejected")))) or 0
    return AdminDashboard(institution_id=institution_id,institution_name=institution_name,
        total_students=_count(session,Student,institution_id),active_students=_count(session,Student,institution_id,Student.enrollment_status=="active"),
        graduated_students=_count(session,Student,institution_id,Student.enrollment_status=="graduated"),
        total_lecturers=_count(session,Lecturer,institution_id),active_lecturers=_count(session,Lecturer,institution_id,Lecturer.employment_status=="active"),
        total_programmes=_count(session,Programme,institution_id),total_courses=_count(session,Course,institution_id),
        current_academic_session=current_session.name if current_session else None,current_semester=current_semester.name if current_semester else None,
        active_course_offerings=_count(session,CourseOffering,institution_id,CourseOffering.status=="active"),
        active_course_registrations=_count(session,CourseRegistration,institution_id,CourseRegistration.status=="active",CourseRegistration.registration_status=="registered"),
        published_results=_count(session,Result,institution_id,Result.status=="published"),
        pending_result_approvals=_count(session,Result,institution_id,Result.status=="submitted"),
        graduation_eligible_students=None,confirmed_graduations=_count(session,GraduationRecord,institution_id,GraduationRecord.status=="confirmed"),
        issued_transcripts=_count(session,OfficialTranscript,institution_id,OfficialTranscript.status=="issued"),
        issued_certificates=_count(session,AcademicDocument,institution_id,AcademicDocument.status=="issued",AcademicDocument.document_type=="certificate"),
        pending_mandatory_clearances=pending_clearances)


def student_summary(session: Session, *, institution_id: UUID, student_id: UUID) -> AdminStudentSummary:
    student=session.scalar(select(Student).options(joinedload(Student.user),joinedload(Student.programme)).where(Student.id==student_id,Student.institution_id==institution_id))
    if student is None: raise AdminPortalStudentNotFoundError()
    registration_count=_count(session,CourseRegistration,institution_id,CourseRegistration.student_id==student.id,CourseRegistration.status=="active")
    attendance=session.execute(select(func.count(AttendanceRecord.id),func.sum(case((AttendanceRecord.attendance_status=="present",1),else_=0)),func.sum(case((AttendanceRecord.attendance_status=="absent",1),else_=0)),func.sum(case((AttendanceRecord.attendance_status=="late",1),else_=0))).join(CourseRegistration,AttendanceRecord.course_registration_id==CourseRegistration.id).where(AttendanceRecord.institution_id==institution_id,CourseRegistration.student_id==student.id,AttendanceRecord.status=="active")).one()
    performance=progression=eligibility=clearance=None
    try: performance=get_student_academic_progress(session,institution_id=institution_id,student_id=student.id); progression=performance.progression
    except Exception: pass
    try: eligibility=evaluate_student_graduation_eligibility(session,institution_id=institution_id,student_id=student.id)
    except Exception: pass
    try: clearance=compute_student_clearance_summary(session,institution_id=institution_id,student_id=student.id)
    except Exception: pass
    transcript_status=session.scalar(select(OfficialTranscript.status).where(OfficialTranscript.institution_id==institution_id,OfficialTranscript.student_id==student.id).order_by(OfficialTranscript.generated_at.desc()).limit(1))
    graduation_status=session.scalar(select(GraduationRecord.status).where(GraduationRecord.institution_id==institution_id,GraduationRecord.student_id==student.id).order_by(GraduationRecord.prepared_at.desc()).limit(1))
    docs=Counter(session.scalars(select(AcademicDocument.status).where(AcademicDocument.institution_id==institution_id,AcademicDocument.student_id==student.id)).all())
    u=student.user; p=student.programme
    return AdminStudentSummary(student_id=student.id,identity={"matriculation_number":student.matriculation_number,"first_name":u.first_name,"last_name":u.last_name,"full_name":f"{u.first_name} {u.last_name}".strip(),"email":u.email},programme={"id":p.id,"name":p.name,"code":p.code} if p else None,current_level=student.current_level,enrollment_status=student.enrollment_status,course_registration_count=registration_count,attendance_headline={"total":attendance[0] or 0,"present":attendance[1] or 0,"absent":attendance[2] or 0,"late":attendance[3] or 0},academic_performance=performance,progression=progression,graduation_eligibility=eligibility,clearance=clearance,transcript_status=transcript_status,graduation_status=graduation_status,document_statuses=dict(docs))


def offering_summary(session: Session, *, institution_id: UUID, course_offering_id: UUID) -> AdminCourseOfferingSummary:
    offering=session.scalar(select(CourseOffering).options(joinedload(CourseOffering.course),joinedload(CourseOffering.academic_session),joinedload(CourseOffering.semester)).where(CourseOffering.id==course_offering_id,CourseOffering.institution_id==institution_id))
    if offering is None: raise AdminPortalOfferingNotFoundError()
    assignments=session.execute(select(LecturerAssignment,Lecturer,User).join(Lecturer,LecturerAssignment.lecturer_id==Lecturer.id).join(User,Lecturer.user_id==User.id).where(LecturerAssignment.institution_id==institution_id,LecturerAssignment.course_offering_id==offering.id,LecturerAssignment.status=="active")).all()
    attendance=session.execute(select(func.count(AttendanceRecord.id),func.sum(case((AttendanceRecord.attendance_status=="present",1),else_=0)),func.sum(case((AttendanceRecord.attendance_status=="absent",1),else_=0)),func.sum(case((AttendanceRecord.attendance_status=="late",1),else_=0))).join(CourseRegistration,AttendanceRecord.course_registration_id==CourseRegistration.id).where(AttendanceRecord.institution_id==institution_id,CourseRegistration.course_offering_id==offering.id,AttendanceRecord.status=="active")).one()
    statuses=dict(session.execute(select(Result.status,func.count(Result.id)).where(Result.institution_id==institution_id,Result.course_offering_id==offering.id).group_by(Result.status)).all())
    return AdminCourseOfferingSummary(course_offering_id=offering.id,course={"id":offering.course.id,"code":offering.course.code,"title":offering.course.title,"credit_units":offering.course.credit_units},academic_session={"id":offering.academic_session.id,"name":offering.academic_session.name},semester={"id":offering.semester.id,"name":offering.semester.name},lecturer_assignments=[{"lecturer_assignment_id":a.id,"lecturer_id":l.id,"staff_number":l.staff_number,"name":f"{u.first_name} {u.last_name}".strip(),"role":a.assignment_role,"status":a.status} for a,l,u in assignments],registered_student_count=_count(session,CourseRegistration,institution_id,CourseRegistration.course_offering_id==offering.id,CourseRegistration.status=="active",CourseRegistration.registration_status=="registered"),class_session_count=_count(session,ClassSession,institution_id,ClassSession.course_offering_id==offering.id,ClassSession.status!="cancelled"),attendance_headline={"total":attendance[0] or 0,"present":attendance[1] or 0,"absent":attendance[2] or 0,"late":attendance[3] or 0},assessment_component_count=_count(session,AssessmentComponent,institution_id,AssessmentComponent.course_offering_id==offering.id,AssessmentComponent.status!="inactive"),examination_count=_count(session,Examination,institution_id,Examination.course_offering_id==offering.id,Examination.status!="inactive"),result_status_summary=statuses)
