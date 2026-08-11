from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ResultStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    WITHHELD = "withheld"
    INACTIVE = "inactive"


def _trim_optional(value: str | None) -> str | None:
    if value is None: return None
    value = value.strip()
    return value or None


class ResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_registration_id: UUID
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class ResultUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class ResultRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value: raise ValueError("must not be blank")
        return value


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    course_registration_id: UUID
    course_offering_id: UUID
    student_id: UUID
    continuous_assessment_score: Decimal
    examination_score: Decimal
    final_score: Decimal
    grade_letter: str
    grade_point: Decimal
    passed: bool
    status: ResultStatus
    computed_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    published_at: datetime | None
    computed_by_user_id: UUID
    submitted_by_user_id: UUID | None
    approved_by_user_id: UUID | None
    published_by_user_id: UUID | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime
