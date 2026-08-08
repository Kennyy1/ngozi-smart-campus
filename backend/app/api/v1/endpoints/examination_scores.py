from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.examination_score import ExaminationScoreBulkCreate, ExaminationScoreBulkResult, ExaminationScoreCreate, ExaminationScoreRead, ExaminationScoreStatus, ExaminationScoreUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.examination_score_service import (
    DuplicateExaminationScoreError, ExaminationGraderUnauthorizedError, ExaminationScoreCourseRegistrationNotFoundError,
    ExaminationScoreCourseRegistrationUnavailableError, ExaminationScoreNotFoundError, ExaminationScoreOfferingMismatchError,
    ExaminationUnavailableForGradingError, InvalidExaminationScoreError, ScoreExaminationNotFoundError,
    create_examination_score, create_examination_scores_bulk, delete_examination_score, get_examination_score,
    list_examination_scores, update_examination_score,
)


router = APIRouter(prefix="/examination-scores", tags=["Examination Scores"])
ExaminationScoreAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]
EXAMINATION_SCORE_ERRORS = (DuplicateExaminationScoreError, ExaminationGraderUnauthorizedError, ExaminationScoreCourseRegistrationNotFoundError, ExaminationScoreCourseRegistrationUnavailableError, ExaminationScoreNotFoundError, ExaminationScoreOfferingMismatchError, ExaminationUnavailableForGradingError, InvalidExaminationScoreError, ScoreExaminationNotFoundError)


@router.post("", response_model=ExaminationScoreRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: ExaminationScoreCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationScoreAdministrator) -> ExaminationScoreRead:
    try: return create_examination_score(session, institution_id=authenticated.institution.id, graded_by_user_id=authenticated.user.id, examination_score_data=request)
    except EXAMINATION_SCORE_ERRORS as error: raise _map_error(error) from error


@router.post("/bulk", response_model=ExaminationScoreBulkResult, status_code=status.HTTP_201_CREATED)
def create_bulk_endpoint(request: ExaminationScoreBulkCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationScoreAdministrator) -> ExaminationScoreBulkResult:
    try:
        scores = create_examination_scores_bulk(session, institution_id=authenticated.institution.id, graded_by_user_id=authenticated.user.id, examination_score_data=request)
        return ExaminationScoreBulkResult(scores=scores)
    except EXAMINATION_SCORE_ERRORS as error: raise _map_error(error) from error


@router.get("", response_model=list[ExaminationScoreRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationScoreAdministrator, examination_id: UUID | None = None, course_registration_id: UUID | None = None, graded_by_user_id: UUID | None = None, status: ExaminationScoreStatus | None = None) -> list[ExaminationScoreRead]:
    return list_examination_scores(session, institution_id=authenticated.institution.id, examination_id=examination_id, course_registration_id=course_registration_id, graded_by_user_id=graded_by_user_id, status=status)


@router.get("/{examination_score_id}", response_model=ExaminationScoreRead)
def get_endpoint(examination_score_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationScoreAdministrator) -> ExaminationScoreRead:
    try: return get_examination_score(session, examination_score_id=examination_score_id, institution_id=authenticated.institution.id)
    except EXAMINATION_SCORE_ERRORS as error: raise _map_error(error) from error


@router.patch("/{examination_score_id}", response_model=ExaminationScoreRead)
def update_endpoint(examination_score_id: UUID, request: ExaminationScoreUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationScoreAdministrator) -> ExaminationScoreRead:
    try: return update_examination_score(session, examination_score_id=examination_score_id, institution_id=authenticated.institution.id, examination_score_data=request)
    except EXAMINATION_SCORE_ERRORS as error: raise _map_error(error) from error


@router.delete("/{examination_score_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(examination_score_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationScoreAdministrator) -> Response:
    try: delete_examination_score(session, examination_score_id=examination_score_id, institution_id=authenticated.institution.id)
    except EXAMINATION_SCORE_ERRORS as error: raise _map_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, ScoreExaminationNotFoundError): return HTTPException(404, "Examination not found")
    if isinstance(error, ExaminationScoreCourseRegistrationNotFoundError): return HTTPException(404, "Course Registration not found")
    if isinstance(error, ExaminationScoreNotFoundError): return HTTPException(404, "Examination Score not found")
    if isinstance(error, DuplicateExaminationScoreError): return HTTPException(409, "Examination Score already exists")
    if isinstance(error, ExaminationScoreOfferingMismatchError): return HTTPException(409, "Registration and Examination Course Offerings do not match")
    if isinstance(error, ExaminationScoreCourseRegistrationUnavailableError): return HTTPException(409, "Course Registration is unavailable for examination scoring")
    if isinstance(error, ExaminationUnavailableForGradingError): return HTTPException(409, "Examination is unavailable for grading")
    if isinstance(error, ExaminationGraderUnauthorizedError): return HTTPException(403, "Grader is not authorized")
    return HTTPException(422, "Invalid Examination Score")
