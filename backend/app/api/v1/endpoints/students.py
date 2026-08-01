from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.student import EnrollmentStatus, StudentCreate, StudentRead, StudentUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.student_service import (
    DuplicateMatriculationNumberError, DuplicateStudentEmailError,
    DuplicateStudentError, InvalidStudentCurrentLevelError,
    InvalidStudentGraduationStateError, StudentNotFoundError,
    StudentProgrammeNotFoundError, create_student, delete_student, get_student,
    get_student_by_matriculation, list_students, update_student,
)


router = APIRouter(prefix="/students", tags=["Students"])
StudentAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student_endpoint(request: StudentCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: StudentAdministrator) -> StudentRead:
    try:
        return create_student(session, institution_id=authenticated.institution.id, student_data=request)
    except StudentProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except InvalidStudentCurrentLevelError as error:
        raise _current_level_error() from error
    except (DuplicateStudentEmailError, DuplicateMatriculationNumberError, DuplicateStudentError) as error:
        raise _duplicate_error(error) from error


@router.get("", response_model=list[StudentRead])
def list_students_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: StudentAdministrator,
    programme_id: UUID | None = None,
    enrollment_status: EnrollmentStatus | None = None,
    admission_year: int | None = None,
    current_level: str | None = None,
    is_active: bool | None = None,
) -> list[StudentRead]:
    return list_students(session, institution_id=authenticated.institution.id, programme_id=programme_id, enrollment_status=enrollment_status, admission_year=admission_year, current_level=current_level, is_active=is_active)


@router.get("/by-matriculation/{matriculation_number}", response_model=StudentRead)
def get_student_by_matriculation_endpoint(matriculation_number: str, session: Annotated[Session, Depends(get_db_session)], authenticated: StudentAdministrator) -> StudentRead:
    try:
        return get_student_by_matriculation(session, matriculation_number=matriculation_number, institution_id=authenticated.institution.id)
    except StudentNotFoundError as error:
        raise _not_found_error() from error


@router.get("/{student_id}", response_model=StudentRead)
def get_student_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: StudentAdministrator) -> StudentRead:
    try:
        return get_student(session, student_id=student_id, institution_id=authenticated.institution.id)
    except StudentNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{student_id}", response_model=StudentRead)
def update_student_endpoint(student_id: UUID, request: StudentUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: StudentAdministrator) -> StudentRead:
    try:
        return update_student(session, student_id=student_id, institution_id=authenticated.institution.id, student_data=request)
    except StudentNotFoundError as error:
        raise _not_found_error() from error
    except StudentProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except InvalidStudentCurrentLevelError as error:
        raise _current_level_error() from error
    except InvalidStudentGraduationStateError as error:
        raise _graduation_error() from error
    except (DuplicateStudentEmailError, DuplicateMatriculationNumberError, DuplicateStudentError) as error:
        raise _duplicate_error(error) from error


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: StudentAdministrator) -> Response:
    try:
        delete_student(session, student_id=student_id, institution_id=authenticated.institution.id)
    except StudentNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Student not found")


def _programme_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Programme not found")


def _current_level_error() -> HTTPException:
    return HTTPException(status_code=422, detail="Invalid current level for Programme")


def _graduation_error() -> HTTPException:
    return HTTPException(status_code=422, detail="Invalid graduation state")


def _duplicate_error(error: Exception) -> HTTPException:
    if isinstance(error, DuplicateStudentEmailError):
        detail = "Student email already exists"
    elif isinstance(error, DuplicateMatriculationNumberError):
        detail = "Matriculation number already exists"
    else:
        detail = "Student already exists"
    return HTTPException(status_code=409, detail=detail)
