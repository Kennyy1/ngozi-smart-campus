from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.result_computation import ComputedCourseResult, CourseOfferingComputedResults
from app.services.authentication import AuthenticatedUserContext
from app.services.result_computation_service import (
    ResultCourseOfferingNotFoundError,
    ResultCourseRegistrationNotFoundError,
    ResultCourseRegistrationUnavailableError,
    compute_course_offering_results,
    compute_course_registration_result,
)


router = APIRouter(tags=["Result Computation"])
ResultComputationAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, ResultCourseRegistrationNotFoundError):
        return HTTPException(404, "Course Registration not found")
    if isinstance(error, ResultCourseRegistrationUnavailableError):
        return HTTPException(409, "Course Registration is unavailable for result computation")
    return HTTPException(404, "Course Offering not found")


@router.get(
    "/course-registrations/{course_registration_id}/computed-result",
    response_model=ComputedCourseResult,
)
def registration_result_endpoint(
    course_registration_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ResultComputationAdministrator,
) -> ComputedCourseResult:
    try:
        return compute_course_registration_result(session, institution_id=authenticated.institution.id, course_registration_id=course_registration_id)
    except (ResultCourseRegistrationNotFoundError, ResultCourseRegistrationUnavailableError, ResultCourseOfferingNotFoundError) as error:
        raise _map_error(error) from error


@router.get(
    "/course-offerings/{course_offering_id}/computed-results",
    response_model=CourseOfferingComputedResults,
)
def offering_results_endpoint(
    course_offering_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: ResultComputationAdministrator,
) -> CourseOfferingComputedResults:
    try:
        return compute_course_offering_results(session, institution_id=authenticated.institution.id, course_offering_id=course_offering_id)
    except ResultCourseOfferingNotFoundError as error:
        raise _map_error(error) from error
