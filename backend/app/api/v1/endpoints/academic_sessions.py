from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.academic_session import (
    AcademicSessionCreate,
    AcademicSessionRead,
    AcademicSessionStatus,
    AcademicSessionUpdate,
)
from app.services.academic_session_service import (
    AcademicSessionNotFoundError,
    DuplicateAcademicSessionError,
    DuplicateAcademicSessionNameError,
    InvalidAcademicSessionDateRangeError,
    create_academic_session,
    delete_academic_session,
    get_academic_session,
    get_current_academic_session,
    list_academic_sessions,
    update_academic_session,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(prefix="/academic-sessions", tags=["Academic Sessions"])
AcademicSessionAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post(
    "",
    response_model=AcademicSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_academic_session_endpoint(
    request: AcademicSessionCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicSessionAdministrator,
) -> AcademicSessionRead:
    try:
        return create_academic_session(
            session,
            institution_id=authenticated.institution.id,
            academic_session_data=request,
        )
    except (
        DuplicateAcademicSessionNameError,
        DuplicateAcademicSessionError,
    ) as error:
        raise _duplicate_error() from error


@router.get("", response_model=list[AcademicSessionRead])
def list_academic_sessions_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicSessionAdministrator,
    status: AcademicSessionStatus | None = None,
    is_current: bool | None = None,
) -> list[AcademicSessionRead]:
    return list_academic_sessions(
        session,
        institution_id=authenticated.institution.id,
        status=status,
        is_current=is_current,
    )


@router.get("/current", response_model=AcademicSessionRead)
def get_current_academic_session_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicSessionAdministrator,
) -> AcademicSessionRead:
    try:
        return get_current_academic_session(
            session,
            institution_id=authenticated.institution.id,
        )
    except AcademicSessionNotFoundError as error:
        raise _not_found_error() from error


@router.get("/{academic_session_id}", response_model=AcademicSessionRead)
def get_academic_session_endpoint(
    academic_session_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicSessionAdministrator,
) -> AcademicSessionRead:
    try:
        return get_academic_session(
            session,
            academic_session_id=academic_session_id,
            institution_id=authenticated.institution.id,
        )
    except AcademicSessionNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{academic_session_id}", response_model=AcademicSessionRead)
def update_academic_session_endpoint(
    academic_session_id: UUID,
    request: AcademicSessionUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicSessionAdministrator,
) -> AcademicSessionRead:
    try:
        return update_academic_session(
            session,
            academic_session_id=academic_session_id,
            institution_id=authenticated.institution.id,
            academic_session_data=request,
        )
    except AcademicSessionNotFoundError as error:
        raise _not_found_error() from error
    except InvalidAcademicSessionDateRangeError as error:
        raise HTTPException(
            status_code=422,
            detail="start_date must be earlier than end_date",
        ) from error
    except (
        DuplicateAcademicSessionNameError,
        DuplicateAcademicSessionError,
    ) as error:
        raise _duplicate_error() from error


@router.delete(
    "/{academic_session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_academic_session_endpoint(
    academic_session_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicSessionAdministrator,
) -> Response:
    try:
        delete_academic_session(
            session,
            academic_session_id=academic_session_id,
            institution_id=authenticated.institution.id,
        )
    except AcademicSessionNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Academic session not found")


def _duplicate_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail="Academic session name already exists",
    )
