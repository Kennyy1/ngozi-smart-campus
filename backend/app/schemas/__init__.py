from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.token import AccessTokenClaims, TokenResponse
from app.schemas.user import AuthenticatedUserResponse

__all__ = [
    "AccessTokenClaims",
    "AuthenticatedUserResponse",
    "LoginRequest",
    "LoginResponse",
    "TokenResponse",
]
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.schemas.faculty import FacultyCreate, FacultyResponse, FacultyUpdate

__all__ = [
    "DepartmentCreate",
    "DepartmentResponse",
    "DepartmentUpdate",
    "FacultyCreate",
    "FacultyResponse",
    "FacultyUpdate",
]
