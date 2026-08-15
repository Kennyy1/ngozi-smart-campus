from datetime import date, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class LecturerDashboard(BaseModel):
    lecturer_id: UUID
    staff_number: str
    name: str
    department: str
    employment_status: str
    active_course_assignment_count: int = 0
    current_course_offering_count: int = 0
    upcoming_class_session_count: int = 0
    total_registered_students: int = 0
    pending_assessment_component_count: int = 0
    completed_examination_count: int = 0


class LecturerCourse(BaseModel):
    lecturer_assignment_id: UUID
    course_offering_id: UUID
    course_id: UUID
    course_code: str
    course_title: str
    credit_units: int
    academic_session_id: UUID
    academic_session: str
    semester_id: UUID
    semester: str
    status: str
    registered_student_count: int


class LecturerCourseStudent(BaseModel):
    course_registration_id: UUID
    student_id: UUID
    matriculation_number: str
    student_name: str
    current_level: str | None
    registration_status: str


class LecturerAttendance(BaseModel):
    course_registration_id: UUID
    student_id: UUID
    matriculation_number: str
    student_name: str
    total_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: Decimal


class LecturerAssessment(BaseModel):
    component_id: UUID
    title: str
    type: str
    maximum_score: Decimal
    weight: Decimal
    status: str
    scheduled_date: date | None
    due_date: date | None
    registered_student_count: int
    scored_student_count: int
    unscored_student_count: int


class LecturerExamination(BaseModel):
    examination_id: UUID
    title: str
    type: str
    maximum_score: Decimal
    weight: Decimal
    examination_date: date
    start_time: time
    end_time: time
    status: str
    registered_student_count: int
    scored_student_count: int
    unscored_student_count: int


class LecturerResultOverview(BaseModel):
    course_offering_id: UUID
    registered_student_count: int
    published_result_count: int
    missing_published_result_count: int
    results: list[dict]
