from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.academic_performance import SemesterGPAResult
from app.services.academic_progression_policy import AcademicStanding, ProgressionReason


class FailedCourseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: UUID
    course_registration_id: UUID
    course_offering_id: UUID
    course_id: UUID
    course_code: str
    course_title: str
    credit_units: int
    grade_letter: str
    grade_point: Decimal
    final_score: Decimal


class AcademicStandingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    programme_id: UUID
    current_level: str | None
    cumulative_attempted_units: int
    cumulative_earned_units: int
    cumulative_quality_points: Decimal
    cgpa: Decimal
    standing: AcademicStanding
    failed_course_count: int
    failed_course_ids: list[UUID]
    failed_course_codes: list[str]
    failed_credit_units: int
    has_carryover_courses: bool


class ProgressionEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    programme_id: UUID
    current_academic_level_id: UUID | None
    current_level: str | None
    current_level_sequence: int | None
    next_academic_level_id: UUID | None
    next_level: str | None
    next_level_sequence: int | None
    cgpa: Decimal
    academic_standing: AcademicStanding
    has_carryover_courses: bool
    failed_course_count: int
    eligible_for_progression: bool
    progression_reason: ProgressionReason


class StudentAcademicProgressSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    programme_id: UUID
    current_level: str | None
    academic_standing: AcademicStanding
    cgpa: Decimal
    cumulative_attempted_units: int
    cumulative_earned_units: int
    failed_courses: list[FailedCourseSummary]
    progression: ProgressionEvaluation
    semester_summaries: list[SemesterGPAResult]
