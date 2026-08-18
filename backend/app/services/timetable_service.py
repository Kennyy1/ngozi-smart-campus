from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.class_session import ClassSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.student import Student

def _row(s,code,title):
    return dict(id=s.id,course_code=code,course_title=title,date=s.session_date,start_time=s.start_time,end_time=s.end_time,venue=s.venue,session_type=s.session_type,status=s.status,topic=s.topic)
def student_timetable(session:Session,institution_id,user_id):
    student=session.scalar(select(Student).where(Student.institution_id==institution_id,Student.user_id==user_id))
    if not student:return []
    rows=session.execute(select(ClassSession,Course.code,Course.title).join(CourseOffering,ClassSession.course_offering_id==CourseOffering.id).join(Course,CourseOffering.course_id==Course.id).join(CourseRegistration,CourseRegistration.course_offering_id==CourseOffering.id).where(ClassSession.institution_id==institution_id,CourseRegistration.student_id==student.id,CourseRegistration.status=="active",CourseRegistration.registration_status=="registered",CourseOffering.status=="active").order_by(ClassSession.session_date,ClassSession.start_time)).all()
    return [_row(*r) for r in rows]
def lecturer_timetable(session:Session,institution_id,user_id):
    lecturer=session.scalar(select(Lecturer).where(Lecturer.institution_id==institution_id,Lecturer.user_id==user_id))
    if not lecturer:return []
    rows=session.execute(select(ClassSession,Course.code,Course.title).join(CourseOffering,ClassSession.course_offering_id==CourseOffering.id).join(Course,CourseOffering.course_id==Course.id).join(LecturerAssignment,ClassSession.lecturer_assignment_id==LecturerAssignment.id).where(ClassSession.institution_id==institution_id,LecturerAssignment.lecturer_id==lecturer.id,LecturerAssignment.status=="active",CourseOffering.status=="active").order_by(ClassSession.session_date,ClassSession.start_time)).all()
    return [_row(*r) for r in rows]
