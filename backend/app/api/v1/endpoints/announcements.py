from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user,get_db_session,require_roles
from app.schemas.communication import AnnouncementCreate,AnnouncementReadModel,AnnouncementUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services import communication_service as service

router=APIRouter(prefix="/announcements",tags=["Announcements"])
Admin=Annotated[AuthenticatedUserContext,Depends(require_roles("administrator","system_super_admin"))]
def guard(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except service.CommunicationNotFound as e:raise HTTPException(404,"Announcement not found") from e
    except service.CommunicationForbidden as e:raise HTTPException(403,str(e)) from e
    except service.CommunicationConflict as e:raise HTTPException(409,str(e)) from e
@router.post("",response_model=AnnouncementReadModel,status_code=201)
def create(data:AnnouncementCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return guard(service.create_announcement,session,institution_id=auth.institution.id,user_id=auth.user.id,data=data)
@router.get("",response_model=list[AnnouncementReadModel])
def listing(session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service.list_admin(session,auth.institution.id)
@router.get("/{announcement_id}",response_model=AnnouncementReadModel)
def detail(announcement_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return guard(service.get_admin,session,auth.institution.id,announcement_id)
@router.patch("/{announcement_id}",response_model=AnnouncementReadModel)
def update(announcement_id:UUID,data:AnnouncementUpdate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return guard(service.update_draft,session,institution_id=auth.institution.id,announcement_id=announcement_id,data=data)
@router.post("/{announcement_id}/publish",response_model=AnnouncementReadModel)
def publish(announcement_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return guard(service.publish,session,auth.institution.id,announcement_id)
@router.post("/{announcement_id}/archive",response_model=AnnouncementReadModel)
def archive(announcement_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return guard(service.archive,session,auth.institution.id,announcement_id)

def feed_response(session,institution_id,user_id,mode):
    return [{**{c.name:getattr(a,c.name) for c in a.__table__.columns},"is_read":read} for a,read in service.feed(session,institution_id=institution_id,user_id=user_id,mode=mode)]

@router.post("/{announcement_id}/read",status_code=204)
def read(announcement_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Annotated[AuthenticatedUserContext,Depends(get_current_user)]):
    guard(service.mark_announcement_read,session,institution_id=auth.institution.id,user_id=auth.user.id,announcement_id=announcement_id)
