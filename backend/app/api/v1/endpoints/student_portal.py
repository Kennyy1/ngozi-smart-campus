from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.student_portal import *
from app.services.authentication import AuthenticatedUserContext
from app.services.student_portal_service import *
from app.schemas.communication import AnnouncementReadModel,TimetableItem
from app.api.v1.endpoints.announcements import feed_response
from app.services import timetable_service

router=APIRouter(prefix="/student-portal",tags=["Student Portal"])
StudentUser=Annotated[AuthenticatedUserContext,Depends(require_roles("student"))]

def _call(fn, session, auth, **kwargs):
    try: return fn(session,institution_id=auth.institution.id,user_id=auth.user.id,**kwargs)
    except StudentPortalProfileNotFoundError as error: raise HTTPException(404,"Student profile not found") from error

@router.get("/dashboard",response_model=StudentDashboard)
def dashboard_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser): return _call(get_dashboard,session,authenticated)
@router.get("/profile",response_model=StudentProfile)
def profile_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser): return _call(get_profile,session,authenticated)
@router.get("/courses",response_model=list[StudentCourse])
def courses_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser,academic_session_id:UUID|None=None,semester_id:UUID|None=None,registration_status:str|None=None): return _call(list_courses,session,authenticated,academic_session_id=academic_session_id,semester_id=semester_id,registration_status=registration_status)
@router.get("/attendance",response_model=list[AttendanceSummary])
def attendance_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser): return _call(list_attendance,session,authenticated)
@router.get("/results",response_model=list[StudentResult])
def results_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser,academic_session_id:UUID|None=None,semester_id:UUID|None=None): return _call(list_results,session,authenticated,academic_session_id=academic_session_id,semester_id=semester_id)
@router.get("/academic-performance",response_model=StudentAcademicPerformance)
def performance_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser): return _call(get_academic_performance,session,authenticated)
@router.get("/transcript",response_model=StudentTranscript)
def transcript_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser):
    student=resolve_student(session,institution_id=authenticated.institution.id,user_id=authenticated.user.id)
    return get_transcript(session,institution_id=authenticated.institution.id,student_id=student.id)
@router.get("/clearance",response_model=StudentClearance)
def clearance_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser):
    student=resolve_student(session,institution_id=authenticated.institution.id,user_id=authenticated.user.id)
    return get_clearance(session,institution_id=authenticated.institution.id,student_id=student.id)
@router.get("/documents",response_model=list[StudentDocument])
def documents_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser): return _call(list_documents,session,authenticated)
@router.get("/announcements",response_model=list[AnnouncementReadModel])
def announcements_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser,view:str="current"):
    if view not in {"current","unread","all"}:raise HTTPException(422,"view must be current, unread, or all")
    return feed_response(session,authenticated.institution.id,authenticated.user.id,view)
@router.get("/timetable",response_model=list[TimetableItem])
def timetable_endpoint(session:Annotated[Session,Depends(get_db_session)],authenticated:StudentUser):return timetable_service.student_timetable(session,authenticated.institution.id,authenticated.user.id)
