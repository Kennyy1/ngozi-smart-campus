from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.programme import Programme
from app.models.student import Student
from app.schemas.transcript import (
    StudentTranscriptSummary, TranscriptAcademicSessionHistory,
    TranscriptCourseResult, TranscriptSemesterHistory,
)
from app.services.academic_performance_service import (
    PerformanceRecord, _build_semester_summary, _query_eligible_published_results,
)
from app.services.academic_progression_service import compute_student_academic_standing
from app.services.attendance_analytics_service import _student_display_name


class TranscriptStudentNotFoundError(Exception): pass
class TranscriptProgrammeNotFoundError(Exception): pass


def compute_student_transcript(session: Session, *, institution_id: UUID, student_id: UUID) -> StudentTranscriptSummary:
    student = _resolve_student(session, institution_id=institution_id, student_id=student_id)
    programme = _resolve_programme(session, institution_id=institution_id, programme_id=student.programme_id)
    records = _query_eligible_published_results(session, institution_id=institution_id, student_id=student.id)
    standing = compute_student_academic_standing(session, institution_id=institution_id, student_id=student.id)
    return StudentTranscriptSummary(
        student_id=student.id, matriculation_number=student.matriculation_number,
        student_name=_student_display_name(student), programme_id=programme.id,
        programme_name=programme.name, programme_code=programme.code,
        current_level=student.current_level, admission_year=student.admission_year,
        enrollment_status=student.enrollment_status,
        cumulative_attempted_units=standing.cumulative_attempted_units,
        cumulative_earned_units=standing.cumulative_earned_units,
        cumulative_quality_points=standing.cumulative_quality_points,
        total_courses=len(records),
        passed_courses=sum(record.result.passed for record in records),
        failed_courses=sum(not record.result.passed for record in records), cgpa=standing.cgpa,
        academic_standing=standing.standing, academic_sessions=_build_academic_sessions(records),
    )


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    student = session.scalar(select(Student).options(joinedload(Student.user)).where(
        Student.id == student_id, Student.institution_id == institution_id,
    ))
    if student is None:
        raise TranscriptStudentNotFoundError()
    return student


def _resolve_programme(session: Session, *, institution_id: UUID, programme_id: UUID | None) -> Programme:
    programme = session.scalar(select(Programme).where(
        Programme.id == programme_id, Programme.institution_id == institution_id,
    ))
    if programme is None:
        raise TranscriptProgrammeNotFoundError()
    return programme


def standing_to_semesters(records: Sequence[PerformanceRecord]) -> list[TranscriptSemesterHistory]:
    grouped: dict[tuple[UUID, UUID], list[PerformanceRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.academic_session.id, record.semester.id)].append(record)
    histories: list[TranscriptSemesterHistory] = []
    for items in grouped.values():
        first = items[0]
        summary = _build_semester_summary(
            first.result.student_id, first.academic_session.id, first.semester.id, items,
        )
        histories.append(TranscriptSemesterHistory(
            semester_id=first.semester.id, semester_name=first.semester.name,
            semester_sequence_number=first.semester.sequence_number,
            academic_session_id=first.academic_session.id,
            academic_session_name=first.academic_session.name,
            attempted_units=summary.attempted_units, earned_units=summary.earned_units,
            total_quality_points=summary.total_quality_points, course_count=summary.course_count,
            passed_courses=summary.passed_courses, failed_courses=summary.failed_courses,
            gpa=summary.gpa,
            courses=sorted((_build_course_result(item) for item in items), key=lambda item: (item.course_code, item.result_id.hex)),
        ))
    return histories


def _build_academic_sessions(records: Sequence[PerformanceRecord]) -> list[TranscriptAcademicSessionHistory]:
    semesters = standing_to_semesters(records)
    session_records: dict[UUID, list[PerformanceRecord]] = defaultdict(list)
    session_semesters: dict[UUID, list[TranscriptSemesterHistory]] = defaultdict(list)
    for record in records:
        session_records[record.academic_session.id].append(record)
    for semester in semesters:
        session_semesters[semester.academic_session_id].append(semester)
    histories: list[TranscriptAcademicSessionHistory] = []
    for academic_session_id, items in session_records.items():
        first = items[0].academic_session
        grouped_semesters = sorted(session_semesters[academic_session_id], key=lambda item: (item.semester_sequence_number, item.semester_id.hex))
        histories.append(TranscriptAcademicSessionHistory(
            academic_session_id=first.id, academic_session_name=first.name,
            start_date=first.start_date, end_date=first.end_date,
            session_attempted_units=sum(item.attempted_units for item in grouped_semesters),
            session_earned_units=sum(item.earned_units for item in grouped_semesters),
            session_quality_points=sum((item.total_quality_points for item in grouped_semesters), start=Decimal("0")),
            session_course_count=sum(item.course_count for item in grouped_semesters),
            session_passed_courses=sum(item.passed_courses for item in grouped_semesters),
            session_failed_courses=sum(item.failed_courses for item in grouped_semesters),
            semesters=grouped_semesters,
        ))
    return sorted(histories, key=lambda item: (item.start_date, item.academic_session_id.hex))


def _build_course_result(record: PerformanceRecord) -> TranscriptCourseResult:
    summary = _build_semester_summary(
        record.result.student_id, record.academic_session.id, record.semester.id, [record],
    ).courses[0]
    return TranscriptCourseResult(
        result_id=summary.result_id, course_registration_id=summary.course_registration_id,
        course_offering_id=summary.course_offering_id, course_id=summary.course_id,
        course_code=summary.course_code, course_title=summary.course_title,
        credit_units=summary.credit_units, final_score=summary.final_score,
        grade_letter=summary.grade_letter, grade_point=summary.grade_point,
        passed=summary.passed, quality_points=summary.quality_points,
    )
