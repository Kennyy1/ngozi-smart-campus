from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator, model_validator

CourseOfferingStatus = Literal["active", "inactive"]


class CourseOfferingCreate(BaseModel):
    course_id: UUID
    academic_session_id: UUID
    semester_id: UUID
    capacity: PositiveInt | None = None
    registration_open: bool = False
    registration_start_date: date | None = None
    registration_end_date: date | None = None
    status: CourseOfferingStatus = "active"
    description: str | None = None

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_registration_window(self) -> "CourseOfferingCreate":
        if (
            self.registration_start_date is not None
            and self.registration_end_date is not None
            and self.registration_start_date >= self.registration_end_date
        ):
            raise ValueError("registration_start_date must be earlier than registration_end_date")
        return self


class CourseOfferingUpdate(BaseModel):
    course_id: UUID | None = None
    academic_session_id: UUID | None = None
    semester_id: UUID | None = None
    capacity: PositiveInt | None = None
    registration_open: bool | None = None
    registration_start_date: date | None = None
    registration_end_date: date | None = None
    status: CourseOfferingStatus | None = None
    description: str | None = None

    @field_validator(
        "course_id",
        "academic_session_id",
        "semester_id",
        "registration_open",
        "status",
    )
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_supplied_registration_window(self) -> "CourseOfferingUpdate":
        if (
            self.registration_start_date is not None
            and self.registration_end_date is not None
            and self.registration_start_date >= self.registration_end_date
        ):
            raise ValueError("registration_start_date must be earlier than registration_end_date")
        return self


class CourseOfferingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_id: UUID
    academic_session_id: UUID
    semester_id: UUID
    capacity: PositiveInt | None
    registration_open: bool
    registration_start_date: date | None
    registration_end_date: date | None
    status: CourseOfferingStatus
    description: str | None
    created_at: datetime
    updated_at: datetime
