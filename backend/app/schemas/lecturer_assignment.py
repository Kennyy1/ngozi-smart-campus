from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssignmentRole(StrEnum):
    PRIMARY = "primary"
    CO_INSTRUCTOR = "co_instructor"
    TEACHING_ASSISTANT = "teaching_assistant"
    LAB_INSTRUCTOR = "lab_instructor"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


def _validate_state(role: AssignmentRole, is_primary: bool, assigned_at: datetime, ended_at: datetime | None) -> None:
    if (role == AssignmentRole.PRIMARY) != is_primary:
        raise ValueError("assignment_role and is_primary are inconsistent")
    if ended_at is not None and assigned_at >= ended_at:
        raise ValueError("assigned_at must be earlier than ended_at")


class LecturerAssignmentCreate(BaseModel):
    lecturer_id: UUID
    course_offering_id: UUID
    assignment_role: AssignmentRole
    is_primary: bool
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    status: AssignmentStatus = AssignmentStatus.ACTIVE
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None: return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_state(self) -> "LecturerAssignmentCreate":
        _validate_state(self.assignment_role, self.is_primary, self.assigned_at, self.ended_at); return self


class LecturerAssignmentUpdate(BaseModel):
    lecturer_id: UUID | None = None
    course_offering_id: UUID | None = None
    assignment_role: AssignmentRole | None = None
    is_primary: bool | None = None
    assigned_at: datetime | None = None
    ended_at: datetime | None = None
    status: AssignmentStatus | None = None
    notes: str | None = None

    @field_validator("lecturer_id", "course_offering_id", "assignment_role", "is_primary", "assigned_at", "status")
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None: raise ValueError("must not be null")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None: return None if value is None else value.strip() or None


class LecturerAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    lecturer_id: UUID
    course_offering_id: UUID
    assignment_role: AssignmentRole
    is_primary: bool
    assigned_at: datetime
    ended_at: datetime | None
    status: AssignmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
