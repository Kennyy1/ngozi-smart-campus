from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
)


class ProgrammeAward(StrEnum):
    BSC = "BSc"
    BA = "BA"
    BENG = "BEng"
    MSC = "MSc"
    MBA = "MBA"
    PGD = "PGD"
    MPHIL = "MPhil"
    PHD = "PhD"


class StudyMode(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    DISTANCE = "DISTANCE"


class ProgrammeCreate(BaseModel):
    faculty_id: UUID
    department_id: UUID
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    award: ProgrammeAward
    duration_years: PositiveInt
    study_mode: StudyMode
    description: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
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

    @field_validator("award", "study_mode", mode="before")
    @classmethod
    def normalize_enum_input(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProgrammeUpdate(BaseModel):
    faculty_id: UUID | None = None
    department_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    award: ProgrammeAward | None = None
    duration_years: PositiveInt | None = None
    study_mode: StudyMode | None = None
    description: str | None = None
    status: Literal["active", "inactive"] | None = None

    @field_validator(
        "faculty_id",
        "department_id",
        "name",
        "code",
        "award",
        "duration_years",
        "study_mode",
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

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("award", "study_mode", mode="before")
    @classmethod
    def normalize_enum_input(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProgrammeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    faculty_id: UUID
    department_id: UUID
    name: str
    code: str
    award: ProgrammeAward
    duration_years: PositiveInt
    study_mode: StudyMode
    description: str | None
    status: Literal["active", "inactive"]
    created_at: datetime
    updated_at: datetime
