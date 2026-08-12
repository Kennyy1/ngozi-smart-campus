from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.transcript import StudentTranscriptSummary
from app.services.academic_performance_service import InvalidCourseCreditUnitsError
from app.services.academic_progression_service import (
    AcademicProgressionProgrammeNotFoundError, AcademicProgressionStudentNotFoundError,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.transcript_service import (
    TranscriptProgrammeNotFoundError, TranscriptStudentNotFoundError,
    compute_student_transcript,
)


router = APIRouter(prefix="/students", tags=["Transcript Computation"])
TranscriptAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, (TranscriptStudentNotFoundError, AcademicProgressionStudentNotFoundError)):
        return HTTPException(404, "Student not found")
    if isinstance(error, (TranscriptProgrammeNotFoundError, AcademicProgressionProgrammeNotFoundError)):
        return HTTPException(409, "Student Programme is not configured")
    return HTTPException(409, "Course has invalid credit units")


@router.get("/{student_id}/transcript", response_model=StudentTranscriptSummary)
def transcript_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> StudentTranscriptSummary:
    try:
        return compute_student_transcript(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (
        TranscriptStudentNotFoundError, TranscriptProgrammeNotFoundError,
        AcademicProgressionStudentNotFoundError, AcademicProgressionProgrammeNotFoundError,
        InvalidCourseCreditUnitsError,
    ) as error:
        raise _map_error(error) from error
