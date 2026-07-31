from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AcademicSessionStatus = Literal["active", "inactive"]


class AcademicSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    is_current: bool = False
    status: AcademicSessionStatus = "active"
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
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_date_range(self) -> "AcademicSessionCreate":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        return self


class AcademicSessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    status: AcademicSessionStatus | None = None
    description: str | None = None

    @field_validator(
        "name",
        "start_date",
        "end_date",
        "is_current",
        "status",
    )
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
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_supplied_date_range(self) -> "AcademicSessionUpdate":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date >= self.end_date
        ):
            raise ValueError("start_date must be earlier than end_date")
        return self


class AcademicSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    name: str
    start_date: date
    end_date: date
    is_current: bool
    status: AcademicSessionStatus
    description: str | None
    created_at: datetime
    updated_at: datetime
