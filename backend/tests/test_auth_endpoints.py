from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.api import dependencies
from app.api.v1.endpoints import auth
from app.core.exceptions import InactiveAccountError, InvalidCredentialsError
from app.main import app
from app.models.institution import Institution
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services.authentication import AuthenticatedUserContext


PASSWORD = "endpoint-test-password"
TOKEN = "signed-access-token-value"


class FakeSession:
    pass


def _authenticated_context() -> AuthenticatedUserContext:
    institution = Institution(
        id=uuid4(),
        name="Test University",
        code="TEST",
        status="active",
    )
    user = User(
        id=uuid4(),
        institution_id=institution.id,
        email="user@example.edu",
        password_hash="never-return-this-hash",
        first_name="Ada",
        last_name="Student",
        phone=None,
        is_active=True,
        is_verified=True,
    )
    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=("lecturer", "student"),
    )


def test_login_returns_bearer_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _authenticated_context()
    received: dict[str, str] = {}

    def fake_authenticate(
        session: object,
        *,
        institution_code: str,
        email: str,
        password: str,
    ) -> AuthenticatedUserContext:
        received.update(
            institution_code=institution_code,
            email=email,
            password=password,
        )
        return context

    monkeypatch.setattr(auth, "authenticate_user", fake_authenticate)
    monkeypatch.setattr(auth, "create_access_token", lambda **_: (TOKEN, 900))
    request = LoginRequest(
        institution_code="  TEST  ",
        email="  USER@EXAMPLE.EDU ",
        password=PASSWORD,
    )

    response = auth.login(request, FakeSession())  # type: ignore[arg-type]

    assert response.model_dump() == {
        "access_token": TOKEN,
        "token_type": "bearer",
        "expires_in": 900,
    }
    assert received == {
        "institution_code": "TEST",
        "email": "user@example.edu",
        "password": PASSWORD,
    }

    login_route = next(
        route
        for route in auth.router.routes
        if isinstance(route, APIRoute) and route.path == "/auth/login"
    )
    assert login_route.status_code == 200


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (InvalidCredentialsError(), "Invalid credentials"),
        (InactiveAccountError(), "Account unavailable"),
    ],
)
def test_login_failures_are_safe(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    detail: str,
) -> None:
    def reject_authentication(*_: object, **__: object) -> None:
        raise error

    monkeypatch.setattr(auth, "authenticate_user", reject_authentication)
    request = LoginRequest(
        institution_code="TEST",
        email="user@example.edu",
        password=PASSWORD,
    )

    with pytest.raises(HTTPException) as raised:
        auth.login(request, FakeSession())  # type: ignore[arg-type]

    assert raised.value.status_code == 401
    assert raised.value.detail == detail
    assert raised.value.headers == {"WWW-Authenticate": "Bearer"}
    assert "institution" not in detail.lower()
    assert "user@example.edu" not in detail


def test_me_without_bearer_token_returns_401() -> None:
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(None, FakeSession())  # type: ignore[arg-type]

    assert raised.value.status_code == 401
    assert raised.value.detail == "Authentication required"
    assert raised.value.headers == {"WWW-Authenticate": "Bearer"}


def test_me_with_invalid_token_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = dependencies.HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-token",
    )
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda _: (_ for _ in ()).throw(InvalidCredentialsError()),
    )

    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(
            credentials,
            FakeSession(),  # type: ignore[arg-type]
        )

    assert raised.value.status_code == 401
    assert raised.value.detail == "Authentication required"


def test_me_returns_safe_current_user_data() -> None:
    context = _authenticated_context()

    response = auth.get_me(context)
    payload = response.model_dump(mode="json")

    assert payload == {
        "id": str(context.user.id),
        "institution_id": str(context.institution.id),
        "institution_code": "TEST",
        "email": "user@example.edu",
        "first_name": "Ada",
        "last_name": "Student",
        "phone": None,
        "is_active": True,
        "is_verified": True,
        "roles": ["lecturer", "student"],
    }
    assert "password_hash" not in payload


def test_auth_and_health_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])

    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/me" in paths
    assert "/health" in paths


def test_endpoints_do_not_print_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        auth,
        "authenticate_user",
        lambda *_, **__: _authenticated_context(),
    )
    monkeypatch.setattr(auth, "create_access_token", lambda **_: (TOKEN, 900))

    auth.login(
        LoginRequest(
            institution_code="TEST",
            email="user@example.edu",
            password=PASSWORD,
        ),
        FakeSession(),  # type: ignore[arg-type]
    )

    captured = capsys.readouterr()
    for sensitive_value in (PASSWORD, TOKEN):
        assert sensitive_value not in captured.out
        assert sensitive_value not in captured.err
