from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.models.lecturer_assignment import LecturerAssignment
from app.schemas.lecturer_assignment import AssignmentRole, AssignmentStatus, LecturerAssignmentCreate, LecturerAssignmentRead, LecturerAssignmentUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.lecturer_assignment_service import AssignmentCourseOfferingNotFoundError, AssignmentLecturerNotFoundError, CourseOfferingUnavailableError, DuplicateLecturerAssignmentError, DuplicatePrimaryLecturerError, InvalidLecturerAssignmentError, LecturerAssignmentConflictError, LecturerAssignmentNotFoundError, LecturerUnavailableError, create_lecturer_assignment, delete_lecturer_assignment, get_lecturer_assignment, list_lecturer_assignments, update_lecturer_assignment

router = APIRouter(prefix="/lecturer-assignments", tags=["Lecturer Assignments"])
AssignmentAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


@router.post("", response_model=LecturerAssignmentRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: LecturerAssignmentCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: AssignmentAdministrator) -> LecturerAssignment:
    try: return create_lecturer_assignment(session, institution_id=authenticated.institution.id, lecturer_assignment_data=request)
    except (AssignmentLecturerNotFoundError, AssignmentCourseOfferingNotFoundError) as error: raise _reference_error(error) from error
    except (LecturerUnavailableError, CourseOfferingUnavailableError) as error: raise HTTPException(status_code=409, detail="Lecturer or Course Offering is inactive") from error
    except InvalidLecturerAssignmentError as error: raise HTTPException(status_code=422, detail="Invalid Lecturer Assignment") from error
    except (DuplicateLecturerAssignmentError, DuplicatePrimaryLecturerError, LecturerAssignmentConflictError) as error: raise _conflict_error(error) from error


@router.get("", response_model=list[LecturerAssignmentRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: AssignmentAdministrator, lecturer_id: UUID | None = None, course_offering_id: UUID | None = None, assignment_role: AssignmentRole | None = None, is_primary: bool | None = None, status: AssignmentStatus | None = None) -> list[LecturerAssignment]:
    return list_lecturer_assignments(session, institution_id=authenticated.institution.id, lecturer_id=lecturer_id, course_offering_id=course_offering_id, assignment_role=assignment_role, is_primary=is_primary, status=status)


@router.get("/{lecturer_assignment_id}", response_model=LecturerAssignmentRead)
def get_endpoint(lecturer_assignment_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AssignmentAdministrator) -> LecturerAssignment:
    try: return get_lecturer_assignment(session, lecturer_assignment_id=lecturer_assignment_id, institution_id=authenticated.institution.id)
    except LecturerAssignmentNotFoundError as error: raise _not_found_error() from error


@router.patch("/{lecturer_assignment_id}", response_model=LecturerAssignmentRead)
def update_endpoint(lecturer_assignment_id: UUID, request: LecturerAssignmentUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: AssignmentAdministrator) -> LecturerAssignment:
    try: return update_lecturer_assignment(session, lecturer_assignment_id=lecturer_assignment_id, institution_id=authenticated.institution.id, lecturer_assignment_data=request)
    except LecturerAssignmentNotFoundError as error: raise _not_found_error() from error
    except (AssignmentLecturerNotFoundError, AssignmentCourseOfferingNotFoundError) as error: raise _reference_error(error) from error
    except (LecturerUnavailableError, CourseOfferingUnavailableError) as error: raise HTTPException(status_code=409, detail="Lecturer or Course Offering is inactive") from error
    except InvalidLecturerAssignmentError as error: raise HTTPException(status_code=422, detail="Invalid Lecturer Assignment") from error
    except (DuplicateLecturerAssignmentError, DuplicatePrimaryLecturerError, LecturerAssignmentConflictError) as error: raise _conflict_error(error) from error


@router.delete("/{lecturer_assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(lecturer_assignment_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AssignmentAdministrator) -> Response:
    try: delete_lecturer_assignment(session, lecturer_assignment_id=lecturer_assignment_id, institution_id=authenticated.institution.id)
    except LecturerAssignmentNotFoundError as error: raise _not_found_error() from error
    return Response(status_code=204)


def _not_found_error() -> HTTPException: return HTTPException(status_code=404, detail="Lecturer Assignment not found")
def _reference_error(error: Exception) -> HTTPException: return HTTPException(status_code=404, detail="Lecturer not found" if isinstance(error, AssignmentLecturerNotFoundError) else "Course Offering not found")
def _conflict_error(error: Exception) -> HTTPException:
    detail = "Lecturer is already assigned to Course Offering" if isinstance(error, DuplicateLecturerAssignmentError) else "Course Offering already has a primary Lecturer" if isinstance(error, DuplicatePrimaryLecturerError) else "Lecturer Assignment conflict"
    return HTTPException(status_code=409, detail=detail)
