from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.transcript import StudentTranscriptSummary


class OfficialTranscriptStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    REVOKED = "revoked"
    INACTIVE = "inactive"


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class OfficialTranscriptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class OfficialTranscriptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class TranscriptRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class OfficialTranscriptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    student_id: UUID
    programme_id: UUID
    transcript_reference: str
    status: OfficialTranscriptStatus
    snapshot_data: StudentTranscriptSummary
    generated_at: datetime
    generated_by_user_id: UUID
    issued_at: datetime | None
    issued_by_user_id: UUID | None
    revoked_at: datetime | None
    revoked_by_user_id: UUID | None
    revocation_reason: str | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime
