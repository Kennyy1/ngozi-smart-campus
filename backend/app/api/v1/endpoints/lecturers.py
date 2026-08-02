from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.lecturer import AcademicRank, EmploymentStatus, LecturerCreate, LecturerRead, LecturerUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.lecturer_service import DuplicateLecturerEmailError, DuplicateLecturerError, DuplicateStaffNumberError, LecturerDepartmentNotFoundError, LecturerNotFoundError, create_lecturer, delete_lecturer, get_lecturer, get_lecturer_by_staff_number, list_lecturers, update_lecturer

router = APIRouter(prefix="/lecturers", tags=["Lecturers"])
LecturerAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


@router.post("", response_model=LecturerRead, status_code=status.HTTP_201_CREATED)
def create_lecturer_endpoint(request: LecturerCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: LecturerAdministrator) -> LecturerRead:
    try: return create_lecturer(session, institution_id=authenticated.institution.id, lecturer_data=request)
    except LecturerDepartmentNotFoundError as error: raise _department_not_found_error() from error
    except (DuplicateLecturerEmailError, DuplicateStaffNumberError, DuplicateLecturerError) as error: raise _duplicate_error(error) from error


@router.get("", response_model=list[LecturerRead])
def list_lecturers_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: LecturerAdministrator, department_id: UUID | None = None, academic_rank: AcademicRank | None = None, employment_status: EmploymentStatus | None = None, is_active: bool | None = None) -> list[LecturerRead]:
    return list_lecturers(session, institution_id=authenticated.institution.id, department_id=department_id, academic_rank=academic_rank, employment_status=employment_status, is_active=is_active)


@router.get("/by-staff-number/{staff_number:path}", response_model=LecturerRead)
def get_lecturer_by_staff_number_endpoint(staff_number: str, session: Annotated[Session, Depends(get_db_session)], authenticated: LecturerAdministrator) -> LecturerRead:
    try: return get_lecturer_by_staff_number(session, staff_number=staff_number, institution_id=authenticated.institution.id)
    except LecturerNotFoundError as error: raise _not_found_error() from error


@router.get("/{lecturer_id}", response_model=LecturerRead)
def get_lecturer_endpoint(lecturer_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: LecturerAdministrator) -> LecturerRead:
    try: return get_lecturer(session, lecturer_id=lecturer_id, institution_id=authenticated.institution.id)
    except LecturerNotFoundError as error: raise _not_found_error() from error


@router.patch("/{lecturer_id}", response_model=LecturerRead)
def update_lecturer_endpoint(lecturer_id: UUID, request: LecturerUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: LecturerAdministrator) -> LecturerRead:
    try: return update_lecturer(session, lecturer_id=lecturer_id, institution_id=authenticated.institution.id, lecturer_data=request)
    except LecturerNotFoundError as error: raise _not_found_error() from error
    except LecturerDepartmentNotFoundError as error: raise _department_not_found_error() from error
    except (DuplicateLecturerEmailError, DuplicateStaffNumberError, DuplicateLecturerError) as error: raise _duplicate_error(error) from error


@router.delete("/{lecturer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lecturer_endpoint(lecturer_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: LecturerAdministrator) -> Response:
    try: delete_lecturer(session, lecturer_id=lecturer_id, institution_id=authenticated.institution.id)
    except LecturerNotFoundError as error: raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException: return HTTPException(status_code=404, detail="Lecturer not found")
def _department_not_found_error() -> HTTPException: return HTTPException(status_code=404, detail="Department not found")
def _duplicate_error(error: Exception) -> HTTPException:
    detail = "Lecturer email already exists" if isinstance(error, DuplicateLecturerEmailError) else "Staff number already exists" if isinstance(error, DuplicateStaffNumberError) else "Lecturer already exists"
    return HTTPException(status_code=409, detail=detail)
