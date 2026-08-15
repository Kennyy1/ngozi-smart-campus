from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.clearance import (
    GraduationClearanceEvaluation, StudentClearanceActionRequest, StudentClearanceCreate,
    StudentClearanceRead, StudentClearanceStatus, StudentClearanceSummary, StudentClearanceUpdate,
)
from app.services.academic_performance_service import AcademicPerformanceStudentNotFoundError, InvalidCourseCreditUnitsError
from app.services.academic_progression_service import AcademicProgressionProgrammeNotFoundError, AcademicProgressionStudentNotFoundError
from app.services.authentication import AuthenticatedUserContext
from app.services.clearance_service import (
    ClearanceRequirementNotFoundError, DuplicateStudentClearanceError,
    InvalidStudentClearanceTransitionError, StudentClearanceNotFoundError,
    StudentClearanceStudentNotFoundError, clear_student_clearance,
    compute_student_clearance_summary, create_student_clearance,
    evaluate_graduation_clearance, get_student_clearance, list_student_clearances,
    reject_student_clearance, reset_student_clearance, update_student_clearance,
    waive_student_clearance,
)
from app.services.graduation_eligibility_service import GraduationEligibilityProgrammeNotFoundError, GraduationEligibilityStudentNotFoundError


router = APIRouter(prefix="/student-clearances", tags=["Clearance Management"])
student_router = APIRouter(prefix="/students", tags=["Clearance Management"])
ClearanceAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


def _not_found(error: Exception) -> HTTPException:
    if isinstance(error, ClearanceRequirementNotFoundError):
        return HTTPException(404, "Clearance Requirement not found")
    if isinstance(error, StudentClearanceNotFoundError):
        return HTTPException(404, "Student Clearance not found")
    return HTTPException(404, "Student not found")


@router.post("", response_model=StudentClearanceRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: StudentClearanceCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return create_student_clearance(session, institution_id=authenticated.institution.id, clearance_data=request)
    except (ClearanceRequirementNotFoundError, StudentClearanceStudentNotFoundError) as error:
        raise _not_found(error) from error
    except DuplicateStudentClearanceError as error:
        raise HTTPException(409, "An active Student Clearance already exists for this Requirement") from error


@router.get("", response_model=list[StudentClearanceRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator, student_id: UUID | None = None, clearance_requirement_id: UUID | None = None, status: StudentClearanceStatus | None = None, reviewed_by_user_id: UUID | None = None) -> object:
    return list_student_clearances(session, institution_id=authenticated.institution.id, student_id=student_id, clearance_requirement_id=clearance_requirement_id, status=status, reviewed_by_user_id=reviewed_by_user_id)


@router.get("/{student_clearance_id}", response_model=StudentClearanceRead)
def get_endpoint(student_clearance_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return get_student_clearance(session, institution_id=authenticated.institution.id, student_clearance_id=student_clearance_id)
    except StudentClearanceNotFoundError as error:
        raise _not_found(error) from error


@router.patch("/{student_clearance_id}", response_model=StudentClearanceRead)
def update_endpoint(student_clearance_id: UUID, request: StudentClearanceUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return update_student_clearance(session, institution_id=authenticated.institution.id, student_clearance_id=student_clearance_id, clearance_data=request)
    except StudentClearanceNotFoundError as error:
        raise _not_found(error) from error


def _transition_error(error: Exception) -> HTTPException:
    if isinstance(error, StudentClearanceNotFoundError):
        return _not_found(error)
    return HTTPException(409, "Invalid Student Clearance lifecycle transition")


@router.post("/{student_clearance_id}/clear", response_model=StudentClearanceRead)
def clear_endpoint(student_clearance_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return clear_student_clearance(session, institution_id=authenticated.institution.id, student_clearance_id=student_clearance_id, user_id=authenticated.user.id)
    except (StudentClearanceNotFoundError, InvalidStudentClearanceTransitionError) as error:
        raise _transition_error(error) from error


@router.post("/{student_clearance_id}/reject", response_model=StudentClearanceRead)
def reject_endpoint(student_clearance_id: UUID, request: StudentClearanceActionRequest, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return reject_student_clearance(session, institution_id=authenticated.institution.id, student_clearance_id=student_clearance_id, user_id=authenticated.user.id, request=request)
    except (StudentClearanceNotFoundError, InvalidStudentClearanceTransitionError) as error:
        raise _transition_error(error) from error


@router.post("/{student_clearance_id}/waive", response_model=StudentClearanceRead)
def waive_endpoint(student_clearance_id: UUID, request: StudentClearanceActionRequest, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return waive_student_clearance(session, institution_id=authenticated.institution.id, student_clearance_id=student_clearance_id, user_id=authenticated.user.id, request=request)
    except (StudentClearanceNotFoundError, InvalidStudentClearanceTransitionError) as error:
        raise _transition_error(error) from error


@router.post("/{student_clearance_id}/reset", response_model=StudentClearanceRead)
def reset_endpoint(student_clearance_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return reset_student_clearance(session, institution_id=authenticated.institution.id, student_clearance_id=student_clearance_id)
    except (StudentClearanceNotFoundError, InvalidStudentClearanceTransitionError) as error:
        raise _transition_error(error) from error


@student_router.get("/{student_id}/clearance-summary", response_model=StudentClearanceSummary)
def summary_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return compute_student_clearance_summary(session, institution_id=authenticated.institution.id, student_id=student_id)
    except StudentClearanceStudentNotFoundError as error:
        raise _not_found(error) from error


@student_router.get("/{student_id}/graduation-clearance", response_model=GraduationClearanceEvaluation)
def graduation_clearance_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return evaluate_graduation_clearance(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (StudentClearanceStudentNotFoundError, GraduationEligibilityStudentNotFoundError, AcademicProgressionStudentNotFoundError, AcademicPerformanceStudentNotFoundError) as error:
        raise _not_found(error) from error
    except (GraduationEligibilityProgrammeNotFoundError, AcademicProgressionProgrammeNotFoundError) as error:
        raise HTTPException(409, "Student Programme is not configured") from error
    except InvalidCourseCreditUnitsError as error:
        raise HTTPException(409, "Course has invalid credit units") from error
