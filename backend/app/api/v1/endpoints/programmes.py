from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.programme import (
    ProgrammeAward,
    ProgrammeCreate,
    ProgrammeResponse,
    ProgrammeUpdate,
    StudyMode,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.programme_service import (
    DuplicateProgrammeCodeError,
    DuplicateProgrammeError,
    DuplicateProgrammeNameError,
    ProgrammeDepartmentNotFoundError,
    ProgrammeFacultyNotFoundError,
    ProgrammeNotFoundError,
    create_programme,
    delete_programme,
    get_programme,
    list_programmes,
    update_programme,
)


router = APIRouter(prefix="/programmes", tags=["Programmes"])
ProgrammeAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post(
    "",
    response_model=ProgrammeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_programme_endpoint(
    request: ProgrammeCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ProgrammeAdministrator,
) -> ProgrammeResponse:
    try:
        return create_programme(
            session,
            institution_id=authenticated.institution.id,
            programme_data=request,
        )
    except ProgrammeFacultyNotFoundError as error:
        raise _faculty_not_found_error() from error
    except ProgrammeDepartmentNotFoundError as error:
        raise _department_not_found_error() from error
    except (
        DuplicateProgrammeCodeError,
        DuplicateProgrammeNameError,
        DuplicateProgrammeError,
    ) as error:
        raise _duplicate_error(error) from error


@router.get("", response_model=list[ProgrammeResponse])
def list_programmes_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ProgrammeAdministrator,
    faculty_id: UUID | None = None,
    department_id: UUID | None = None,
    award: ProgrammeAward | None = None,
    study_mode: StudyMode | None = None,
) -> list[ProgrammeResponse]:
    return list_programmes(
        session,
        institution_id=authenticated.institution.id,
        faculty_id=faculty_id,
        department_id=department_id,
        award=award,
        study_mode=study_mode,
    )


@router.get("/{programme_id}", response_model=ProgrammeResponse)
def get_programme_endpoint(
    programme_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ProgrammeAdministrator,
) -> ProgrammeResponse:
    try:
        return get_programme(
            session,
            programme_id=programme_id,
            institution_id=authenticated.institution.id,
        )
    except ProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error


@router.patch("/{programme_id}", response_model=ProgrammeResponse)
def update_programme_endpoint(
    programme_id: UUID,
    request: ProgrammeUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ProgrammeAdministrator,
) -> ProgrammeResponse:
    try:
        return update_programme(
            session,
            programme_id=programme_id,
            institution_id=authenticated.institution.id,
            programme_data=request,
        )
    except ProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except ProgrammeFacultyNotFoundError as error:
        raise _faculty_not_found_error() from error
    except ProgrammeDepartmentNotFoundError as error:
        raise _department_not_found_error() from error
    except (
        DuplicateProgrammeCodeError,
        DuplicateProgrammeNameError,
        DuplicateProgrammeError,
    ) as error:
        raise _duplicate_error(error) from error


@router.delete(
    "/{programme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_programme_endpoint(
    programme_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ProgrammeAdministrator,
) -> Response:
    try:
        delete_programme(
            session,
            programme_id=programme_id,
            institution_id=authenticated.institution.id,
        )
    except ProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _programme_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Programme not found")


def _faculty_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Faculty not found")


def _department_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Department not found")


def _duplicate_error(error: Exception) -> HTTPException:
    if isinstance(error, DuplicateProgrammeCodeError):
        detail = "Programme code already exists"
    elif isinstance(error, DuplicateProgrammeNameError):
        detail = "Programme name already exists in this department"
    else:
        detail = "Programme already exists"
    return HTTPException(status_code=409, detail=detail)
