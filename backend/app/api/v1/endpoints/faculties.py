from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.faculty import FacultyCreate, FacultyResponse, FacultyUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.faculty_service import (
    DuplicateFacultyCodeError,
    FacultyNotFoundError,
    create_faculty,
    delete_faculty,
    get_faculty,
    list_faculties,
    update_faculty,
)


router = APIRouter(prefix="/faculties", tags=["Faculties"])
FacultyAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post(
    "",
    response_model=FacultyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_faculty_endpoint(
    request: FacultyCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: FacultyAdministrator,
) -> FacultyResponse:
    try:
        return create_faculty(
            session,
            institution_id=authenticated.institution.id,
            faculty_data=request,
        )
    except DuplicateFacultyCodeError as error:
        raise _duplicate_code_error() from error


@router.get("", response_model=list[FacultyResponse])
def list_faculties_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: FacultyAdministrator,
) -> list[FacultyResponse]:
    return list_faculties(
        session,
        institution_id=authenticated.institution.id,
    )


@router.get("/{id}", response_model=FacultyResponse)
def get_faculty_endpoint(
    id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: FacultyAdministrator,
) -> FacultyResponse:
    try:
        return get_faculty(
            session,
            faculty_id=id,
            institution_id=authenticated.institution.id,
        )
    except FacultyNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{id}", response_model=FacultyResponse)
def update_faculty_endpoint(
    id: UUID,
    request: FacultyUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: FacultyAdministrator,
) -> FacultyResponse:
    try:
        return update_faculty(
            session,
            faculty_id=id,
            institution_id=authenticated.institution.id,
            faculty_data=request,
        )
    except FacultyNotFoundError as error:
        raise _not_found_error() from error
    except DuplicateFacultyCodeError as error:
        raise _duplicate_code_error() from error


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_faculty_endpoint(
    id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: FacultyAdministrator,
) -> Response:
    try:
        delete_faculty(
            session,
            faculty_id=id,
            institution_id=authenticated.institution.id,
        )
    except FacultyNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Faculty not found",
    )


def _duplicate_code_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Faculty code already exists",
    )
