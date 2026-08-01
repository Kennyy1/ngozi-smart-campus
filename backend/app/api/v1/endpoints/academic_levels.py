from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.academic_level import (
    AcademicLevelCreate,
    AcademicLevelRead,
    AcademicLevelStatus,
    AcademicLevelUpdate,
)
from app.services.academic_level_service import (
    AcademicLevelNotFoundError,
    AcademicLevelProgrammeNotFoundError,
    DuplicateAcademicLevelCodeError,
    DuplicateAcademicLevelError,
    DuplicateAcademicLevelNameError,
    DuplicateAcademicLevelSequenceError,
    create_academic_level,
    delete_academic_level,
    get_academic_level,
    list_academic_levels,
    update_academic_level,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(prefix="/academic-levels", tags=["Academic Levels"])
AcademicLevelAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post("", response_model=AcademicLevelRead, status_code=status.HTTP_201_CREATED)
def create_academic_level_endpoint(
    request: AcademicLevelCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicLevelAdministrator,
) -> AcademicLevelRead:
    try:
        return create_academic_level(
            session,
            institution_id=authenticated.institution.id,
            academic_level_data=request,
        )
    except AcademicLevelProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except (
        DuplicateAcademicLevelNameError,
        DuplicateAcademicLevelCodeError,
        DuplicateAcademicLevelSequenceError,
        DuplicateAcademicLevelError,
    ) as error:
        raise _duplicate_error(error) from error


@router.get("", response_model=list[AcademicLevelRead])
def list_academic_levels_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicLevelAdministrator,
    programme_id: UUID | None = None,
    status: AcademicLevelStatus | None = None,
) -> list[AcademicLevelRead]:
    return list_academic_levels(
        session,
        institution_id=authenticated.institution.id,
        programme_id=programme_id,
        status=status,
    )


@router.get("/{academic_level_id}", response_model=AcademicLevelRead)
def get_academic_level_endpoint(
    academic_level_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicLevelAdministrator,
) -> AcademicLevelRead:
    try:
        return get_academic_level(
            session,
            academic_level_id=academic_level_id,
            institution_id=authenticated.institution.id,
        )
    except AcademicLevelNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{academic_level_id}", response_model=AcademicLevelRead)
def update_academic_level_endpoint(
    academic_level_id: UUID,
    request: AcademicLevelUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicLevelAdministrator,
) -> AcademicLevelRead:
    try:
        return update_academic_level(
            session,
            academic_level_id=academic_level_id,
            institution_id=authenticated.institution.id,
            academic_level_data=request,
        )
    except AcademicLevelNotFoundError as error:
        raise _not_found_error() from error
    except AcademicLevelProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except (
        DuplicateAcademicLevelNameError,
        DuplicateAcademicLevelCodeError,
        DuplicateAcademicLevelSequenceError,
        DuplicateAcademicLevelError,
    ) as error:
        raise _duplicate_error(error) from error


@router.delete("/{academic_level_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_academic_level_endpoint(
    academic_level_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AcademicLevelAdministrator,
) -> Response:
    try:
        delete_academic_level(
            session,
            academic_level_id=academic_level_id,
            institution_id=authenticated.institution.id,
        )
    except AcademicLevelNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Academic Level not found")


def _programme_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Programme not found")


def _duplicate_error(error: Exception) -> HTTPException:
    if isinstance(error, DuplicateAcademicLevelNameError):
        detail = "Academic Level name already exists in this Programme"
    elif isinstance(error, DuplicateAcademicLevelCodeError):
        detail = "Academic Level code already exists in this Programme"
    elif isinstance(error, DuplicateAcademicLevelSequenceError):
        detail = "Academic Level sequence number already exists in this Programme"
    else:
        detail = "Academic Level already exists"
    return HTTPException(status_code=409, detail=detail)
