from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class ClearanceRequirementStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class StudentClearanceStatus(StrEnum):
    PENDING = "pending"
    CLEARED = "cleared"
    REJECTED = "rejected"
    WAIVED = "waived"
    INACTIVE = "inactive"


def _normalize_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be blank")
    return value


def _normalize_code(value: str) -> str:
    value = value.strip().upper()
    if not value:
        raise ValueError("must not be blank")
    return value


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class ClearanceRequirementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = None
    sequence_number: PositiveInt
    is_mandatory: bool
    status: ClearanceRequirementStatus = ClearanceRequirementStatus.ACTIVE
    _name = field_validator("name")(_normalize_name)
    _code = field_validator("code")(_normalize_code)
    _description = field_validator("description")(_trim_optional)


class ClearanceRequirementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    sequence_number: PositiveInt | None = None
    is_mandatory: bool | None = None
    status: ClearanceRequirementStatus | None = None

    @field_validator("name", "code", "sequence_number", "is_mandatory", "status")
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    _name = field_validator("name")(_normalize_name)
    _code = field_validator("code")(_normalize_code)
    _description = field_validator("description")(_trim_optional)


class ClearanceRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    name: str
    code: str
    description: str | None
    sequence_number: PositiveInt
    is_mandatory: bool
    status: ClearanceRequirementStatus
    created_at: datetime
    updated_at: datetime


class StudentClearanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    clearance_requirement_id: UUID
    remarks: str | None = None
    evidence_reference: str | None = Field(default=None, max_length=500)
    _trim = field_validator("remarks", "evidence_reference")(_trim_optional)


class StudentClearanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str | None = None
    evidence_reference: str | None = Field(default=None, max_length=500)
    _trim = field_validator("remarks", "evidence_reference")(_trim_optional)


class StudentClearanceActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class StudentClearanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    student_id: UUID
    clearance_requirement_id: UUID
    status: StudentClearanceStatus
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None
    remarks: str | None
    evidence_reference: str | None
    created_at: datetime
    updated_at: datetime


class StudentClearanceSummaryItem(BaseModel):
    clearance_requirement_id: UUID
    name: str
    code: str
    is_mandatory: bool
    sequence_number: PositiveInt
    student_clearance_id: UUID | None
    status: str
    remarks: str | None
    evidence_reference: str | None
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None


class StudentClearanceSummary(BaseModel):
    student_id: UUID
    matriculation_number: str
    student_name: str
    total_active_requirements: int
    mandatory_requirements: int
    optional_requirements: int
    cleared_count: int
    waived_count: int
    rejected_count: int
    pending_count: int
    missing_count: int
    is_fully_cleared: bool
    requirements: list[StudentClearanceSummaryItem]


class GraduationClearanceEvaluation(BaseModel):
    student_id: UUID
    academically_eligible_for_graduation: bool
    academic_eligibility_reasons: list[str]
    administratively_cleared: bool
    clearance_blockers: list[str]
    ready_for_final_graduation_processing: bool
