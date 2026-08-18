from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user,get_db_session
from app.schemas.communication import NotificationReadModel,UnreadCount
from app.services.authentication import AuthenticatedUserContext
from app.services import communication_service as service
router=APIRouter(prefix="/notifications",tags=["Notifications"])
Auth=Annotated[AuthenticatedUserContext,Depends(get_current_user)]
@router.get("",response_model=list[NotificationReadModel])
def listing(session:Annotated[Session,Depends(get_db_session)],auth:Auth):return service.notifications(session,auth.institution.id,auth.user.id)
@router.get("/unread-count",response_model=UnreadCount)
def count(session:Annotated[Session,Depends(get_db_session)],auth:Auth):return {"unread_count":service.unread_count(session,auth.institution.id,auth.user.id)}
@router.post("/{notification_id}/read",response_model=NotificationReadModel)
def read(notification_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Auth):
    try:return service.mark_notification(session,auth.institution.id,auth.user.id,notification_id)
    except service.CommunicationNotFound as e:raise HTTPException(404,"Notification not found") from e
@router.post("/read-all",status_code=204)
def read_all(session:Annotated[Session,Depends(get_db_session)],auth:Auth):service.mark_all_notifications(session,auth.institution.id,auth.user.id)
