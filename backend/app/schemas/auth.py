from typing import Literal

from pydantic import BaseModel, EmailStr, PositiveInt, field_validator

from app.schemas.token import TokenResponse


class LoginRequest(BaseModel):
    institution_code: str
    email: EmailStr
    password: str

    @field_validator("institution_code")
    @classmethod
    def validate_institution_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Institution code must not be empty")
        return normalized

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise ValueError("Password must not be empty")
        if "\x00" in value:
            raise ValueError("Password must not contain null bytes")
        return value


class LoginResponse(TokenResponse):
    token_type: Literal["bearer"] = "bearer"
    expires_in: PositiveInt
