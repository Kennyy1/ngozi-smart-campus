from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    DEFERRED = "deferred"
    SUSPENDED = "suspended"
    WITHDRAWN = "withdrawn"
    GRADUATED = "graduated"
    INACTIVE = "inactive"


class StudentCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    programme_id: UUID
    matriculation_number: str = Field(min_length=1, max_length=100)
    admission_year: int
    current_level: str | None = Field(default=None, max_length=255)
    enrollment_status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    graduation_date: date | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("first_name", "last_name", "matriculation_number")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone", "current_level")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("must not contain null bytes")
        return value

    @field_validator("admission_year")
    @classmethod
    def validate_admission_year(cls, value: int) -> int:
        if value < 1900 or value > date.today().year + 1:
            raise ValueError("must be a reasonable admission year")
        return value

    @model_validator(mode="after")
    def validate_graduation_state(self) -> "StudentCreate":
        validate_graduation_state(self.enrollment_status, self.graduation_date)
        return self


class StudentUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    programme_id: UUID | None = None
    matriculation_number: str | None = Field(default=None, min_length=1, max_length=100)
    admission_year: int | None = None
    current_level: str | None = Field(default=None, max_length=255)
    enrollment_status: EnrollmentStatus | None = None
    graduation_date: date | None = None
    is_active: bool | None = None
    is_verified: bool | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email", "first_name", "last_name", "programme_id", "matriculation_number", "admission_year", "enrollment_status", "is_active", "is_verified")
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value

    @field_validator("first_name", "last_name", "matriculation_number")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone", "current_level")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @field_validator("admission_year")
    @classmethod
    def validate_admission_year(cls, value: int | None) -> int | None:
        if value is not None and (value < 1900 or value > date.today().year + 1):
            raise ValueError("must be a reasonable admission year")
        return value


class StudentRead(BaseModel):
    id: UUID
    institution_id: UUID
    user_id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    programme_id: UUID
    matriculation_number: str
    admission_year: int
    current_level: str | None
    enrollment_status: EnrollmentStatus
    graduation_date: date | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


def validate_graduation_state(
    enrollment_status: EnrollmentStatus | str,
    graduation_date: date | None,
) -> None:
    if enrollment_status == EnrollmentStatus.GRADUATED and graduation_date is None:
        raise ValueError("graduation_date is required for graduated students")
    if enrollment_status != EnrollmentStatus.GRADUATED and graduation_date is not None:
        raise ValueError("graduation_date is only allowed for graduated students")
