from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssessmentType(StrEnum):
    ATTENDANCE = "attendance"
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    TEST = "test"
    PROJECT = "project"
    PRESENTATION = "presentation"
    LABORATORY = "laboratory"
    PRACTICAL = "practical"
    MID_SEMESTER = "mid_semester"
    OTHER = "other"


class AssessmentComponentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    INACTIVE = "inactive"


class AssessmentComponentCreate(BaseModel):
    course_offering_id: UUID
    lecturer_assignment_id: UUID
    title: str = Field(min_length=1, max_length=255)
    assessment_type: AssessmentType
    maximum_score: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    weight_percentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    scheduled_date: date | None = None
    due_at: datetime | None = None
    status: AssessmentComponentStatus = AssessmentComponentStatus.DRAFT
    description: str | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_dates(self) -> "AssessmentComponentCreate":
        if self.scheduled_date is not None and self.due_at is not None and self.scheduled_date > self.due_at.date():
            raise ValueError("scheduled_date must not be later than due_at")
        return self


class AssessmentComponentUpdate(BaseModel):
    course_offering_id: UUID | None = None
    lecturer_assignment_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    assessment_type: AssessmentType | None = None
    maximum_score: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    weight_percentage: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    scheduled_date: date | None = None
    due_at: datetime | None = None
    status: AssessmentComponentStatus | None = None
    description: str | None = None

    @field_validator("course_offering_id", "lecturer_assignment_id", "title", "assessment_type", "maximum_score", "weight_percentage", "status")
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

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None


class AssessmentComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_offering_id: UUID
    lecturer_assignment_id: UUID
    title: str
    assessment_type: AssessmentType
    maximum_score: Decimal
    weight_percentage: Decimal
    scheduled_date: date | None
    due_at: datetime | None
    status: AssessmentComponentStatus
    description: str | None
    created_at: datetime
    updated_at: datetime
