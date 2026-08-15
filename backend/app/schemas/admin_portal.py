from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AdminDashboard(BaseModel):
    institution_id: UUID
    institution_name: str
    total_students: int = 0
    active_students: int = 0
    graduated_students: int = 0
    total_lecturers: int = 0
    active_lecturers: int = 0
    total_programmes: int = 0
    total_courses: int = 0
    current_academic_session: str | None
    current_semester: str | None
    active_course_offerings: int = 0
    active_course_registrations: int = 0
    published_results: int = 0
    pending_result_approvals: int = 0
    graduation_eligible_students: int | None = None
    confirmed_graduations: int = 0
    issued_transcripts: int = 0
    issued_certificates: int = 0
    pending_mandatory_clearances: int = 0


class AdminStudentSummary(BaseModel):
    student_id: UUID
    identity: dict[str, Any]
    programme: dict[str, Any] | None
    current_level: str | None
    enrollment_status: str
    course_registration_count: int
    attendance_headline: dict[str, Any]
    academic_performance: Any | None
    progression: Any | None
    graduation_eligibility: Any | None
    clearance: Any | None
    transcript_status: str | None
    graduation_status: str | None
    document_statuses: dict[str, int]


class AdminCourseOfferingSummary(BaseModel):
    course_offering_id: UUID
    course: dict[str, Any]
    academic_session: dict[str, Any]
    semester: dict[str, Any]
    lecturer_assignments: list[dict[str, Any]]
    registered_student_count: int
    class_session_count: int
    attendance_headline: dict[str, Any]
    assessment_component_count: int
    examination_count: int
    result_status_summary: dict[str, int]
