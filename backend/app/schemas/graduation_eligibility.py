from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.services.academic_progression_policy import AcademicStanding
from app.services.graduation_policy import GraduationEligibilityReason


class GraduationCourseDeficiency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: UUID
    course_code: str
    course_title: str
    credit_units: int
    latest_result_id: UUID
    latest_final_score: Decimal
    latest_grade_letter: str
    latest_grade_point: Decimal
    attempt_count: int
    has_passing_attempt: bool
    outstanding: bool


class GraduationEligibilityEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    matriculation_number: str
    student_name: str
    programme_id: UUID
    programme_name: str
    programme_code: str
    current_academic_level_id: UUID | None
    current_level: str | None
    current_level_sequence: int | None
    final_academic_level_id: UUID | None
    final_level: str | None
    final_level_sequence: int | None
    cumulative_attempted_units: int
    cumulative_earned_units: int
    minimum_required_units: int | None
    credit_requirement_configured: bool
    curriculum_completion_verified: bool
    cgpa: Decimal
    minimum_graduation_cgpa: Decimal
    academic_standing: AcademicStanding
    total_published_courses: int
    passed_course_count: int
    outstanding_failed_course_count: int
    outstanding_failed_credit_units: int
    outstanding_courses: list[GraduationCourseDeficiency]
    final_level_reached: bool
    meets_cgpa_requirement: bool
    meets_credit_requirement: bool | None
    has_published_results: bool
    eligible_for_graduation: bool
    eligibility_reasons: list[GraduationEligibilityReason]
