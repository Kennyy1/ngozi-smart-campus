from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SessionType(StrEnum):
    LECTURE = "lecture"; TUTORIAL = "tutorial"; LABORATORY = "laboratory"; PRACTICAL = "practical"; SEMINAR = "seminar"


class DeliveryMode(StrEnum):
    PHYSICAL = "physical"; ONLINE = "online"; HYBRID = "hybrid"


class ClassSessionStatus(StrEnum):
    SCHEDULED = "scheduled"; COMPLETED = "completed"; CANCELLED = "cancelled"; POSTPONED = "postponed"; INACTIVE = "inactive"


def validate_session_state(start_time: time, end_time: time, delivery_mode: DeliveryMode, venue: str | None) -> None:
    if start_time >= end_time: raise ValueError("start_time must be earlier than end_time")
    if delivery_mode in (DeliveryMode.PHYSICAL, DeliveryMode.HYBRID) and not venue: raise ValueError("venue is required for physical or hybrid delivery")


class ClassSessionCreate(BaseModel):
    course_offering_id: UUID
    lecturer_assignment_id: UUID
    session_date: date
    start_time: time
    end_time: time
    session_type: SessionType
    topic: str = Field(min_length=1, max_length=255)
    venue: str | None = Field(default=None, max_length=255)
    delivery_mode: DeliveryMode = DeliveryMode.PHYSICAL
    status: ClassSessionStatus = ClassSessionStatus.SCHEDULED
    notes: str | None = None

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, value: str) -> str:
        value = value.strip()
        if not value: raise ValueError("must not be blank")
        return value

    @field_validator("venue", "notes")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None: return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_state(self) -> "ClassSessionCreate": validate_session_state(self.start_time, self.end_time, self.delivery_mode, self.venue); return self


class ClassSessionUpdate(BaseModel):
    course_offering_id: UUID | None = None; lecturer_assignment_id: UUID | None = None; session_date: date | None = None
    start_time: time | None = None; end_time: time | None = None; session_type: SessionType | None = None
    topic: str | None = Field(default=None, min_length=1, max_length=255); venue: str | None = Field(default=None, max_length=255)
    delivery_mode: DeliveryMode | None = None; status: ClassSessionStatus | None = None; notes: str | None = None

    @field_validator("course_offering_id", "lecturer_assignment_id", "session_date", "start_time", "end_time", "session_type", "topic", "delivery_mode", "status")
    @classmethod
    def reject_null_required(cls, value: object) -> object:
        if value is None: raise ValueError("must not be null")
        return value

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, value: str | None) -> str | None:
        if value is None: return value
        value = value.strip()
        if not value: raise ValueError("must not be blank")
        return value

    @field_validator("venue", "notes")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None: return None if value is None else value.strip() or None


class ClassSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; institution_id: UUID; course_offering_id: UUID; lecturer_assignment_id: UUID
    session_date: date; start_time: time; end_time: time; session_type: SessionType; topic: str
    venue: str | None; delivery_mode: DeliveryMode; status: ClassSessionStatus; notes: str | None
    created_at: datetime; updated_at: datetime
