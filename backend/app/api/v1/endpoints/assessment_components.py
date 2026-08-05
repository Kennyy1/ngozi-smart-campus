from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.models.assessment_component import AssessmentComponent
from app.schemas.assessment_component import AssessmentComponentCreate, AssessmentComponentRead, AssessmentComponentStatus, AssessmentComponentUpdate, AssessmentType
from app.services.assessment_component_service import (
    AssessmentComponentConflictError,
    AssessmentComponentNotFoundError,
    AssessmentCourseOfferingNotFoundError,
    AssessmentCourseOfferingUnavailableError,
    AssessmentDateRangeError,
    AssessmentHierarchyMismatchError,
    AssessmentLecturerAssignmentNotFoundError,
    AssessmentLecturerAssignmentUnavailableError,
    AssessmentLecturerUnavailableError,
    AssessmentWeightConflictError,
    DuplicateAssessmentComponentError,
    create_assessment_component,
    delete_assessment_component,
    get_assessment_component,
    list_assessment_components,
    update_assessment_component,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(prefix="/assessment-components", tags=["Assessment Components"])
AssessmentAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


@router.post("", response_model=AssessmentComponentRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: AssessmentComponentCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: AssessmentAdministrator) -> AssessmentComponent:
    try:
        return create_assessment_component(session, institution_id=authenticated.institution.id, assessment_component_data=request)
    except Exception as error:
        raise _map_error(error) from error


@router.get("", response_model=list[AssessmentComponentRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: AssessmentAdministrator, course_offering_id: UUID | None = None, lecturer_assignment_id: UUID | None = None, assessment_type: AssessmentType | None = None, status: AssessmentComponentStatus | None = None, scheduled_date: date | None = None) -> list[AssessmentComponent]:
    return list_assessment_components(session, institution_id=authenticated.institution.id, course_offering_id=course_offering_id, lecturer_assignment_id=lecturer_assignment_id, assessment_type=assessment_type, status=status, scheduled_date=scheduled_date)


@router.get("/{assessment_component_id}", response_model=AssessmentComponentRead)
def get_endpoint(assessment_component_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AssessmentAdministrator) -> AssessmentComponent:
    try:
        return get_assessment_component(session, assessment_component_id=assessment_component_id, institution_id=authenticated.institution.id)
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/{assessment_component_id}", response_model=AssessmentComponentRead)
def update_endpoint(assessment_component_id: UUID, request: AssessmentComponentUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: AssessmentAdministrator) -> AssessmentComponent:
    try:
        return update_assessment_component(session, assessment_component_id=assessment_component_id, institution_id=authenticated.institution.id, assessment_component_data=request)
    except Exception as error:
        raise _map_error(error) from error


@router.delete("/{assessment_component_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(assessment_component_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AssessmentAdministrator) -> Response:
    try:
        delete_assessment_component(session, assessment_component_id=assessment_component_id, institution_id=authenticated.institution.id)
    except Exception as error:
        raise _map_error(error) from error
    return Response(status_code=204)


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, AssessmentComponentNotFoundError):
        return HTTPException(status_code=404, detail="Assessment Component not found")
    if isinstance(error, AssessmentCourseOfferingNotFoundError):
        return HTTPException(status_code=404, detail="Course Offering not found")
    if isinstance(error, AssessmentLecturerAssignmentNotFoundError):
        return HTTPException(status_code=404, detail="Lecturer Assignment not found")
    if isinstance(error, (AssessmentCourseOfferingUnavailableError, AssessmentLecturerAssignmentUnavailableError, AssessmentLecturerUnavailableError)):
        return HTTPException(status_code=409, detail="Course Offering, Lecturer Assignment, or Lecturer is inactive")
    if isinstance(error, AssessmentHierarchyMismatchError):
        return HTTPException(status_code=409, detail="Lecturer Assignment does not belong to Course Offering")
    if isinstance(error, AssessmentDateRangeError):
        return HTTPException(status_code=422, detail="Assessment dates fall outside the Offering period")
    if isinstance(error, DuplicateAssessmentComponentError):
        return HTTPException(status_code=409, detail="Assessment Component title already exists for Course Offering")
    if isinstance(error, AssessmentWeightConflictError):
        return HTTPException(status_code=409, detail="Active assessment weight total cannot exceed 100")
    if isinstance(error, AssessmentComponentConflictError):
        return HTTPException(status_code=409, detail="Assessment Component conflict")
    raise error
