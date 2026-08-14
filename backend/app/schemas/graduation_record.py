from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class GraduationRecordStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REVOKED = "revoked"
    INACTIVE = "inactive"


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class GraduationRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class GraduationRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class GraduationRecordConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graduation_date: date


class GraduationRecordRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class GraduationRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    student_id: UUID
    programme_id: UUID
    graduation_reference: str
    status: GraduationRecordStatus
    graduation_date: date | None
    award_title: str
    degree_classification: str | None
    degree_classification_label: str | None
    final_cgpa: Decimal
    academic_standing: str
    eligibility_snapshot: dict[str, Any]
    outcome_snapshot: dict[str, Any]
    prepared_at: datetime
    prepared_by_user_id: UUID
    confirmed_at: datetime | None
    confirmed_by_user_id: UUID | None
    revoked_at: datetime | None
    revoked_by_user_id: UUID | None
    revocation_reason: str | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime
