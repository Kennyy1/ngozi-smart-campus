from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CourseGradePointBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: UUID
    course_registration_id: UUID
    course_offering_id: UUID
    course_id: UUID
    course_code: str
    course_title: str
    credit_units: int
    final_score: Decimal
    grade_letter: str
    grade_point: Decimal
    passed: bool
    quality_points: Decimal


class SemesterGPAResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    academic_session_id: UUID
    semester_id: UUID
    attempted_units: int
    earned_units: int
    total_quality_points: Decimal
    course_count: int
    passed_courses: int
    failed_courses: int
    gpa: Decimal
    courses: list[CourseGradePointBreakdown]


class CGPAResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    cumulative_attempted_units: int
    cumulative_earned_units: int
    cumulative_quality_points: Decimal
    total_courses: int
    passed_courses: int
    failed_courses: int
    cgpa: Decimal
    semester_summaries: list[SemesterGPAResult]
