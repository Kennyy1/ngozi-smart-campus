from typing import Annotated, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.result import ResultCreate, ResultRead, ResultRejectRequest, ResultStatus, ResultUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services import result_service as service


router = APIRouter(prefix="/results", tags=["Results"])
ResultAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, (service.ResultNotFoundError, service.ResultCourseRegistrationNotFoundError)):
        return HTTPException(404, "Result or Course Registration not found")
    if isinstance(error, service.DuplicateResultError): return HTTPException(409, "An active Result already exists for this Course Registration")
    if isinstance(error, service.IncompleteResultComputationError): return HTTPException(409, "Course result computation is incomplete")
    if isinstance(error, service.ResultCourseRegistrationUnavailableError): return HTTPException(409, "Course Registration is unavailable for result management")
    if isinstance(error, service.ResultImmutableError): return HTTPException(409, "Result is immutable in its current status")
    return HTTPException(409, "Invalid Result workflow transition")


ERRORS = (service.ResultNotFoundError, service.ResultCourseRegistrationNotFoundError, service.ResultCourseRegistrationUnavailableError, service.DuplicateResultError, service.IncompleteResultComputationError, service.InvalidResultTransitionError, service.ResultImmutableError)


@router.post("", response_model=ResultRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: ResultCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead:
    try: return service.create_result(session, institution_id=authenticated.institution.id, computed_by_user_id=authenticated.user.id, result_data=request)
    except ERRORS as error: raise _map_error(error) from error


@router.get("", response_model=list[ResultRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator, course_registration_id: UUID | None = None, course_offering_id: UUID | None = None, student_id: UUID | None = None, status: ResultStatus | None = None, passed: bool | None = None, grade_letter: str | None = None) -> list[ResultRead]:
    return service.list_results(session, institution_id=authenticated.institution.id, course_registration_id=course_registration_id, course_offering_id=course_offering_id, student_id=student_id, status=status, passed=passed, grade_letter=grade_letter)


def _action(operation: Callable[..., object], session: Session, authenticated: AuthenticatedUserContext, result_id: UUID, **kwargs: object) -> object:
    try: return operation(session, institution_id=authenticated.institution.id, result_id=result_id, user_id=authenticated.user.id, **kwargs)
    except ERRORS as error: raise _map_error(error) from error


@router.post("/{result_id}/refresh", response_model=ResultRead)
def refresh_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead:
    try: return service.refresh_result(session, institution_id=authenticated.institution.id, result_id=result_id, computed_by_user_id=authenticated.user.id)
    except ERRORS as error: raise _map_error(error) from error


@router.post("/{result_id}/submit", response_model=ResultRead)
def submit_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead: return _action(service.submit_result, session, authenticated, result_id)  # type: ignore[return-value]


@router.post("/{result_id}/approve", response_model=ResultRead)
def approve_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead: return _action(service.approve_result, session, authenticated, result_id)  # type: ignore[return-value]


@router.post("/{result_id}/reject", response_model=ResultRead)
def reject_endpoint(result_id: UUID, request: ResultRejectRequest, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead: return _action(service.reject_result, session, authenticated, result_id, request=request)  # type: ignore[return-value]


@router.post("/{result_id}/return-to-draft", response_model=ResultRead)
def return_to_draft_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead: return _action(service.return_result_to_draft, session, authenticated, result_id)  # type: ignore[return-value]


@router.post("/{result_id}/publish", response_model=ResultRead)
def publish_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead: return _action(service.publish_result, session, authenticated, result_id)  # type: ignore[return-value]


@router.post("/{result_id}/withhold", response_model=ResultRead)
def withhold_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead: return _action(service.withhold_result, session, authenticated, result_id)  # type: ignore[return-value]


@router.get("/{result_id}", response_model=ResultRead)
def get_endpoint(result_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead:
    try: return service.get_result(session, institution_id=authenticated.institution.id, result_id=result_id)
    except ERRORS as error: raise _map_error(error) from error


@router.patch("/{result_id}", response_model=ResultRead)
def update_endpoint(result_id: UUID, request: ResultUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: ResultAdministrator) -> ResultRead:
    try: return service.update_result(session, institution_id=authenticated.institution.id, result_id=result_id, result_data=request)
    except ERRORS as error: raise _map_error(error) from error
