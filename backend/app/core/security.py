from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any
from uuid import UUID, uuid4

import jwt
from pydantic import ValidationError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import settings
from app.core.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    SecurityConfigurationError,
)
from app.schemas.token import AccessTokenClaims


PASSWORD_HASH = PasswordHash.recommended()
REQUIRED_ACCESS_TOKEN_CLAIMS = [
    "sub",
    "institution_id",
    "roles",
    "type",
    "jti",
    "iat",
    "exp",
    "iss",
    "aud",
]
INVALID_JWT_SECRETS = {
    "",
    "replace-with-a-long-random-secret",
    "changeme",
    "change-me",
}


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    if "\x00" in password:
        raise ValueError("Password must not contain null bytes")
    return PASSWORD_HASH.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not plain_password or not password_hash or "\x00" in plain_password:
        return False
    try:
        return PASSWORD_HASH.verify(plain_password, password_hash)
    except (UnknownHashError, ValueError):
        return False
    except Exception:
        # Hash backends may raise format-specific errors for malformed input.
        return False


def password_hash_needs_update(password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        for hasher in PASSWORD_HASH.hashers:
            if hasher.identify(password_hash):
                return (
                    hasher != PASSWORD_HASH.current_hasher
                    or hasher.check_needs_rehash(password_hash)
                )
        return False
    except (UnknownHashError, ValueError):
        return False
    except Exception:
        # Hash backends may raise format-specific errors for malformed input.
        return False


def create_access_token(
    *,
    user_id: UUID,
    institution_id: UUID,
    roles: Sequence[str],
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> tuple[str, int]:
    secret = _get_jwt_secret()
    issued_at = _utc_now_or_supplied(now)
    expiry_duration = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    if expiry_duration.total_seconds() <= 0:
        raise ValueError("Access-token expiry must be greater than zero")

    expires_at = issued_at + expiry_duration
    normalized_roles = sorted(
        {role.strip() for role in roles if role.strip()}
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "institution_id": str(institution_id),
        "roles": normalized_roles,
        "type": "access",
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    encoded_token = jwt.encode(
        payload,
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_token, ceil(expiry_duration.total_seconds())


def decode_access_token(
    token: str,
    *,
    now: datetime | None = None,
) -> AccessTokenClaims:
    if not token or not token.strip():
        raise InvalidTokenError()

    secret = _get_jwt_secret()
    validation_time = _utc_now_or_supplied(now) if now is not None else None
    options: dict[str, Any] = {"require": REQUIRED_ACCESS_TOKEN_CLAIMS}
    if validation_time is not None:
        options["verify_exp"] = False
        options["verify_iat"] = False

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options=options,
        )
        claims = AccessTokenClaims.model_validate(payload)
    except jwt.ExpiredSignatureError as error:
        raise ExpiredTokenError() from error
    except (jwt.PyJWTError, ValidationError, TypeError, ValueError) as error:
        raise InvalidTokenError() from error

    if validation_time is not None:
        if claims.exp <= validation_time:
            raise ExpiredTokenError()
        if claims.iat > validation_time:
            raise InvalidTokenError()

    return claims


def _get_jwt_secret() -> str:
    secret = settings.JWT_SECRET_KEY.get_secret_value().strip()
    if secret.lower() in INVALID_JWT_SECRETS:
        raise SecurityConfigurationError()
    return secret


def _utc_now_or_supplied(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must be timezone-aware")
    return value.astimezone(UTC)
