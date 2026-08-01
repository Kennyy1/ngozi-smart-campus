from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.semester import SemesterCreate, SemesterRead, SemesterStatus, SemesterUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.semester_service import (
    DuplicateSemesterError, DuplicateSemesterNameError, DuplicateSemesterSequenceError,
    InactiveCurrentAcademicSessionError, InvalidSemesterDateRangeError,
    SemesterAcademicSessionNotFoundError, SemesterNotFoundError,
    SemesterOutsideAcademicSessionError, create_semester, delete_semester,
    get_current_semester, get_semester, list_semesters, update_semester,
)

router = APIRouter(prefix="/semesters", tags=["Semesters"])
SemesterAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


@router.post("", response_model=SemesterRead, status_code=status.HTTP_201_CREATED)
def create_semester_endpoint(request: SemesterCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: SemesterAdministrator) -> SemesterRead:
    try:
        return create_semester(session, institution_id=authenticated.institution.id, semester_data=request)
    except SemesterAcademicSessionNotFoundError as error:
        raise _academic_session_not_found() from error
    except (DuplicateSemesterNameError, DuplicateSemesterSequenceError, DuplicateSemesterError) as error:
        raise _duplicate_error(error) from error
    except InactiveCurrentAcademicSessionError as error:
        raise HTTPException(status_code=422, detail="Current Semester requires a current Academic Session") from error
    except (InvalidSemesterDateRangeError, SemesterOutsideAcademicSessionError) as error:
        raise _date_error(error) from error


@router.get("", response_model=list[SemesterRead])
def list_semesters_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: SemesterAdministrator, academic_session_id: UUID | None = None, status: SemesterStatus | None = None, is_current: bool | None = None) -> list[SemesterRead]:
    return list_semesters(session, institution_id=authenticated.institution.id, academic_session_id=academic_session_id, status=status, is_current=is_current)


@router.get("/current", response_model=SemesterRead)
def get_current_semester_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: SemesterAdministrator) -> SemesterRead:
    try:
        return get_current_semester(session, institution_id=authenticated.institution.id)
    except SemesterNotFoundError as error:
        raise _not_found() from error


@router.get("/{semester_id}", response_model=SemesterRead)
def get_semester_endpoint(semester_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: SemesterAdministrator) -> SemesterRead:
    try:
        return get_semester(session, semester_id=semester_id, institution_id=authenticated.institution.id)
    except SemesterNotFoundError as error:
        raise _not_found() from error


@router.patch("/{semester_id}", response_model=SemesterRead)
def update_semester_endpoint(semester_id: UUID, request: SemesterUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: SemesterAdministrator) -> SemesterRead:
    try:
        return update_semester(session, semester_id=semester_id, institution_id=authenticated.institution.id, semester_data=request)
    except SemesterNotFoundError as error:
        raise _not_found() from error
    except SemesterAcademicSessionNotFoundError as error:
        raise _academic_session_not_found() from error
    except (DuplicateSemesterNameError, DuplicateSemesterSequenceError, DuplicateSemesterError) as error:
        raise _duplicate_error(error) from error
    except InactiveCurrentAcademicSessionError as error:
        raise HTTPException(status_code=422, detail="Current Semester requires a current Academic Session") from error
    except (InvalidSemesterDateRangeError, SemesterOutsideAcademicSessionError) as error:
        raise _date_error(error) from error


@router.delete("/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semester_endpoint(semester_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: SemesterAdministrator) -> Response:
    try:
        delete_semester(session, semester_id=semester_id, institution_id=authenticated.institution.id)
    except SemesterNotFoundError as error:
        raise _not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Semester not found")


def _academic_session_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Academic session not found")


def _duplicate_error(error: Exception) -> HTTPException:
    detail = "Semester sequence number already exists" if isinstance(error, DuplicateSemesterSequenceError) else "Semester name already exists"
    return HTTPException(status_code=409, detail=detail)


def _date_error(error: Exception) -> HTTPException:
    detail = "Semester dates must fall within the Academic Session" if isinstance(error, SemesterOutsideAcademicSessionError) else "start_date must be earlier than end_date"
    return HTTPException(status_code=422, detail=detail)
