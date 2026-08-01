from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class CourseType(StrEnum):
    COMPULSORY = "compulsory"
    ELECTIVE = "elective"
    REQUIRED = "required"
    GENERAL = "general"


CourseStatus = Literal["active", "inactive"]


class CourseCreate(BaseModel):
    department_id: UUID
    programme_id: UUID
    academic_level_id: UUID
    title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    credit_units: PositiveInt
    course_type: CourseType
    description: str | None = None
    status: CourseStatus = "active"

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("course_type", mode="before")
    @classmethod
    def normalize_course_type(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None


class CourseUpdate(BaseModel):
    department_id: UUID | None = None
    programme_id: UUID | None = None
    academic_level_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    credit_units: PositiveInt | None = None
    course_type: CourseType | None = None
    description: str | None = None
    status: CourseStatus | None = None

    @field_validator(
        "department_id",
        "programme_id",
        "academic_level_id",
        "title",
        "code",
        "credit_units",
        "course_type",
        "status",
    )
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("course_type", mode="before")
    @classmethod
    def normalize_course_type(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    department_id: UUID
    programme_id: UUID
    academic_level_id: UUID
    title: str
    code: str
    credit_units: PositiveInt
    course_type: CourseType
    description: str | None
    status: CourseStatus
    created_at: datetime
    updated_at: datetime
