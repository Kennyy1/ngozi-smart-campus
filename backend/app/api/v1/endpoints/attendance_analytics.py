from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.attendance_analytics import (
    AttendanceRiskListResponse,
    ClassSessionAttendanceSummary,
    CourseOfferingAttendanceSummary,
    CourseRegistrationAttendanceSummary,
)
from app.services.attendance_analytics_service import (
    DEFAULT_MINIMUM_PERCENTAGE,
    AttendanceAnalyticsClassSessionNotFoundError,
    AttendanceAnalyticsCourseOfferingNotFoundError,
    AttendanceAnalyticsRegistrationNotFoundError,
    InvalidMinimumPercentageError,
    get_class_session_attendance_summary,
    get_course_offering_attendance_summary,
    get_course_registration_attendance_summary,
    list_at_risk_course_registrations,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(tags=["Attendance Analytics"])
AttendanceAnalyticsAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]
MinimumPercentage = Annotated[float, Query(ge=0, le=100)]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidMinimumPercentageError):
        return HTTPException(422, "minimum_percentage must be between 0 and 100")
    if isinstance(error, AttendanceAnalyticsRegistrationNotFoundError):
        return HTTPException(404, "Course Registration not found")
    if isinstance(error, AttendanceAnalyticsClassSessionNotFoundError):
        return HTTPException(404, "Class Session not found")
    return HTTPException(404, "Course Offering not found")


@router.get(
    "/course-registrations/{course_registration_id}/attendance-summary",
    response_model=CourseRegistrationAttendanceSummary,
)
def registration_summary_endpoint(
    course_registration_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAnalyticsAdministrator,
    minimum_percentage: MinimumPercentage = DEFAULT_MINIMUM_PERCENTAGE,
) -> CourseRegistrationAttendanceSummary:
    try:
        return get_course_registration_attendance_summary(
            session,
            institution_id=authenticated.institution.id,
            course_registration_id=course_registration_id,
            minimum_percentage=minimum_percentage,
        )
    except (AttendanceAnalyticsRegistrationNotFoundError, InvalidMinimumPercentageError) as error:
        raise _map_error(error) from error


@router.get(
    "/class-sessions/{class_session_id}/attendance-summary",
    response_model=ClassSessionAttendanceSummary,
)
def class_session_summary_endpoint(
    class_session_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAnalyticsAdministrator,
) -> ClassSessionAttendanceSummary:
    try:
        return get_class_session_attendance_summary(session, institution_id=authenticated.institution.id, class_session_id=class_session_id)
    except AttendanceAnalyticsClassSessionNotFoundError as error:
        raise _map_error(error) from error


@router.get(
    "/course-offerings/{course_offering_id}/attendance-summary",
    response_model=CourseOfferingAttendanceSummary,
    response_model_exclude_none=True,
)
def course_offering_summary_endpoint(
    course_offering_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAnalyticsAdministrator,
    minimum_percentage: MinimumPercentage = DEFAULT_MINIMUM_PERCENTAGE,
    include_students: bool = False,
) -> CourseOfferingAttendanceSummary:
    try:
        return get_course_offering_attendance_summary(
            session,
            institution_id=authenticated.institution.id,
            course_offering_id=course_offering_id,
            minimum_percentage=minimum_percentage,
            include_students=include_students,
        )
    except (AttendanceAnalyticsCourseOfferingNotFoundError, InvalidMinimumPercentageError) as error:
        raise _map_error(error) from error


@router.get("/attendance-analytics/at-risk", response_model=AttendanceRiskListResponse)
def at_risk_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAnalyticsAdministrator,
    minimum_percentage: MinimumPercentage = DEFAULT_MINIMUM_PERCENTAGE,
    course_offering_id: UUID | None = None,
) -> AttendanceRiskListResponse:
    try:
        return list_at_risk_course_registrations(
            session,
            institution_id=authenticated.institution.id,
            minimum_percentage=minimum_percentage,
            course_offering_id=course_offering_id,
        )
    except (AttendanceAnalyticsCourseOfferingNotFoundError, InvalidMinimumPercentageError) as error:
        raise _map_error(error) from error
