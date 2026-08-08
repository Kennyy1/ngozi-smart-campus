from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExaminationType(StrEnum):
    WRITTEN = "written"
    PRACTICAL = "practical"
    ORAL = "oral"
    PROJECT_DEFENSE = "project_defense"
    CLINICAL = "clinical"
    OTHER = "other"


class DeliveryMode(StrEnum):
    PHYSICAL = "physical"
    ONLINE = "online"
    HYBRID = "hybrid"


class ExaminationStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    INACTIVE = "inactive"


def _normalize_optional(value: str | None) -> str | None:
    return None if value is None else value.strip() or None


class ExaminationCreate(BaseModel):
    course_offering_id: UUID
    lecturer_assignment_id: UUID
    title: str = Field(min_length=1, max_length=255)
    examination_type: ExaminationType
    maximum_score: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    weight_percentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    exam_date: date
    start_time: time
    end_time: time
    venue: str | None = Field(default=None, max_length=255)
    delivery_mode: DeliveryMode
    status: ExaminationStatus = ExaminationStatus.DRAFT
    instructions: str | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("venue", "instructions")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ExaminationCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        if self.delivery_mode in (DeliveryMode.PHYSICAL, DeliveryMode.HYBRID) and self.venue is None:
            raise ValueError("venue is required for physical and hybrid examinations")
        return self


class ExaminationUpdate(BaseModel):
    course_offering_id: UUID | None = None
    lecturer_assignment_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    examination_type: ExaminationType | None = None
    maximum_score: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    weight_percentage: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    venue: str | None = Field(default=None, max_length=255)
    delivery_mode: DeliveryMode | None = None
    status: ExaminationStatus | None = None
    instructions: str | None = None

    @field_validator("course_offering_id", "lecturer_assignment_id", "title", "examination_type", "maximum_score", "weight_percentage", "exam_date", "start_time", "end_time", "delivery_mode", "status")
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = " ".join(value.split())
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("venue", "instructions")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional(value)


class ExaminationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    course_offering_id: UUID
    lecturer_assignment_id: UUID
    title: str
    examination_type: ExaminationType
    maximum_score: Decimal
    weight_percentage: Decimal
    exam_date: date
    start_time: time
    end_time: time
    venue: str | None
    delivery_mode: DeliveryMode
    status: ExaminationStatus
    instructions: str | None
    created_at: datetime
    updated_at: datetime
