from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.assessment_score import (
    AssessmentScoreBulkCreate,
    AssessmentScoreBulkResult,
    AssessmentScoreCreate,
    AssessmentScoreRead,
    AssessmentScoreStatus,
    AssessmentScoreUpdate,
)
from app.services.assessment_score_service import (
    AssessmentComponentUnavailableForGradingError,
    AssessmentGraderUnauthorizedError,
    AssessmentScoreNotFoundError,
    AssessmentScoreOfferingMismatchError,
    DuplicateAssessmentScoreError,
    InvalidAssessmentScoreError,
    ScoreAssessmentComponentNotFoundError,
    ScoreCourseRegistrationNotFoundError,
    ScoreCourseRegistrationUnavailableError,
    create_assessment_score,
    create_assessment_scores_bulk,
    delete_assessment_score,
    get_assessment_score,
    list_assessment_scores,
    update_assessment_score,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(prefix="/assessment-scores", tags=["Assessment Scores"])
AssessmentScoreAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]

ASSESSMENT_SCORE_ERRORS = (
    AssessmentComponentUnavailableForGradingError,
    AssessmentGraderUnauthorizedError,
    AssessmentScoreNotFoundError,
    AssessmentScoreOfferingMismatchError,
    DuplicateAssessmentScoreError,
    InvalidAssessmentScoreError,
    ScoreAssessmentComponentNotFoundError,
    ScoreCourseRegistrationNotFoundError,
    ScoreCourseRegistrationUnavailableError,
)


@router.post("", response_model=AssessmentScoreRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(
    request: AssessmentScoreCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AssessmentScoreAdministrator,
) -> AssessmentScoreRead:
    try:
        return create_assessment_score(
            session,
            institution_id=authenticated.institution.id,
            graded_by_user_id=authenticated.user.id,
            assessment_score_data=request,
        )
    except ASSESSMENT_SCORE_ERRORS as error:
        raise _map_error(error) from error


@router.post("/bulk", response_model=AssessmentScoreBulkResult, status_code=status.HTTP_201_CREATED)
def create_bulk_endpoint(
    request: AssessmentScoreBulkCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AssessmentScoreAdministrator,
) -> AssessmentScoreBulkResult:
    try:
        scores = create_assessment_scores_bulk(
            session,
            institution_id=authenticated.institution.id,
            graded_by_user_id=authenticated.user.id,
            assessment_score_data=request,
        )
        return AssessmentScoreBulkResult(scores=scores)
    except ASSESSMENT_SCORE_ERRORS as error:
        raise _map_error(error) from error


@router.get("", response_model=list[AssessmentScoreRead])
def list_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AssessmentScoreAdministrator,
    assessment_component_id: UUID | None = None,
    course_registration_id: UUID | None = None,
    graded_by_user_id: UUID | None = None,
    status: AssessmentScoreStatus | None = None,
) -> list[AssessmentScoreRead]:
    return list_assessment_scores(
        session,
        institution_id=authenticated.institution.id,
        assessment_component_id=assessment_component_id,
        course_registration_id=course_registration_id,
        graded_by_user_id=graded_by_user_id,
        status=status,
    )


@router.get("/{assessment_score_id}", response_model=AssessmentScoreRead)
def get_endpoint(
    assessment_score_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AssessmentScoreAdministrator,
) -> AssessmentScoreRead:
    try:
        return get_assessment_score(session, assessment_score_id=assessment_score_id, institution_id=authenticated.institution.id)
    except ASSESSMENT_SCORE_ERRORS as error:
        raise _map_error(error) from error


@router.patch("/{assessment_score_id}", response_model=AssessmentScoreRead)
def update_endpoint(
    assessment_score_id: UUID,
    request: AssessmentScoreUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AssessmentScoreAdministrator,
) -> AssessmentScoreRead:
    try:
        return update_assessment_score(
            session,
            assessment_score_id=assessment_score_id,
            institution_id=authenticated.institution.id,
            assessment_score_data=request,
        )
    except ASSESSMENT_SCORE_ERRORS as error:
        raise _map_error(error) from error


@router.delete("/{assessment_score_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(
    assessment_score_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AssessmentScoreAdministrator,
) -> Response:
    try:
        delete_assessment_score(session, assessment_score_id=assessment_score_id, institution_id=authenticated.institution.id)
    except ASSESSMENT_SCORE_ERRORS as error:
        raise _map_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, ScoreAssessmentComponentNotFoundError):
        return HTTPException(404, "Assessment Component not found")
    if isinstance(error, ScoreCourseRegistrationNotFoundError):
        return HTTPException(404, "Course Registration not found")
    if isinstance(error, AssessmentScoreNotFoundError):
        return HTTPException(404, "Assessment Score not found")
    if isinstance(error, DuplicateAssessmentScoreError):
        return HTTPException(409, "Assessment Score already exists")
    if isinstance(error, AssessmentScoreOfferingMismatchError):
        return HTTPException(409, "Registration and Assessment Component Course Offerings do not match")
    if isinstance(error, ScoreCourseRegistrationUnavailableError):
        return HTTPException(409, "Course Registration is unavailable for assessment scoring")
    if isinstance(error, AssessmentComponentUnavailableForGradingError):
        return HTTPException(409, "Assessment Component is unavailable for grading")
    if isinstance(error, AssessmentGraderUnauthorizedError):
        return HTTPException(403, "Grader is not authorized")
    return HTTPException(422, "Invalid Assessment Score")
