from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AttendanceRecordStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


def validate_attendance_state(
    attendance_status: AttendanceStatus,
    check_in_time: datetime | None,
) -> None:
    if attendance_status is AttendanceStatus.LATE and check_in_time is None:
        raise ValueError("check_in_time is required for late attendance")
    if attendance_status in (AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED) and check_in_time is not None:
        raise ValueError("check_in_time is not allowed for absent or excused attendance")


class _AttendanceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attendance_status: AttendanceStatus
    check_in_time: datetime | None = None
    remarks: str | None = None

    @field_validator("remarks")
    @classmethod
    def trim_remarks(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_state(self) -> "_AttendanceFields":
        validate_attendance_state(self.attendance_status, self.check_in_time)
        return self


class AttendanceRecordCreate(_AttendanceFields):
    class_session_id: UUID
    course_registration_id: UUID


class AttendanceRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attendance_status: AttendanceStatus | None = None
    check_in_time: datetime | None = None
    remarks: str | None = None

    @field_validator("attendance_status")
    @classmethod
    def reject_null_status(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("remarks")
    @classmethod
    def trim_remarks(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class AttendanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    class_session_id: UUID
    course_registration_id: UUID
    attendance_status: AttendanceStatus
    check_in_time: datetime | None
    recorded_by_user_id: UUID
    remarks: str | None
    status: AttendanceRecordStatus
    created_at: datetime
    updated_at: datetime


class AttendanceBulkItem(_AttendanceFields):
    course_registration_id: UUID


class AttendanceBulkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_session_id: UUID
    records: list[AttendanceBulkItem] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_registrations(self) -> "AttendanceBulkCreate":
        registration_ids = [item.course_registration_id for item in self.records]
        if len(registration_ids) != len(set(registration_ids)):
            raise ValueError("duplicate course_registration_id values are not allowed")
        return self


class AttendanceBulkResult(BaseModel):
    records: list[AttendanceRecordRead]
