from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.services.academic_progression_policy import AcademicStanding


class TranscriptCourseResult(BaseModel):
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


class TranscriptSemesterHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester_id: UUID
    semester_name: str
    semester_sequence_number: int
    academic_session_id: UUID
    academic_session_name: str
    attempted_units: int
    earned_units: int
    total_quality_points: Decimal
    course_count: int
    passed_courses: int
    failed_courses: int
    gpa: Decimal
    courses: list[TranscriptCourseResult]


class TranscriptAcademicSessionHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_session_id: UUID
    academic_session_name: str
    start_date: date
    end_date: date
    session_attempted_units: int
    session_earned_units: int
    session_quality_points: Decimal
    session_course_count: int
    session_passed_courses: int
    session_failed_courses: int
    semesters: list[TranscriptSemesterHistory]


class StudentTranscriptSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    matriculation_number: str
    student_name: str
    programme_id: UUID
    programme_name: str
    programme_code: str
    current_level: str | None
    admission_year: int
    enrollment_status: str
    cumulative_attempted_units: int
    cumulative_earned_units: int
    cumulative_quality_points: Decimal
    total_courses: int
    passed_courses: int
    failed_courses: int
    cgpa: Decimal
    academic_standing: AcademicStanding
    academic_sessions: list[TranscriptAcademicSessionHistory]
