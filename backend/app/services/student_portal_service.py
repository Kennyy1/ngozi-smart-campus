from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.academic_document import AcademicDocument
from app.models.academic_session import AcademicSession
from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.programme import Programme
from app.models.result import Result
from app.models.semester import Semester
from app.models.student import Student
from app.models.user import User
from app.schemas.student_portal import (
    AttendanceSummary, StudentAcademicPerformance, StudentCourse, StudentDashboard,
    StudentDocument, StudentProfile, StudentResult,
)
from app.services.academic_performance_service import compute_student_cgpa, compute_student_semester_gpa
from app.services.academic_progression_service import get_student_academic_progress
from app.services.clearance_service import compute_student_clearance_summary
from app.services.graduation_eligibility_service import evaluate_student_graduation_eligibility
from app.services.transcript_service import compute_student_transcript


class StudentPortalProfileNotFoundError(Exception):
    pass


def resolve_student(session: Session, *, institution_id: UUID, user_id: UUID) -> Student:
    student = session.scalar(
        select(Student).options(joinedload(Student.user), joinedload(Student.programme)).where(
            Student.user_id == user_id, Student.institution_id == institution_id
        )
    )
    if student is None:
        raise StudentPortalProfileNotFoundError()
    return student


def get_profile(session: Session, *, institution_id: UUID, user_id: UUID) -> StudentProfile:
    return _profile(resolve_student(session, institution_id=institution_id, user_id=user_id))


def list_courses(session: Session, *, institution_id: UUID, user_id: UUID,
                 academic_session_id: UUID | None = None, semester_id: UUID | None = None,
                 registration_status: str | None = None) -> list[StudentCourse]:
    student = resolve_student(session, institution_id=institution_id, user_id=user_id)
    statement = (select(CourseRegistration, CourseOffering, Course, Semester, AcademicSession)
        .join(CourseOffering, CourseRegistration.course_offering_id == CourseOffering.id)
        .join(Course, CourseOffering.course_id == Course.id)
        .join(Semester, CourseOffering.semester_id == Semester.id)
        .join(AcademicSession, CourseOffering.academic_session_id == AcademicSession.id)
        .where(CourseRegistration.institution_id == institution_id, CourseRegistration.student_id == student.id,
               CourseRegistration.status != "inactive"))
    if academic_session_id: statement = statement.where(CourseOffering.academic_session_id == academic_session_id)
    if semester_id: statement = statement.where(CourseOffering.semester_id == semester_id)
    if registration_status: statement = statement.where(CourseRegistration.registration_status == registration_status)
    return [StudentCourse(course_registration_id=r.id, course_offering_id=o.id, course_id=c.id,
        course_code=c.code, title=c.title, credit_units=c.credit_units, course_type=c.course_type,
        semester_id=sem.id, semester=sem.name, academic_session_id=a.id, academic_session=a.name,
        registration_status=r.registration_status) for r, o, c, sem, a in session.execute(statement).all()]


def list_attendance(session: Session, *, institution_id: UUID, user_id: UUID) -> list[AttendanceSummary]:
    student = resolve_student(session, institution_id=institution_id, user_id=user_id)
    rows = session.execute(
        select(CourseRegistration.id, CourseOffering.id, Course.code, Course.title,
               func.count(AttendanceRecord.id),
               func.sum(case((AttendanceRecord.attendance_status == "present", 1), else_=0)),
               func.sum(case((AttendanceRecord.attendance_status == "absent", 1), else_=0)),
               func.sum(case((AttendanceRecord.attendance_status == "late", 1), else_=0)))
        .join(CourseOffering, CourseRegistration.course_offering_id == CourseOffering.id)
        .join(Course, CourseOffering.course_id == Course.id)
        .outerjoin(AttendanceRecord, (AttendanceRecord.course_registration_id == CourseRegistration.id) & (AttendanceRecord.status == "active"))
        .where(CourseRegistration.institution_id == institution_id, CourseRegistration.student_id == student.id,
               CourseRegistration.status == "active", CourseRegistration.registration_status == "registered")
        .group_by(CourseRegistration.id, CourseOffering.id, Course.code, Course.title)
    ).all()
    result = []
    for _, offering_id, code, title, total, present, absent, late in rows:
        total, present, absent, late = total or 0, present or 0, absent or 0, late or 0
        percentage = (Decimal(present + late) * 100 / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total else Decimal("0.00")
        result.append(AttendanceSummary(course_offering_id=offering_id, course_code=code, course_title=title,
            total_sessions=total, present_count=present, absent_count=absent, late_count=late,
            attendance_percentage=percentage))
    return result


def list_results(session: Session, *, institution_id: UUID, user_id: UUID,
                 academic_session_id: UUID | None = None, semester_id: UUID | None = None) -> list[StudentResult]:
    student = resolve_student(session, institution_id=institution_id, user_id=user_id)
    statement = (select(Result, CourseOffering, Course, AcademicSession, Semester)
        .join(CourseOffering, Result.course_offering_id == CourseOffering.id).join(Course, CourseOffering.course_id == Course.id)
        .join(AcademicSession, CourseOffering.academic_session_id == AcademicSession.id).join(Semester, CourseOffering.semester_id == Semester.id)
        .where(Result.institution_id == institution_id, Result.student_id == student.id, Result.status == "published"))
    if academic_session_id: statement = statement.where(CourseOffering.academic_session_id == academic_session_id)
    if semester_id: statement = statement.where(CourseOffering.semester_id == semester_id)
    return [StudentResult(result_id=r.id, course_offering_id=o.id, course_code=c.code, course_title=c.title,
        academic_session_id=a.id, academic_session=a.name, semester_id=sem.id, semester=sem.name,
        credit_units=c.credit_units, final_score=r.final_score, grade=r.grade_letter,
        grade_point=r.grade_point, passed=r.passed) for r, o, c, a, sem in session.execute(statement).all()]


def get_academic_performance(session: Session, *, institution_id: UUID, user_id: UUID) -> StudentAcademicPerformance:
    student = resolve_student(session, institution_id=institution_id, user_id=user_id)
    progress = get_student_academic_progress(session, institution_id=institution_id, student_id=student.id)
    current_semester = session.scalar(select(Semester).where(Semester.institution_id == institution_id, Semester.is_current.is_(True)))
    current_gpa = compute_student_semester_gpa(session, institution_id=institution_id, student_id=student.id, semester_id=current_semester.id).gpa if current_semester else None
    return StudentAcademicPerformance(current_gpa=current_gpa, cgpa=progress.cgpa,
        cumulative_attempted_units=progress.cumulative_attempted_units,
        cumulative_earned_units=progress.cumulative_earned_units, academic_standing=progress.academic_standing,
        progression_summary=progress.progression, failed_courses=progress.failed_courses)


def list_documents(session: Session, *, institution_id: UUID, user_id: UUID) -> list[StudentDocument]:
    student = resolve_student(session, institution_id=institution_id, user_id=user_id)
    items = session.scalars(select(AcademicDocument).where(AcademicDocument.institution_id == institution_id,
        AcademicDocument.student_id == student.id, AcademicDocument.status != "inactive").order_by(AcademicDocument.generated_at.desc())).all()
    return [StudentDocument(document_id=x.id, type=x.document_type, reference=x.document_reference,
        status=x.status, issued_at=x.issued_at, verification_code=x.verification_code) for x in items]


def get_dashboard(session: Session, *, institution_id: UUID, user_id: UUID) -> StudentDashboard:
    student = resolve_student(session, institution_id=institution_id, user_id=user_id)
    profile = _profile(student)
    current_session = session.scalar(select(AcademicSession).where(AcademicSession.institution_id == institution_id, AcademicSession.is_current.is_(True)))
    current_semester = session.scalar(select(Semester).where(Semester.institution_id == institution_id, Semester.is_current.is_(True)))
    courses = list_courses(session, institution_id=institution_id, user_id=user_id,
                           academic_session_id=current_session.id if current_session else None)
    attendance = list_attendance(session, institution_id=institution_id, user_id=user_id)
    performance = clearance = graduation = None
    try: performance = get_academic_performance(session, institution_id=institution_id, user_id=user_id)
    except Exception: pass
    try: clearance = compute_student_clearance_summary(session, institution_id=institution_id, student_id=student.id)
    except Exception: pass
    try: graduation = evaluate_student_graduation_eligibility(session, institution_id=institution_id, student_id=student.id)
    except Exception: pass
    total = sum(x.total_sessions for x in attendance); present = sum(x.present_count for x in attendance)
    return StudentDashboard(**profile.model_dump(), current_academic_session=current_session.name if current_session else None,
        current_semester=current_semester.name if current_semester else None, registered_course_count=len(courses),
        active_course_count=sum(x.registration_status == "registered" for x in courses),
        attendance_summary={"total_sessions": total, "present_count": present},
        current_gpa=performance.current_gpa if performance else None, cgpa=performance.cgpa if performance else None,
        academic_standing=performance.academic_standing if performance else None,
        progression_summary=performance.progression_summary if performance else None,
        clearance_summary=clearance, graduation_summary=graduation)


def _profile(student: Student) -> StudentProfile:
    user: User = student.user; programme: Programme | None = student.programme
    return StudentProfile(student_id=student.id, matriculation_number=student.matriculation_number,
        first_name=user.first_name, last_name=user.last_name, full_name=f"{user.first_name} {user.last_name}".strip(),
        email=user.email, phone=user.phone, programme_id=programme.id if programme else None,
        programme_name=programme.name if programme else None, programme_code=programme.code if programme else None,
        current_level=student.current_level, admission_year=student.admission_year, enrollment_status=student.enrollment_status)


get_transcript = compute_student_transcript
get_clearance = compute_student_clearance_summary
