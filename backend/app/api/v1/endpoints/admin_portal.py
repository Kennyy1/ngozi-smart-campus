from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session,require_roles
from app.schemas.admin_portal import *
from app.services.authentication import AuthenticatedUserContext
from app.services import admin_portal_service as service

router=APIRouter(prefix="/admin-portal",tags=["Administrative Portal"])
Admin=Annotated[AuthenticatedUserContext,Depends(require_roles("administrator","system_super_admin"))]
@router.get("/dashboard",response_model=AdminDashboard)
def dashboard(session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):return service.dashboard(session,institution_id=authenticated.institution.id,institution_name=authenticated.institution.name)
@router.get("/students/{student_id}/summary",response_model=AdminStudentSummary)
def student_summary(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):
    try:return service.student_summary(session,institution_id=authenticated.institution.id,student_id=student_id)
    except service.AdminPortalStudentNotFoundError as e:raise HTTPException(404,"Student not found") from e
@router.get("/course-offerings/{course_offering_id}/summary",response_model=AdminCourseOfferingSummary)
def offering_summary(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):
    try:return service.offering_summary(session,institution_id=authenticated.institution.id,course_offering_id=course_offering_id)
    except service.AdminPortalOfferingNotFoundError as e:raise HTTPException(404,"Course Offering not found") from e
