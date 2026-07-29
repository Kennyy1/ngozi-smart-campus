from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, PositiveInt, field_validator


class AccessTokenClaims(BaseModel):
    sub: UUID
    institution_id: UUID
    roles: list[str]
    type: Literal["access"]
    jti: UUID
    iat: datetime
    exp: datetime
    iss: str
    aud: str

    @field_validator("iat", "exp")
    @classmethod
    def require_timezone_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Token timestamps must be timezone-aware")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: PositiveInt
