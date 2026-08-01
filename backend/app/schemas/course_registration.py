from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class RegistrationStatus(StrEnum):
    REGISTERED = "registered"
    DROPPED = "dropped"


class CourseRegistrationCreate(BaseModel):
    student_id: UUID
    course_offering_id: UUID
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None


class CourseRegistrationUpdate(BaseModel):
    registration_status: RegistrationStatus | None = None
    notes: str | None = None

    @field_validator("registration_status")
    @classmethod
    def reject_null_status(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("registration_status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None


class CourseRegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    student_id: UUID
    course_offering_id: UUID
    registration_status: RegistrationStatus
    registered_at: datetime
    dropped_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
