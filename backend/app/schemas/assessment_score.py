from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssessmentScoreStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class _AssessmentScoreFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
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


class AssessmentScoreCreate(_AssessmentScoreFields):
    assessment_component_id: UUID
    course_registration_id: UUID


class AssessmentScoreUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    remarks: str | None = None

    @field_validator("score")
    @classmethod
    def reject_null_score(cls, value: object) -> object:
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


class AssessmentScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    assessment_component_id: UUID
    course_registration_id: UUID
    score: Decimal
    graded_by_user_id: UUID
    graded_at: datetime
    remarks: str | None
    status: AssessmentScoreStatus
    created_at: datetime
    updated_at: datetime


class AssessmentScoreBulkItem(_AssessmentScoreFields):
    course_registration_id: UUID


class AssessmentScoreBulkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_component_id: UUID
    scores: list[AssessmentScoreBulkItem] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_registrations(self) -> "AssessmentScoreBulkCreate":
        registration_ids = [item.course_registration_id for item in self.scores]
        if len(registration_ids) != len(set(registration_ids)):
            raise ValueError("duplicate course_registration_id values are not allowed")
        return self


class AssessmentScoreBulkResult(BaseModel):
    scores: list[AssessmentScoreRead]
