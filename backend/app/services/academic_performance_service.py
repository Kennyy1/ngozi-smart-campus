from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_session import AcademicSession
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.result import Result
from app.models.semester import Semester
from app.models.student import Student
from app.schemas.academic_performance import CGPAResult, CourseGradePointBreakdown, SemesterGPAResult


TWO_PLACES = Decimal("0.01")


class AcademicPerformanceStudentNotFoundError(Exception): pass
class AcademicPerformanceSemesterNotFoundError(Exception): pass
class AcademicPerformanceSessionNotFoundError(Exception): pass
class InvalidCourseCreditUnitsError(Exception): pass


class PerformanceRecord(NamedTuple):
    result: Result
    registration: CourseRegistration
    offering: CourseOffering
    course: Course
    semester: Semester
    academic_session: AcademicSession


def compute_student_semester_gpa(session: Session, *, institution_id: UUID, student_id: UUID, semester_id: UUID) -> SemesterGPAResult:
    student = _resolve_student(session, institution_id=institution_id, student_id=student_id)
    semester = _resolve_semester(session, institution_id=institution_id, semester_id=semester_id)
    academic_session = _resolve_academic_session(session, institution_id=institution_id, academic_session_id=semester.academic_session_id)
    records = _query_eligible_published_results(session, institution_id=institution_id, student_id=student.id, semester_id=semester.id)
    return _build_semester_summary(student.id, academic_session.id, semester.id, records)


def compute_student_cgpa(session: Session, *, institution_id: UUID, student_id: UUID) -> CGPAResult:
    student = _resolve_student(session, institution_id=institution_id, student_id=student_id)
    records = _query_eligible_published_results(session, institution_id=institution_id, student_id=student.id)
    grouped: dict[tuple[UUID, UUID], list[PerformanceRecord]] = defaultdict(list)
    ordering: dict[tuple[UUID, UUID], tuple[object, int]] = {}
    for record in records:
        key = (record.academic_session.id, record.semester.id)
        grouped[key].append(record)
        ordering[key] = (record.academic_session.start_date, record.semester.sequence_number)
    summaries = [
        _build_semester_summary(student.id, session_id, semester_id, grouped[(session_id, semester_id)])
        for session_id, semester_id in sorted(grouped, key=lambda key: ordering[key])
    ]
    attempted = sum(item.attempted_units for item in summaries)
    earned = sum(item.earned_units for item in summaries)
    quality = sum((item.total_quality_points for item in summaries), Decimal("0"))
    total_courses = sum(item.course_count for item in summaries)
    passed = sum(item.passed_courses for item in summaries)
    return CGPAResult(
        student_id=student.id, cumulative_attempted_units=attempted, cumulative_earned_units=earned,
        cumulative_quality_points=_rounded(quality), total_courses=total_courses,
        passed_courses=passed, failed_courses=total_courses - passed,
        cgpa=_average(quality, attempted), semester_summaries=summaries,
    )


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    item = session.scalar(select(Student).where(Student.id == student_id, Student.institution_id == institution_id))
    if item is None: raise AcademicPerformanceStudentNotFoundError()
    return item


def _resolve_semester(session: Session, *, institution_id: UUID, semester_id: UUID) -> Semester:
    item = session.scalar(select(Semester).where(Semester.id == semester_id, Semester.institution_id == institution_id))
    if item is None: raise AcademicPerformanceSemesterNotFoundError()
    return item


def _resolve_academic_session(session: Session, *, institution_id: UUID, academic_session_id: UUID) -> AcademicSession:
    item = session.scalar(select(AcademicSession).where(AcademicSession.id == academic_session_id, AcademicSession.institution_id == institution_id))
    if item is None: raise AcademicPerformanceSessionNotFoundError()
    return item


def _query_eligible_published_results(session: Session, *, institution_id: UUID, student_id: UUID, semester_id: UUID | None = None) -> list[PerformanceRecord]:
    statement = (
        select(Result, CourseRegistration, CourseOffering, Course, Semester, AcademicSession)
        .join(CourseRegistration, Result.course_registration_id == CourseRegistration.id)
        .join(CourseOffering, Result.course_offering_id == CourseOffering.id)
        .join(Course, CourseOffering.course_id == Course.id)
        .join(Semester, CourseOffering.semester_id == Semester.id)
        .join(AcademicSession, CourseOffering.academic_session_id == AcademicSession.id)
        .where(
            Result.institution_id == institution_id, Result.student_id == student_id, Result.status == "published",
            CourseRegistration.institution_id == institution_id,
            CourseRegistration.registration_status == "registered",
            CourseRegistration.status.in_(("active", "inactive")),
            CourseOffering.institution_id == institution_id, Course.institution_id == institution_id,
            Semester.institution_id == institution_id, AcademicSession.institution_id == institution_id,
        )
    )
    if semester_id is not None: statement = statement.where(CourseOffering.semester_id == semester_id)
    return [PerformanceRecord(*row) for row in session.execute(statement).all()]


def _build_semester_summary(student_id: UUID, academic_session_id: UUID, semester_id: UUID, records: Sequence[PerformanceRecord]) -> SemesterGPAResult:
    courses = [_build_course_breakdown(record) for record in records]
    attempted = sum(item.credit_units for item in courses)
    earned = sum(item.credit_units for item in courses if item.passed)
    quality = sum((item.quality_points for item in courses), Decimal("0"))
    passed = sum(item.passed for item in courses)
    return SemesterGPAResult(
        student_id=student_id, academic_session_id=academic_session_id, semester_id=semester_id,
        attempted_units=attempted, earned_units=earned, total_quality_points=_rounded(quality),
        course_count=len(courses), passed_courses=passed, failed_courses=len(courses) - passed,
        gpa=_average(quality, attempted), courses=courses,
    )


def _build_course_breakdown(record: PerformanceRecord) -> CourseGradePointBreakdown:
    units = record.course.credit_units
    if units <= 0: raise InvalidCourseCreditUnitsError()
    quality = Decimal(record.result.grade_point) * Decimal(units)
    return CourseGradePointBreakdown(
        result_id=record.result.id, course_registration_id=record.registration.id,
        course_offering_id=record.offering.id, course_id=record.course.id,
        course_code=record.course.code, course_title=record.course.title, credit_units=units,
        final_score=_rounded(Decimal(record.result.final_score)), grade_letter=record.result.grade_letter,
        grade_point=_rounded(Decimal(record.result.grade_point)), passed=record.result.passed,
        quality_points=_rounded(quality),
    )


def _average(quality_points: Decimal, attempted_units: int) -> Decimal:
    if attempted_units == 0: return Decimal("0.00")
    return _rounded(quality_points / Decimal(attempted_units))


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
