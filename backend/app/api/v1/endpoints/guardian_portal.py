from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session,require_roles
from app.schemas.guardian import *
from app.schemas.student_portal import AttendanceSummary,StudentAcademicPerformance,StudentResult,StudentTranscript
from app.services.authentication import AuthenticatedUserContext
from app.services.guardian_portal_service import *

router=APIRouter(prefix="/guardian-portal",tags=["Guardian Portal"])
GuardianUser=Annotated[AuthenticatedUserContext,Depends(require_roles("guardian"))]
def _call(fn,session,auth,**kwargs):
    try:return fn(session,institution_id=auth.institution.id,user_id=auth.user.id,**kwargs)
    except GuardianPortalNotFoundError as e:raise HTTPException(404,"Guardian resource not found") from e
@router.get("/dashboard",response_model=GuardianDashboard)
def dashboard_endpoint(session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(dashboard,session,auth)
@router.get("/children",response_model=list[GuardianChild])
def children_endpoint(session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(list_children,session,auth)
@router.get("/children/{student_id}/overview",response_model=ChildOverview)
def overview_endpoint(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(overview,session,auth,student_id=student_id)
@router.get("/children/{student_id}/results",response_model=list[StudentResult])
def results_endpoint(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(results,session,auth,student_id=student_id)
@router.get("/children/{student_id}/attendance",response_model=list[AttendanceSummary])
def attendance_endpoint(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(attendance,session,auth,student_id=student_id)
@router.get("/children/{student_id}/academic-performance",response_model=StudentAcademicPerformance)
def performance_endpoint(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(performance,session,auth,student_id=student_id)
@router.get("/children/{student_id}/transcript",response_model=StudentTranscript)
def transcript_endpoint(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(transcript,session,auth,student_id=student_id)
@router.get("/children/{student_id}/clearance",response_model=GuardianClearance)
def clearance_endpoint(student_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:GuardianUser):return _call(clearance,session,auth,student_id=student_id)
