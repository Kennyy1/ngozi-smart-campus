from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SemesterStatus = Literal["active", "inactive"]


class SemesterCreate(BaseModel):
    academic_session_id: UUID
    name: str = Field(min_length=1, max_length=255)
    sequence_number: int = Field(gt=0)
    start_date: date
    end_date: date
    is_current: bool = False
    status: SemesterStatus = "active"
    description: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_date_range(self) -> "SemesterCreate":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        return self


class SemesterUpdate(BaseModel):
    academic_session_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence_number: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    status: SemesterStatus | None = None
    description: str | None = None

    @field_validator("academic_session_id", "name", "sequence_number", "start_date", "end_date", "is_current", "status")
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_supplied_date_range(self) -> "SemesterUpdate":
        if self.start_date is not None and self.end_date is not None and self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        return self


class SemesterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    institution_id: UUID
    academic_session_id: UUID
    name: str
    sequence_number: int
    start_date: date
    end_date: date
    is_current: bool
    status: SemesterStatus
    description: str | None
    created_at: datetime
    updated_at: datetime
