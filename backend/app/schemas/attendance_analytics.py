from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CourseRegistrationAttendanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_registration_id: UUID
    student_id: UUID
    course_offering_id: UUID
    total_sessions: int
    recorded_sessions: int
    present_count: int
    late_count: int
    absent_count: int
    excused_count: int
    unmarked_count: int
    effective_session_count: int
    attendance_percentage: float
    minimum_required_percentage: float
    meets_requirement: bool


class ClassSessionAttendanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_session_id: UUID
    course_offering_id: UUID
    eligible_registration_count: int
    marked_count: int
    present_count: int
    late_count: int
    absent_count: int
    excused_count: int
    unmarked_count: int
    attendance_rate: float


class CourseOfferingAttendanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_offering_id: UUID
    total_class_sessions: int
    completed_class_sessions: int
    active_registration_count: int
    attendance_record_count: int
    average_attendance_percentage: float
    students_meeting_requirement: int
    students_below_requirement: int
    minimum_required_percentage: float
    student_summaries: list[CourseRegistrationAttendanceSummary] | None = None


class AttendanceRiskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_registration_id: UUID
    student_id: UUID
    matriculation_number: str
    student_name: str
    course_offering_id: UUID
    attendance_percentage: float
    minimum_required_percentage: float
    shortfall_percentage: float


class AttendanceRiskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_required_percentage: float = Field(ge=0, le=100)
    total_at_risk: int
    items: list[AttendanceRiskItem]
