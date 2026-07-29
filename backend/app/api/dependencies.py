from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthenticationError,
    ExpiredTokenError,
    InactiveAccountError,
    InvalidTokenError,
)
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.services.authentication import (
    AuthenticatedUserContext,
    load_authenticated_user,
)


bearer_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[Session, Depends(get_db_session)],
) -> AuthenticatedUserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_http_error("Authentication required")

    try:
        claims = decode_access_token(credentials.credentials)
        return load_authenticated_user(
            session,
            user_id=claims.sub,
            institution_id=claims.institution_id,
        )
    except ExpiredTokenError as error:
        raise _authentication_http_error("Token expired") from error
    except InactiveAccountError as error:
        raise _authentication_http_error("Account unavailable") from error
    except InvalidTokenError as error:
        raise _authentication_http_error("Authentication required") from error
    except AuthenticationError as error:
        raise _authentication_http_error("Authentication required") from error


def require_roles(
    *required_roles: str,
) -> Callable[[AuthenticatedUserContext], AuthenticatedUserContext]:
    if not required_roles:
        raise ValueError("At least one role is required")

    normalized_roles = tuple(role.strip().lower() for role in required_roles)
    if any(not role for role in normalized_roles):
        raise ValueError("Role names must not be blank")
    required = frozenset(normalized_roles)

    def role_dependency(
        current_user: Annotated[
            AuthenticatedUserContext,
            Depends(get_current_user),
        ],
    ) -> AuthenticatedUserContext:
        current_roles = {
            role.strip().lower() for role in current_user.roles if role.strip()
        }
        if required.isdisjoint(current_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return current_user

    return role_dependency


def _authentication_http_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
