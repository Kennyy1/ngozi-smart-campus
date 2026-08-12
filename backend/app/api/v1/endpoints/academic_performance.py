from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.academic_performance import CGPAResult, SemesterGPAResult
from app.services.academic_performance_service import (
    AcademicPerformanceSemesterNotFoundError,
    AcademicPerformanceSessionNotFoundError,
    AcademicPerformanceStudentNotFoundError,
    InvalidCourseCreditUnitsError,
    compute_student_cgpa,
    compute_student_semester_gpa,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(tags=["Academic Performance"])
AcademicPerformanceAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, AcademicPerformanceStudentNotFoundError): return HTTPException(404, "Student not found")
    if isinstance(error, AcademicPerformanceSemesterNotFoundError): return HTTPException(404, "Semester not found")
    if isinstance(error, AcademicPerformanceSessionNotFoundError): return HTTPException(404, "Academic Session not found")
    return HTTPException(409, "Course has invalid credit units")


@router.get("/students/{student_id}/semesters/{semester_id}/gpa", response_model=SemesterGPAResult)
def semester_gpa_endpoint(student_id: UUID, semester_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AcademicPerformanceAdministrator) -> SemesterGPAResult:
    try: return compute_student_semester_gpa(session, institution_id=authenticated.institution.id, student_id=student_id, semester_id=semester_id)
    except (AcademicPerformanceStudentNotFoundError, AcademicPerformanceSemesterNotFoundError, AcademicPerformanceSessionNotFoundError, InvalidCourseCreditUnitsError) as error: raise _map_error(error) from error


@router.get("/students/{student_id}/cgpa", response_model=CGPAResult)
def cgpa_endpoint(student_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: AcademicPerformanceAdministrator) -> CGPAResult:
    try: return compute_student_cgpa(session, institution_id=authenticated.institution.id, student_id=student_id)
    except (AcademicPerformanceStudentNotFoundError, InvalidCourseCreditUnitsError) as error: raise _map_error(error) from error
