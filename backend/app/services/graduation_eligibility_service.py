from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.academic_level import AcademicLevel
from app.models.programme import Programme
from app.models.student import Student
from app.schemas.graduation_eligibility import GraduationCourseDeficiency, GraduationEligibilityEvaluation
from app.services.academic_performance_service import PerformanceRecord, _query_eligible_published_results, compute_student_cgpa
from app.services.academic_progression_service import compute_student_academic_standing, _resolve_current_academic_level
from app.services.attendance_analytics_service import _student_display_name
from app.services.graduation_policy import MINIMUM_GRADUATION_CGPA, evaluate_graduation_policy


class GraduationEligibilityStudentNotFoundError(Exception): pass
class GraduationEligibilityProgrammeNotFoundError(Exception): pass


def evaluate_student_graduation_eligibility(session: Session, *, institution_id: UUID, student_id: UUID) -> GraduationEligibilityEvaluation:
    student = _resolve_student(session, institution_id=institution_id, student_id=student_id)
    programme = _resolve_programme(session, institution_id=institution_id, programme_id=student.programme_id)
    current = _resolve_current_academic_level(session, institution_id=institution_id, programme_id=programme.id, current_level=student.current_level)
    final = _resolve_final_academic_level(session, institution_id=institution_id, programme_id=programme.id)
    cgpa = compute_student_cgpa(session, institution_id=institution_id, student_id=student.id)
    standing = compute_student_academic_standing(session, institution_id=institution_id, student_id=student.id)
    records = _query_eligible_published_results(session, institution_id=institution_id, student_id=student.id)
    outstanding = _resolve_outstanding_failed_courses(records)
    has_results = bool(records)
    final_reached = bool(current and final and current.sequence_number >= final.sequence_number)
    minimum_units = _resolve_minimum_required_units(programme)
    eligible, reasons = evaluate_graduation_policy(
        has_published_results=has_results, current_level_resolved=current is not None,
        final_level_reached=final_reached, outstanding_failed_course_count=len(outstanding),
        cgpa=cgpa.cgpa, academic_standing=standing.standing,
        enrollment_status=student.enrollment_status, minimum_required_units=minimum_units,
        cumulative_earned_units=cgpa.cumulative_earned_units,
    )
    return GraduationEligibilityEvaluation(
        student_id=student.id, matriculation_number=student.matriculation_number,
        student_name=_student_display_name(student), programme_id=programme.id,
        programme_name=programme.name, programme_code=programme.code,
        current_academic_level_id=current.id if current else None, current_level=student.current_level,
        current_level_sequence=current.sequence_number if current else None,
        final_academic_level_id=final.id if final else None, final_level=final.name if final else None,
        final_level_sequence=final.sequence_number if final else None,
        cumulative_attempted_units=cgpa.cumulative_attempted_units,
        cumulative_earned_units=cgpa.cumulative_earned_units,
        minimum_required_units=minimum_units, credit_requirement_configured=minimum_units is not None,
        curriculum_completion_verified=False, cgpa=cgpa.cgpa,
        minimum_graduation_cgpa=MINIMUM_GRADUATION_CGPA,
        academic_standing=standing.standing, total_published_courses=len(records),
        passed_course_count=sum(record.result.passed for record in records),
        outstanding_failed_course_count=len(outstanding),
        outstanding_failed_credit_units=sum(item.credit_units for item in outstanding),
        outstanding_courses=outstanding, final_level_reached=final_reached,
        meets_cgpa_requirement=has_results and cgpa.cgpa >= MINIMUM_GRADUATION_CGPA,
        meets_credit_requirement=None if minimum_units is None else cgpa.cumulative_earned_units >= minimum_units,
        has_published_results=has_results, eligible_for_graduation=eligible,
        eligibility_reasons=reasons,
    )


def _resolve_student(session: Session, *, institution_id: UUID, student_id: UUID) -> Student:
    item = session.scalar(select(Student).options(joinedload(Student.user)).where(Student.id == student_id, Student.institution_id == institution_id))
    if item is None:
        raise GraduationEligibilityStudentNotFoundError()
    return item


def _resolve_programme(session: Session, *, institution_id: UUID, programme_id: UUID | None) -> Programme:
    item = session.scalar(select(Programme).where(Programme.id == programme_id, Programme.institution_id == institution_id))
    if item is None:
        raise GraduationEligibilityProgrammeNotFoundError()
    return item


def _resolve_final_academic_level(session: Session, *, institution_id: UUID, programme_id: UUID) -> AcademicLevel | None:
    return session.scalar(select(AcademicLevel).where(
        AcademicLevel.institution_id == institution_id, AcademicLevel.programme_id == programme_id,
        AcademicLevel.status == "active",
    ).order_by(AcademicLevel.sequence_number.desc()).limit(1))


def _resolve_outstanding_failed_courses(records: Sequence[PerformanceRecord]) -> list[GraduationCourseDeficiency]:
    grouped: dict[UUID, list[PerformanceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.course.id].append(record)
    outstanding: list[GraduationCourseDeficiency] = []
    for attempts in grouped.values():
        attempts.sort(key=_attempt_order)
        latest = attempts[-1]
        has_passing = any(record.result.passed for record in attempts)
        if has_passing:
            continue
        outstanding.append(GraduationCourseDeficiency(
            course_id=latest.course.id, course_code=latest.course.code,
            course_title=latest.course.title, credit_units=latest.course.credit_units,
            latest_result_id=latest.result.id, latest_final_score=latest.result.final_score,
            latest_grade_letter=latest.result.grade_letter, latest_grade_point=latest.result.grade_point,
            attempt_count=len(attempts), has_passing_attempt=False, outstanding=True,
        ))
    return sorted(outstanding, key=lambda item: (item.course_code, item.course_id.hex))


def _attempt_order(record: PerformanceRecord) -> tuple[object, int, object, str]:
    return (record.academic_session.start_date, record.semester.sequence_number, record.result.computed_at, record.result.id.hex)


def _resolve_minimum_required_units(programme: Programme) -> int | None:
    # The current Programme model has no authoritative graduation-credit requirement.
    return None
