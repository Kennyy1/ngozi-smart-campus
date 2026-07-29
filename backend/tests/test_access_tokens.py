from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    SecurityConfigurationError,
)
from app.core.security import create_access_token, decode_access_token


TEST_SECRET = "test-only-secret-with-sufficient-entropy-123456789"
OTHER_SECRET = "different-test-only-secret-with-sufficient-entropy"
NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
USER_ID = uuid4()
INSTITUTION_ID = uuid4()
REQUIRED_PAYLOAD: dict[str, Any] = {
    "sub": str(USER_ID),
    "institution_id": str(INSTITUTION_ID),
    "roles": ["student"],
    "type": "access",
    "jti": str(uuid4()),
    "iat": NOW,
    "exp": NOW + timedelta(minutes=15),
    "iss": "ngozi-smart-campus",
    "aud": "ngozi-smart-campus-api",
}


@pytest.fixture(autouse=True)
def configure_test_security(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", SecretStr(TEST_SECRET))
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ISSUER", "ngozi-smart-campus")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "ngozi-smart-campus-api")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)


def _encode(payload: dict[str, Any], secret: str = TEST_SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def test_valid_access_token_can_be_created_and_decoded() -> None:
    token, expires_in = create_access_token(
        user_id=USER_ID,
        institution_id=INSTITUTION_ID,
        roles=["student", "lecturer", "student", "", "  "],
        now=NOW,
    )

    claims = decode_access_token(token, now=NOW)

    assert claims.sub == USER_ID
    assert claims.institution_id == INSTITUTION_ID
    assert claims.roles == ["lecturer", "student"]
    assert claims.type == "access"
    assert isinstance(claims.jti, UUID)
    assert claims.iss == settings.JWT_ISSUER
    assert claims.aud == settings.JWT_AUDIENCE
    assert claims.exp > claims.iat
    assert expires_in == 15 * 60


def test_token_signed_with_another_secret_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(_encode(REQUIRED_PAYLOAD, OTHER_SECRET), now=NOW)


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("iss", "wrong-issuer"),
        ("aud", "wrong-audience"),
        ("type", "refresh"),
    ],
)
def test_invalid_access_token_claims_are_rejected(
    claim: str,
    value: str,
) -> None:
    payload = {**REQUIRED_PAYLOAD, claim: value}

    with pytest.raises(InvalidTokenError):
        decode_access_token(_encode(payload), now=NOW)


def test_expired_token_raises_expired_token_error() -> None:
    payload = {
        **REQUIRED_PAYLOAD,
        "iat": NOW - timedelta(minutes=30),
        "exp": NOW - timedelta(minutes=15),
    }

    with pytest.raises(ExpiredTokenError):
        decode_access_token(_encode(payload), now=NOW)


@pytest.mark.parametrize("token", ["not-a-jwt", "", "   "])
def test_malformed_or_blank_token_is_rejected(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, now=NOW)


@pytest.mark.parametrize(
    "expires_delta",
    [timedelta(0), timedelta(seconds=-1)],
)
def test_non_positive_expiry_is_rejected(expires_delta: timedelta) -> None:
    with pytest.raises(ValueError):
        create_access_token(
            user_id=USER_ID,
            institution_id=INSTITUTION_ID,
            roles=["student"],
            expires_delta=expires_delta,
            now=NOW,
        )


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError):
        create_access_token(
            user_id=USER_ID,
            institution_id=INSTITUTION_ID,
            roles=["student"],
            now=datetime(2026, 1, 15, 12, 0),
        )

    with pytest.raises(ValueError):
        decode_access_token(_encode(REQUIRED_PAYLOAD), now=datetime(2026, 1, 15))


def test_placeholder_secret_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        SecretStr("replace-with-a-long-random-secret"),
    )

    with pytest.raises(SecurityConfigurationError):
        create_access_token(
            user_id=USER_ID,
            institution_id=INSTITUTION_ID,
            roles=["student"],
            now=NOW,
        )

    with pytest.raises(SecurityConfigurationError):
        decode_access_token(_encode(REQUIRED_PAYLOAD), now=NOW)


def test_sensitive_password_fields_are_absent() -> None:
    token, _ = create_access_token(
        user_id=USER_ID,
        institution_id=INSTITUTION_ID,
        roles=["student"],
        now=NOW,
    )
    payload = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"verify_exp": False},
    )

    assert "password" not in payload
    assert "password_hash" not in payload


def test_token_operations_do_not_print_token_or_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    token, _ = create_access_token(
        user_id=USER_ID,
        institution_id=INSTITUTION_ID,
        roles=["student"],
        now=NOW,
    )
    decode_access_token(token, now=NOW)

    captured = capsys.readouterr()
    assert token not in captured.out
    assert token not in captured.err
    assert TEST_SECRET not in captured.out
    assert TEST_SECRET not in captured.err
