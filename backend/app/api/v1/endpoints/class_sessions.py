from datetime import date
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session, require_roles
from app.models.class_session import ClassSession
from app.schemas.class_session import ClassSessionCreate, ClassSessionRead, ClassSessionStatus, ClassSessionUpdate, DeliveryMode, SessionType
from app.services.authentication import AuthenticatedUserContext
from app.services.class_session_service import *

router = APIRouter(prefix="/class-sessions", tags=["Class Sessions"])
Administrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]

def _map(error: Exception) -> HTTPException:
    if isinstance(error, (ClassSessionNotFoundError, ClassSessionOfferingNotFoundError, ClassSessionAssignmentNotFoundError)): return HTTPException(404, "Class Session parent not found")
    if isinstance(error, (DuplicateClassSessionError, OverlappingClassSessionError, ClassSessionConflictError, ClassSessionHierarchyError, ClassSessionParentUnavailableError)): return HTTPException(409, "Class Session conflict")
    return HTTPException(422, "Invalid Class Session")

@router.post("", response_model=ClassSessionRead, status_code=201)
def create_endpoint(request: ClassSessionCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: Administrator) -> ClassSession:
    try: return create_class_session(session, institution_id=authenticated.institution.id, class_session_data=request)
    except (ClassSessionOfferingNotFoundError, ClassSessionAssignmentNotFoundError, ClassSessionHierarchyError, ClassSessionParentUnavailableError, InvalidClassSessionError, DuplicateClassSessionError, OverlappingClassSessionError, ClassSessionConflictError) as error: raise _map(error) from error

@router.get("", response_model=list[ClassSessionRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: Administrator, course_offering_id: UUID | None = None, lecturer_assignment_id: UUID | None = None, session_date: date | None = None, session_type: SessionType | None = None, delivery_mode: DeliveryMode | None = None, status: ClassSessionStatus | None = None) -> list[ClassSession]:
    return list_class_sessions(session, institution_id=authenticated.institution.id, course_offering_id=course_offering_id, lecturer_assignment_id=lecturer_assignment_id, session_date=session_date, session_type=session_type, delivery_mode=delivery_mode, status=status)

@router.get("/{class_session_id}", response_model=ClassSessionRead)
def get_endpoint(class_session_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: Administrator) -> ClassSession:
    try: return get_class_session(session, class_session_id=class_session_id, institution_id=authenticated.institution.id)
    except ClassSessionNotFoundError as error: raise _map(error) from error

@router.patch("/{class_session_id}", response_model=ClassSessionRead)
def update_endpoint(class_session_id: UUID, request: ClassSessionUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: Administrator) -> ClassSession:
    try: return update_class_session(session, class_session_id=class_session_id, institution_id=authenticated.institution.id, class_session_data=request)
    except (ClassSessionNotFoundError, ClassSessionOfferingNotFoundError, ClassSessionAssignmentNotFoundError, ClassSessionHierarchyError, ClassSessionParentUnavailableError, InvalidClassSessionError, DuplicateClassSessionError, OverlappingClassSessionError, ClassSessionConflictError) as error: raise _map(error) from error

@router.delete("/{class_session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(class_session_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: Administrator) -> Response:
    try: delete_class_session(session, class_session_id=class_session_id, institution_id=authenticated.institution.id)
    except ClassSessionNotFoundError as error: raise _map(error) from error
    return Response(status_code=204)
