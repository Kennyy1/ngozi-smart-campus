from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.guardian import *
from app.services.authentication import AuthenticatedUserContext
from app.services.guardian_service import *

router=APIRouter(prefix="/guardians",tags=["Guardians"])
relationships_router=APIRouter(prefix="/guardian-student-relationships",tags=["Guardian Student Relationships"])
Admin=Annotated[AuthenticatedUserContext,Depends(require_roles("administrator","system_super_admin"))]

def _raise(error: Exception):
    if isinstance(error,(GuardianNotFoundError,GuardianRelationshipNotFoundError,GuardianReferenceNotFoundError)): raise HTTPException(404,"Guardian resource not found") from error
    raise HTTPException(409,"Guardian resource conflicts with an existing record or lifecycle state") from error

@router.post("",response_model=GuardianRead,status_code=201)
def create_endpoint(data:GuardianCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:return create_guardian(session,institution_id=auth.institution.id,data=data)
    except GuardianConflictError as e:_raise(e)
@router.get("",response_model=list[GuardianRead])
def list_endpoint(session:Annotated[Session,Depends(get_db_session)],auth:Admin):return list_guardians(session,institution_id=auth.institution.id)
@router.get("/{guardian_id}",response_model=GuardianRead)
def get_endpoint(guardian_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:return get_guardian(session,institution_id=auth.institution.id,guardian_id=guardian_id)
    except GuardianNotFoundError as e:_raise(e)
@router.patch("/{guardian_id}",response_model=GuardianRead)
def update_endpoint(guardian_id:UUID,data:GuardianUpdate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:return update_guardian(session,institution_id=auth.institution.id,guardian_id=guardian_id,data=data)
    except (GuardianNotFoundError,GuardianConflictError) as e:_raise(e)
@router.delete("/{guardian_id}",status_code=204)
def delete_endpoint(guardian_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:delete_guardian(session,institution_id=auth.institution.id,guardian_id=guardian_id)
    except GuardianNotFoundError as e:_raise(e)
    return Response(status_code=204)

@relationships_router.post("",response_model=GuardianStudentRead,status_code=201)
def create_rel(data:GuardianStudentCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:return create_relationship(session,institution_id=auth.institution.id,data=data)
    except (GuardianReferenceNotFoundError,GuardianRelationshipConflictError) as e:_raise(e)
@relationships_router.get("",response_model=list[GuardianStudentRead])
def list_rel(session:Annotated[Session,Depends(get_db_session)],auth:Admin,guardian_id:UUID|None=None,student_id:UUID|None=None):return list_relationships(session,institution_id=auth.institution.id,guardian_id=guardian_id,student_id=student_id)
@relationships_router.get("/{relationship_id}",response_model=GuardianStudentRead)
def get_rel(relationship_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:return GuardianStudentRead.model_validate(get_relationship_model(session,institution_id=auth.institution.id,relationship_id=relationship_id),from_attributes=True)
    except GuardianRelationshipNotFoundError as e:_raise(e)
@relationships_router.patch("/{relationship_id}",response_model=GuardianStudentRead)
def update_rel(relationship_id:UUID,data:GuardianStudentUpdate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:return update_relationship(session,institution_id=auth.institution.id,relationship_id=relationship_id,data=data)
    except GuardianRelationshipNotFoundError as e:_raise(e)
def _transition(relationship_id,session,auth,target):
    try:return transition_relationship(session,institution_id=auth.institution.id,relationship_id=relationship_id,target=target)
    except (GuardianRelationshipNotFoundError,GuardianRelationshipConflictError) as e:_raise(e)
@relationships_router.post("/{relationship_id}/verify",response_model=GuardianStudentRead)
def verify_rel(relationship_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return _transition(relationship_id,session,auth,RelationshipStatus.VERIFIED)
@relationships_router.post("/{relationship_id}/suspend",response_model=GuardianStudentRead)
def suspend_rel(relationship_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return _transition(relationship_id,session,auth,RelationshipStatus.SUSPENDED)
@relationships_router.post("/{relationship_id}/revoke",response_model=GuardianStudentRead)
def revoke_rel(relationship_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return _transition(relationship_id,session,auth,RelationshipStatus.REVOKED)
