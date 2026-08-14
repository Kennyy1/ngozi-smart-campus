from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class AcademicDocumentType(StrEnum):
    CERTIFICATE = "certificate"
    STATEMENT_OF_RESULT = "statement_of_result"


class AcademicDocumentStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    REVOKED = "revoked"
    INACTIVE = "inactive"


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class AcademicDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    document_type: AcademicDocumentType
    graduation_record_id: UUID | None = None
    official_transcript_id: UUID | None = None
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)

    @model_validator(mode="after")
    def validate_source(self) -> "AcademicDocumentCreate":
        if self.document_type == AcademicDocumentType.CERTIFICATE:
            if self.graduation_record_id is None:
                raise ValueError("graduation_record_id is required for a certificate")
            if self.official_transcript_id is not None:
                raise ValueError("official_transcript_id is not valid for a certificate")
        elif self.graduation_record_id is not None:
            raise ValueError("graduation_record_id is not valid for a statement of result")
        return self


class AcademicDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str | None = None
    _trim = field_validator("remarks")(_trim_optional)


class AcademicDocumentRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class AcademicDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    student_id: UUID
    programme_id: UUID | None
    graduation_record_id: UUID | None
    official_transcript_id: UUID | None
    document_type: AcademicDocumentType
    document_reference: str
    verification_code: str
    status: AcademicDocumentStatus
    title: str
    snapshot_data: dict[str, Any]
    generated_at: datetime
    generated_by_user_id: UUID
    issued_at: datetime | None
    issued_by_user_id: UUID | None
    revoked_at: datetime | None
    revoked_by_user_id: UUID | None
    revocation_reason: str | None
    file_reference: str | None
    file_generated_at: datetime | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class PublicAcademicDocumentVerification(BaseModel):
    valid: bool
    document_type: AcademicDocumentType
    document_reference: str
    status: AcademicDocumentStatus
    student_name: str
    programme_name: str | None
    award_title: str | None = None
    degree_classification_label: str | None = None
    graduation_date: date | None = None
    issued_at: datetime | None
