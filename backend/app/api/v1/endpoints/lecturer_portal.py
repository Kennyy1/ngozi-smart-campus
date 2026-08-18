from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session,require_roles
from app.schemas.lecturer_portal import *
from app.services.authentication import AuthenticatedUserContext
from app.services import lecturer_portal_service as service
from pydantic import BaseModel
from app.schemas.communication import AnnouncementReadModel,CourseAnnouncementCreate,TimetableItem,AnnouncementCreate,AnnouncementType,AudienceType
from app.services import communication_service,timetable_service

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
class Rows(BaseModel):records:list[dict]
class Scores(BaseModel):scores:list[dict]
@router.get("/course-offerings/{course_offering_id}/class-sessions")
def sessions(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.class_sessions,session,authenticated,course_offering_id=course_offering_id)
@router.get("/course-offerings/{course_offering_id}/class-sessions/{class_session_id}/attendance")
def sheet(course_offering_id:UUID,class_session_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.attendance_sheet,session,authenticated,course_offering_id=course_offering_id,class_session_id=class_session_id)
@router.put("/course-offerings/{course_offering_id}/class-sessions/{class_session_id}/attendance")
def save_sheet(course_offering_id:UUID,class_session_id:UUID,request:Rows,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.save_attendance,session,authenticated,course_offering_id=course_offering_id,class_session_id=class_session_id,records=request.records)
@router.get("/course-offerings/{course_offering_id}/assessments/{component_id}/scores")
def assessment_sheet(course_offering_id:UUID,component_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.assessment_sheet,session,authenticated,course_offering_id=course_offering_id,component_id=component_id)
@router.put("/course-offerings/{course_offering_id}/assessments/{component_id}/scores")
def assessment_save(course_offering_id:UUID,component_id:UUID,request:Scores,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.save_assessment_scores,session,authenticated,course_offering_id=course_offering_id,component_id=component_id,scores=request.scores)
@router.get("/course-offerings/{course_offering_id}/examinations/{examination_id}/scores")
def examination_sheet(course_offering_id:UUID,examination_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.examination_sheet,session,authenticated,course_offering_id=course_offering_id,examination_id=examination_id)
@router.put("/course-offerings/{course_offering_id}/examinations/{examination_id}/scores")
def examination_save(course_offering_id:UUID,examination_id:UUID,request:Scores,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return call(service.save_examination_scores,session,authenticated,course_offering_id=course_offering_id,examination_id=examination_id,scores=request.scores)
@router.get("/course-offerings/{course_offering_id}/announcements",response_model=list[AnnouncementReadModel])
def offering_announcements(course_offering_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):
    try:return communication_service.lecturer_announcements(session,institution_id=authenticated.institution.id,user_id=authenticated.user.id,offering_id=course_offering_id)
    except communication_service.CommunicationForbidden as e:raise HTTPException(403,str(e)) from e
@router.post("/course-offerings/{course_offering_id}/announcements",response_model=AnnouncementReadModel,status_code=201)
def create_offering_announcement(course_offering_id:UUID,request:CourseAnnouncementCreate,session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):
    try:
        communication_service.lecturer_offering(session,authenticated.institution.id,authenticated.user.id,course_offering_id)
        data=AnnouncementCreate(**request.model_dump(),announcement_type=AnnouncementType.COURSE,audience_type=AudienceType.COURSE_OFFERING,target_ids=[course_offering_id])
        return communication_service.create_announcement(session,institution_id=authenticated.institution.id,user_id=authenticated.user.id,data=data,status="published")
    except communication_service.CommunicationForbidden as e:raise HTTPException(403,str(e)) from e
@router.get("/timetable",response_model=list[TimetableItem])
def timetable(session:Annotated[Session,Depends(get_db_session)],authenticated:LecturerUser):return timetable_service.lecturer_timetable(session,authenticated.institution.id,authenticated.user.id)
