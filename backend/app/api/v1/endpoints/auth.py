from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db_session
from app.core.exceptions import InactiveAccountError, InvalidCredentialsError
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import AuthenticatedUserResponse
from app.services.authentication import (
    AuthenticatedUserContext,
    authenticate_user,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(
    request: LoginRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> LoginResponse:
    try:
        authenticated = authenticate_user(
            session,
            institution_code=request.institution_code,
            email=str(request.email),
            password=request.password,
        )
    except InvalidCredentialsError as error:
        raise _login_http_error("Invalid credentials") from error
    except InactiveAccountError as error:
        raise _login_http_error("Account unavailable") from error

    token, expires_in = create_access_token(
        user_id=authenticated.user.id,
        institution_id=authenticated.institution.id,
        roles=authenticated.roles,
    )
    return LoginResponse(access_token=token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=AuthenticatedUserResponse,
    status_code=status.HTTP_200_OK,
)
def get_me(
    authenticated: Annotated[
        AuthenticatedUserContext,
        Depends(get_current_user),
    ],
) -> AuthenticatedUserResponse:
    user = authenticated.user
    return AuthenticatedUserResponse(
        id=user.id,
        institution_id=authenticated.institution.id,
        institution_code=authenticated.institution.code,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        is_active=user.is_active,
        is_verified=user.is_verified,
        roles=list(authenticated.roles),
    )


def _login_http_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
