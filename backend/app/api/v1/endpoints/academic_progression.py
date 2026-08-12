from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.academic_progression import (
    AcademicStandingSummary, ProgressionEvaluation, StudentAcademicProgressSummary,
)
from app.services.academic_performance_service import InvalidCourseCreditUnitsError
from app.services.academic_progression_service import (
    AcademicProgressionProgrammeNotFoundError, AcademicProgressionStudentNotFoundError,
    compute_student_academic_standing, evaluate_student_progression,
    get_student_academic_progress,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(prefix="/students", tags=["Academic Progression"])
AcademicProgressionAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, AcademicProgressionStudentNotFoundError):
        return HTTPException(404, "Student not found")
    if isinstance(error, AcademicProgressionProgrammeNotFoundError):
        return HTTPException(409, "Student Programme is not configured")
    return HTTPException(409, "Course has invalid credit units")


@router.get("/{student_id}/academic-standing", response_model=AcademicStandingSummary)
def academic_standing_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AcademicProgressionAdministrator) -> AcademicStandingSummary:
    try:
        return compute_student_academic_standing(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (AcademicProgressionStudentNotFoundError, AcademicProgressionProgrammeNotFoundError, InvalidCourseCreditUnitsError) as error:
        raise _map_error(error) from error


@router.get("/{student_id}/progression", response_model=ProgressionEvaluation)
def progression_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AcademicProgressionAdministrator) -> ProgressionEvaluation:
    try:
        return evaluate_student_progression(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (AcademicProgressionStudentNotFoundError, AcademicProgressionProgrammeNotFoundError, InvalidCourseCreditUnitsError) as error:
        raise _map_error(error) from error


@router.get("/{student_id}/academic-progress", response_model=StudentAcademicProgressSummary)
def academic_progress_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AcademicProgressionAdministrator) -> StudentAcademicProgressSummary:
    try:
        return get_student_academic_progress(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (AcademicProgressionStudentNotFoundError, AcademicProgressionProgrammeNotFoundError, InvalidCourseCreditUnitsError) as error:
        raise _map_error(error) from error
