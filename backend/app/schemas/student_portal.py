from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.clearance import StudentClearanceSummary
from app.schemas.transcript import StudentTranscriptSummary


class StudentProfile(BaseModel):
    student_id: UUID
    matriculation_number: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str | None
    programme_id: UUID | None
    programme_name: str | None
    programme_code: str | None
    current_level: str | None
    admission_year: int
    enrollment_status: str


class StudentCourse(BaseModel):
    course_registration_id: UUID
    course_offering_id: UUID
    course_id: UUID
    course_code: str
    title: str
    credit_units: int
    course_type: str
    semester_id: UUID
    semester: str
    academic_session_id: UUID
    academic_session: str
    registration_status: str


class AttendanceSummary(BaseModel):
    course_offering_id: UUID
    course_code: str
    course_title: str
    total_sessions: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    attendance_percentage: Decimal = Decimal("0.00")


class StudentResult(BaseModel):
    result_id: UUID
    course_offering_id: UUID
    course_code: str
    course_title: str
    academic_session_id: UUID
    academic_session: str
    semester_id: UUID
    semester: str
    credit_units: int
    final_score: Decimal
    grade: str
    grade_point: Decimal
    passed: bool


class StudentDocument(BaseModel):
    document_id: UUID
    type: str
    reference: str
    status: str
    issued_at: datetime | None
    verification_code: str


class StudentAcademicPerformance(BaseModel):
    current_gpa: Decimal | None
    cgpa: Decimal
    cumulative_attempted_units: int
    cumulative_earned_units: int
    academic_standing: str
    progression_summary: Any | None
    failed_courses: list[Any]


class StudentDashboard(StudentProfile):
    current_academic_session: str | None
    current_semester: str | None
    registered_course_count: int = 0
    active_course_count: int = 0
    attendance_summary: dict[str, Any]
    current_gpa: Decimal | None
    cgpa: Decimal | None
    academic_standing: str | None
    progression_summary: Any | None
    clearance_summary: Any | None
    graduation_summary: Any | None


StudentTranscript = StudentTranscriptSummary
StudentClearance = StudentClearanceSummary
