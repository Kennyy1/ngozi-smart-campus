from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session,require_roles
from app.schemas.lecturer_portal import *
from app.services.authentication import AuthenticatedUserContext
from app.services import lecturer_portal_service as service

router=APIRouter(prefix="/lecturer-portal",tags=["Lecturer Portal"])
LecturerUser=Annotated[AuthenticatedUserContext,Depends(require_roles("lecturer"))]
def call(fn,session,auth,**kw):
    try:return fn(session,institution_id=auth.institution.id,user_id=auth.user.id,**kw)
    except service.LecturerPortalProfileNotFoundError as e:raise HTTPException(404,"Lecturer profile not found") from e
    except service.LecturerPortalOfferingNotFoundError as e:raise HTTPException(404,"Course Offering not found") from e
@router.get("/dashboard",response_model=LecturerDashboard)
def dashboard(session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.dashboard,session,authenticated)
@router.get("/courses",response_model=list[LecturerCourse])
def courses(session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser,academic_session_id:UUID|None=None,semester_id:UUID|None=None,status:str|None=None):return call(service.list_courses,session,authenticated,academic_session_id=academic_session_id,semester_id=semester_id,status=status)
@router.get("/course-offerings/{course_offering_id}/students",response_model=list[LecturerCourseStudent])
def students(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.list_students,session,authenticated,course_offering_id=course_offering_id)
@router.get("/course-offerings/{course_offering_id}/attendance",response_model=list[LecturerAttendance])
def attendance(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.attendance,session,authenticated,course_offering_id=course_offering_id)
@router.get("/course-offerings/{course_offering_id}/assessments",response_model=list[LecturerAssessment])
def assessments(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.assessments,session,authenticated,course_offering_id=course_offering_id)
@router.get("/course-offerings/{course_offering_id}/examinations",response_model=list[LecturerExamination])
def examinations(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.examinations,session,authenticated,course_offering_id=course_offering_id)
@router.get("/course-offerings/{course_offering_id}/results",response_model=LecturerResultOverview)
def results(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.results,session,authenticated,course_offering_id=course_offering_id)
