from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.graduation_eligibility import GraduationEligibilityEvaluation
from app.services.academic_performance_service import InvalidCourseCreditUnitsError
from app.services.academic_progression_service import (
    AcademicProgressionProgrammeNotFoundError, AcademicProgressionStudentNotFoundError,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.graduation_eligibility_service import (
    GraduationEligibilityProgrammeNotFoundError, GraduationEligibilityStudentNotFoundError,
    evaluate_student_graduation_eligibility,
)


router = APIRouter(prefix="/students", tags=["Graduation Eligibility"])
GraduationEligibilityAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, (GraduationEligibilityStudentNotFoundError, AcademicProgressionStudentNotFoundError)):
        return HTTPException(404, "Student not found")
    if isinstance(error, (GraduationEligibilityProgrammeNotFoundError, AcademicProgressionProgrammeNotFoundError)):
        return HTTPException(409, "Student Programme is not configured")
    return HTTPException(409, "Course has invalid credit units")


@router.get("/{student_id}/graduation-eligibility", response_model=GraduationEligibilityEvaluation)
def graduation_eligibility_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationEligibilityAdministrator) -> GraduationEligibilityEvaluation:
    try:
        return evaluate_student_graduation_eligibility(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (
        GraduationEligibilityStudentNotFoundError, GraduationEligibilityProgrammeNotFoundError,
        AcademicProgressionStudentNotFoundError, AcademicProgressionProgrammeNotFoundError,
        InvalidCourseCreditUnitsError,
    ) as error:
        raise _map_error(error) from error
