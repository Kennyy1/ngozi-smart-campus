from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.models.examination import Examination
from app.schemas.examination import DeliveryMode, ExaminationCreate, ExaminationRead, ExaminationStatus, ExaminationType, ExaminationUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.examination_service import *


router = APIRouter(prefix="/examinations", tags=["Examinations"])
ExaminationAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


@router.post("", response_model=ExaminationRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: ExaminationCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationAdministrator) -> Examination:
    try: return create_examination(session, institution_id=authenticated.institution.id, examination_data=request)
    except Exception as error: raise _map_error(error) from error


@router.get("", response_model=list[ExaminationRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationAdministrator, course_offering_id: UUID | None = None, lecturer_assignment_id: UUID | None = None, examination_type: ExaminationType | None = None, exam_date: date | None = None, delivery_mode: DeliveryMode | None = None, status: ExaminationStatus | None = None) -> list[Examination]:
    return list_examinations(session, institution_id=authenticated.institution.id, course_offering_id=course_offering_id, lecturer_assignment_id=lecturer_assignment_id, examination_type=examination_type, exam_date=exam_date, delivery_mode=delivery_mode, status=status)


@router.get("/{examination_id}", response_model=ExaminationRead)
def get_endpoint(examination_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationAdministrator) -> Examination:
    try: return get_examination(session, examination_id=examination_id, institution_id=authenticated.institution.id)
    except Exception as error: raise _map_error(error) from error


@router.patch("/{examination_id}", response_model=ExaminationRead)
def update_endpoint(examination_id: UUID, request: ExaminationUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationAdministrator) -> Examination:
    try: return update_examination(session, examination_id=examination_id, institution_id=authenticated.institution.id, examination_data=request)
    except Exception as error: raise _map_error(error) from error


@router.delete("/{examination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(examination_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ExaminationAdministrator) -> Response:
    try: delete_examination(session, examination_id=examination_id, institution_id=authenticated.institution.id)
    except Exception as error: raise _map_error(error) from error
    return Response(status_code=204)


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, ExaminationNotFoundError): return HTTPException(404, "Examination not found")
    if isinstance(error, ExaminationCourseOfferingNotFoundError): return HTTPException(404, "Course Offering not found")
    if isinstance(error, ExaminationLecturerAssignmentNotFoundError): return HTTPException(404, "Lecturer Assignment not found")
    if isinstance(error, (ExaminationCourseOfferingUnavailableError, ExaminationLecturerAssignmentUnavailableError, ExaminationLecturerUnavailableError)): return HTTPException(409, "Course Offering, Lecturer Assignment, or Lecturer is inactive")
    if isinstance(error, ExaminationHierarchyMismatchError): return HTTPException(409, "Lecturer Assignment does not belong to Course Offering")
    if isinstance(error, ExaminationDateRangeError): return HTTPException(422, "Examination date falls outside the Offering period")
    if isinstance(error, ExaminationTimeRangeError): return HTTPException(422, "start_time must be earlier than end_time")
    if isinstance(error, ExaminationVenueRequiredError): return HTTPException(422, "Venue is required for physical and hybrid examinations")
    if isinstance(error, DuplicateExaminationError): return HTTPException(409, "Examination title already exists for Course Offering")
    if isinstance(error, ExaminationWeightConflictError): return HTTPException(409, "Active examination weight total cannot exceed 100")
    if isinstance(error, ExaminationConflictError): return HTTPException(409, "Examination conflict")
    raise error
