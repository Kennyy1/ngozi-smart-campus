from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.department_service import (
    DepartmentFacultyNotFoundError,
    DepartmentNotFoundError,
    DuplicateDepartmentCodeError,
    DuplicateDepartmentError,
    DuplicateDepartmentNameError,
    create_department,
    delete_department,
    get_department,
    list_departments,
    update_department,
)


router = APIRouter(prefix="/departments", tags=["Departments"])
DepartmentAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department_endpoint(
    request: DepartmentCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: DepartmentAdministrator,
) -> DepartmentResponse:
    try:
        return create_department(
            session,
            institution_id=authenticated.institution.id,
            department_data=request,
        )
    except DepartmentFacultyNotFoundError as error:
        raise _faculty_not_found_error() from error
    except (
        DuplicateDepartmentCodeError,
        DuplicateDepartmentNameError,
        DuplicateDepartmentError,
    ) as error:
        raise _duplicate_error(error) from error


@router.get("", response_model=list[DepartmentResponse])
def list_departments_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: DepartmentAdministrator,
    faculty_id: UUID | None = None,
) -> list[DepartmentResponse]:
    return list_departments(
        session,
        institution_id=authenticated.institution.id,
        faculty_id=faculty_id,
    )


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department_endpoint(
    department_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: DepartmentAdministrator,
) -> DepartmentResponse:
    try:
        return get_department(
            session,
            department_id=department_id,
            institution_id=authenticated.institution.id,
        )
    except DepartmentNotFoundError as error:
        raise _department_not_found_error() from error


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department_endpoint(
    department_id: UUID,
    request: DepartmentUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: DepartmentAdministrator,
) -> DepartmentResponse:
    try:
        return update_department(
            session,
            department_id=department_id,
            institution_id=authenticated.institution.id,
            department_data=request,
        )
    except DepartmentNotFoundError as error:
        raise _department_not_found_error() from error
    except DepartmentFacultyNotFoundError as error:
        raise _faculty_not_found_error() from error
    except (
        DuplicateDepartmentCodeError,
        DuplicateDepartmentNameError,
        DuplicateDepartmentError,
    ) as error:
        raise _duplicate_error(error) from error


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_department_endpoint(
    department_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: DepartmentAdministrator,
) -> Response:
    try:
        delete_department(
            session,
            department_id=department_id,
            institution_id=authenticated.institution.id,
        )
    except DepartmentNotFoundError as error:
        raise _department_not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _department_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Department not found",
    )


def _faculty_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Faculty not found",
    )


def _duplicate_error(error: Exception) -> HTTPException:
    if isinstance(error, DuplicateDepartmentCodeError):
        detail = "Department code already exists"
    elif isinstance(error, DuplicateDepartmentNameError):
        detail = "Department name already exists in this faculty"
    else:
        detail = "Department already exists"
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
