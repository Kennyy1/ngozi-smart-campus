from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_level import AcademicLevel
from app.models.programme import Programme
from app.models.student import Student
from app.schemas.academic_progression import (
    AcademicStandingSummary, FailedCourseSummary, ProgressionEvaluation,
    StudentAcademicProgressSummary,
)
from app.services.academic_performance_service import (
    PerformanceRecord, _query_eligible_published_results, compute_student_cgpa,
)
from app.services.academic_progression_policy import (
    ProgressionReason, determine_academic_standing, determine_progression_reason,
)


class AcademicProgressionStudentNotFoundError(Exception): pass
class AcademicProgressionProgrammeNotFoundError(Exception): pass


def compute_student_academic_standing(session: Session, *, institution_id: UUID, student_id: UUID) -> AcademicStandingSummary:
    student, programme = _resolve_student_programme(session, institution_id=institution_id, student_id=student_id)
    cgpa = compute_student_cgpa(session, institution_id=institution_id, student_id=student.id)
    failed = _query_published_failed_results(session, institution_id=institution_id, student_id=student.id)
    standing = determine_academic_standing(cgpa=cgpa.cgpa, has_published_results=cgpa.total_courses > 0)
    return AcademicStandingSummary(
        student_id=student.id, programme_id=programme.id, current_level=student.current_level,
        cumulative_attempted_units=cgpa.cumulative_attempted_units,
        cumulative_earned_units=cgpa.cumulative_earned_units,
        cumulative_quality_points=cgpa.cumulative_quality_points, cgpa=cgpa.cgpa,
        standing=standing, failed_course_count=len(failed),
        failed_course_ids=[record.course.id for record in failed],
        failed_course_codes=[record.course.code for record in failed],
        failed_credit_units=sum(record.course.credit_units for record in failed),
        has_carryover_courses=bool(failed),
    )


def evaluate_student_progression(session: Session, *, institution_id: UUID, student_id: UUID) -> ProgressionEvaluation:
    student, programme = _resolve_student_programme(session, institution_id=institution_id, student_id=student_id)
    cgpa = compute_student_cgpa(session, institution_id=institution_id, student_id=student.id)
    failed = _query_published_failed_results(session, institution_id=institution_id, student_id=student.id)
    current = _resolve_current_academic_level(session, institution_id=institution_id, programme_id=programme.id, current_level=student.current_level)
    next_level = _resolve_next_academic_level(session, institution_id=institution_id, programme_id=programme.id, current=current) if current else None
    final = bool(current and _is_final_academic_level(programme=programme, current=current))
    standing = determine_academic_standing(cgpa=cgpa.cgpa, has_published_results=cgpa.total_courses > 0)
    reason = determine_progression_reason(
        cgpa=cgpa.cgpa, standing=standing, current_level_resolved=current is not None,
        next_level_exists=next_level is not None, final_level_reached=final,
        has_published_results=cgpa.total_courses > 0,
    )
    return ProgressionEvaluation(
        student_id=student.id, programme_id=programme.id,
        current_academic_level_id=current.id if current else None, current_level=student.current_level,
        current_level_sequence=current.sequence_number if current else None,
        next_academic_level_id=next_level.id if next_level else None,
        next_level=next_level.name if next_level else None,
        next_level_sequence=next_level.sequence_number if next_level else None,
        cgpa=cgpa.cgpa, academic_standing=standing, has_carryover_courses=bool(failed),
        failed_course_count=len(failed), eligible_for_progression=reason == ProgressionReason.ELIGIBLE,
        progression_reason=reason,
    )


def get_student_academic_progress(session: Session, *, institution_id: UUID, student_id: UUID) -> StudentAcademicProgressSummary:
    student, programme = _resolve_student_programme(session, institution_id=institution_id, student_id=student_id)
    cgpa = compute_student_cgpa(session, institution_id=institution_id, student_id=student.id)
    failed_records = _query_published_failed_results(session, institution_id=institution_id, student_id=student.id)
    progression = evaluate_student_progression(session, institution_id=institution_id, student_id=student.id)
    return StudentAcademicProgressSummary(
        student_id=student.id, programme_id=programme.id, current_level=student.current_level,
        academic_standing=progression.academic_standing, cgpa=cgpa.cgpa,
        cumulative_attempted_units=cgpa.cumulative_attempted_units,
        cumulative_earned_units=cgpa.cumulative_earned_units,
        failed_courses=[_build_failed_course(record) for record in failed_records],
        progression=progression, semester_summaries=cgpa.semester_summaries,
    )


def _resolve_student_programme(session: Session, *, institution_id: UUID, student_id: UUID) -> tuple[Student, Programme]:
    student = session.scalar(select(Student).where(Student.id == student_id, Student.institution_id == institution_id))
    if student is None:
        raise AcademicProgressionStudentNotFoundError()
    programme = session.scalar(select(Programme).where(Programme.id == student.programme_id, Programme.institution_id == institution_id))
    if programme is None:
        raise AcademicProgressionProgrammeNotFoundError()
    return student, programme


def _resolve_current_academic_level(session: Session, *, institution_id: UUID, programme_id: UUID, current_level: str | None) -> AcademicLevel | None:
    if current_level is None:
        return None
    return session.scalar(select(AcademicLevel).where(
        AcademicLevel.institution_id == institution_id, AcademicLevel.programme_id == programme_id,
        AcademicLevel.name == current_level, AcademicLevel.status == "active",
    ))


def _resolve_next_academic_level(session: Session, *, institution_id: UUID, programme_id: UUID, current: AcademicLevel) -> AcademicLevel | None:
    return session.scalar(select(AcademicLevel).where(
        AcademicLevel.institution_id == institution_id, AcademicLevel.programme_id == programme_id,
        AcademicLevel.status == "active", AcademicLevel.sequence_number > current.sequence_number,
    ).order_by(AcademicLevel.sequence_number).limit(1))


def _is_final_academic_level(*, programme: Programme, current: AcademicLevel) -> bool:
    # Programme duration is the existing indication that the configured level is terminal.
    # A missing successor before that point is reported separately as a configuration gap.
    return current.sequence_number >= programme.duration_years


def _query_published_failed_results(session: Session, *, institution_id: UUID, student_id: UUID) -> list[PerformanceRecord]:
    return [record for record in _query_eligible_published_results(session, institution_id=institution_id, student_id=student_id) if not record.result.passed]


def _build_failed_course(record: PerformanceRecord) -> FailedCourseSummary:
    return FailedCourseSummary(
        result_id=record.result.id, course_registration_id=record.registration.id,
        course_offering_id=record.offering.id, course_id=record.course.id,
        course_code=record.course.code, course_title=record.course.title,
        credit_units=record.course.credit_units, grade_letter=record.result.grade_letter,
        grade_point=record.result.grade_point, final_score=record.result.final_score,
    )
