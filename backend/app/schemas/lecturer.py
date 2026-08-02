from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class AcademicRank(StrEnum):
    GRADUATE_ASSISTANT = "graduate_assistant"
    ASSISTANT_LECTURER = "assistant_lecturer"
    LECTURER_II = "lecturer_ii"
    LECTURER_I = "lecturer_i"
    SENIOR_LECTURER = "senior_lecturer"
    ASSOCIATE_PROFESSOR = "associate_professor"
    PROFESSOR = "professor"


class EmploymentStatus(StrEnum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    RESIGNED = "resigned"
    INACTIVE = "inactive"


class _LecturerTextValidation(BaseModel):
    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("first_name", "last_name", "staff_number", check_fields=False)
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone", "specialization", "office_location", check_fields=False)
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None


class LecturerCreate(_LecturerTextValidation):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    department_id: UUID
    staff_number: str = Field(min_length=1, max_length=100)
    academic_rank: AcademicRank
    specialization: str | None = Field(default=None, max_length=255)
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    employment_date: date | None = None
    office_location: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("must not contain null bytes")
        return value


class LecturerUpdate(_LecturerTextValidation):
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    department_id: UUID | None = None
    staff_number: str | None = Field(default=None, min_length=1, max_length=100)
    academic_rank: AcademicRank | None = None
    specialization: str | None = Field(default=None, max_length=255)
    employment_status: EmploymentStatus | None = None
    employment_date: date | None = None
    office_location: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_verified: bool | None = None

    @field_validator("email", "first_name", "last_name", "department_id", "staff_number", "academic_rank", "employment_status", "is_active", "is_verified")
    @classmethod
    def reject_null_required_values(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value


class LecturerRead(BaseModel):
    id: UUID
    institution_id: UUID
    user_id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    department_id: UUID
    staff_number: str
    academic_rank: AcademicRank
    specialization: str | None
    employment_status: EmploymentStatus
    employment_date: date | None
    office_location: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
