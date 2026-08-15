from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.clearance import ClearanceRequirementCreate, ClearanceRequirementRead, ClearanceRequirementStatus, ClearanceRequirementUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services.clearance_service import (
    ClearanceRequirementNotFoundError, DuplicateClearanceRequirementCodeError,
    create_clearance_requirement, delete_clearance_requirement, get_clearance_requirement,
    list_clearance_requirements, update_clearance_requirement,
)


router = APIRouter(prefix="/clearance-requirements", tags=["Clearance Management"])
ClearanceAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


@router.post("", response_model=ClearanceRequirementRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: ClearanceRequirementCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return create_clearance_requirement(session, institution_id=authenticated.institution.id, requirement_data=request)
    except DuplicateClearanceRequirementCodeError as error:
        raise HTTPException(409, "Clearance Requirement code already exists in this Institution") from error


@router.get("", response_model=list[ClearanceRequirementRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator, status: ClearanceRequirementStatus | None = None, is_mandatory: bool | None = None, code: str | None = None) -> object:
    return list_clearance_requirements(session, institution_id=authenticated.institution.id, status=status, is_mandatory=is_mandatory, code=code)


@router.get("/{requirement_id}", response_model=ClearanceRequirementRead)
def get_endpoint(requirement_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return get_clearance_requirement(session, institution_id=authenticated.institution.id, requirement_id=requirement_id)
    except ClearanceRequirementNotFoundError as error:
        raise HTTPException(404, "Clearance Requirement not found") from error


@router.patch("/{requirement_id}", response_model=ClearanceRequirementRead)
def update_endpoint(requirement_id: UUID, request: ClearanceRequirementUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> object:
    try:
        return update_clearance_requirement(session, institution_id=authenticated.institution.id, requirement_id=requirement_id, requirement_data=request)
    except ClearanceRequirementNotFoundError as error:
        raise HTTPException(404, "Clearance Requirement not found") from error
    except DuplicateClearanceRequirementCodeError as error:
        raise HTTPException(409, "Clearance Requirement code already exists in this Institution") from error


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(requirement_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: ClearanceAdministrator) -> Response:
    try:
        delete_clearance_requirement(session, institution_id=authenticated.institution.id, requirement_id=requirement_id)
    except ClearanceRequirementNotFoundError as error:
        raise HTTPException(404, "Clearance Requirement not found") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
