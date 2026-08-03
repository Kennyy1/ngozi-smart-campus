from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.attendance_record import (
    AttendanceBulkCreate,
    AttendanceBulkResult,
    AttendanceRecordCreate,
    AttendanceRecordRead,
    AttendanceRecordStatus,
    AttendanceRecordUpdate,
    AttendanceStatus,
)
from app.services.attendance_record_service import (
    AttendanceClassSessionNotFoundError,
    AttendanceCourseRegistrationNotFoundError,
    AttendanceOfferingMismatchError,
    AttendanceRecordNotFoundError,
    AttendanceRecorderUnauthorizedError,
    AttendanceRegistrationUnavailableError,
    AttendanceSessionUnavailableError,
    DuplicateAttendanceRecordError,
    InvalidAttendanceStateError,
    create_attendance_record,
    create_attendance_records_bulk,
    delete_attendance_record,
    get_attendance_record,
    list_attendance_records,
    update_attendance_record,
)
from app.services.authentication import AuthenticatedUserContext


router = APIRouter(prefix="/attendance-records", tags=["Attendance Records"])
AttendanceAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, AttendanceClassSessionNotFoundError):
        return HTTPException(404, "Class Session not found")
    if isinstance(error, AttendanceCourseRegistrationNotFoundError):
        return HTTPException(404, "Course Registration not found")
    if isinstance(error, AttendanceRecordNotFoundError):
        return HTTPException(404, "Attendance Record not found")
    if isinstance(error, DuplicateAttendanceRecordError):
        return HTTPException(409, "Attendance Record already exists")
    if isinstance(error, AttendanceOfferingMismatchError):
        return HTTPException(409, "Registration and Class Session Course Offerings do not match")
    if isinstance(error, AttendanceRegistrationUnavailableError):
        return HTTPException(409, "Course Registration is unavailable for attendance")
    if isinstance(error, AttendanceSessionUnavailableError):
        return HTTPException(409, "Class Session is unavailable for attendance")
    if isinstance(error, AttendanceRecorderUnauthorizedError):
        return HTTPException(403, "Recorder is not authorized")
    return HTTPException(422, "Invalid Attendance Record")


ATTENDANCE_ERRORS = (
    AttendanceClassSessionNotFoundError,
    AttendanceCourseRegistrationNotFoundError,
    AttendanceOfferingMismatchError,
    AttendanceRecordNotFoundError,
    AttendanceRecorderUnauthorizedError,
    AttendanceRegistrationUnavailableError,
    AttendanceSessionUnavailableError,
    DuplicateAttendanceRecordError,
    InvalidAttendanceStateError,
)


@router.post("", response_model=AttendanceRecordRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(
    request: AttendanceRecordCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAdministrator,
) -> AttendanceRecordRead:
    try:
        return create_attendance_record(
            session,
            institution_id=authenticated.institution.id,
            recorded_by_user_id=authenticated.user.id,
            attendance_data=request,
        )
    except ATTENDANCE_ERRORS as error:
        raise _map_error(error) from error


@router.post("/bulk", response_model=AttendanceBulkResult, status_code=status.HTTP_201_CREATED)
def create_bulk_endpoint(
    request: AttendanceBulkCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAdministrator,
) -> AttendanceBulkResult:
    try:
        records = create_attendance_records_bulk(
            session,
            institution_id=authenticated.institution.id,
            recorded_by_user_id=authenticated.user.id,
            attendance_data=request,
        )
        return AttendanceBulkResult(records=records)
    except ATTENDANCE_ERRORS as error:
        raise _map_error(error) from error


@router.get("", response_model=list[AttendanceRecordRead])
def list_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAdministrator,
    class_session_id: UUID | None = None,
    course_registration_id: UUID | None = None,
    attendance_status: AttendanceStatus | None = None,
    recorded_by_user_id: UUID | None = None,
    status: AttendanceRecordStatus | None = None,
) -> list[AttendanceRecordRead]:
    return list_attendance_records(
        session,
        institution_id=authenticated.institution.id,
        class_session_id=class_session_id,
        course_registration_id=course_registration_id,
        attendance_status=attendance_status,
        recorded_by_user_id=recorded_by_user_id,
        status=status,
    )


@router.get("/{attendance_record_id}", response_model=AttendanceRecordRead)
def get_endpoint(
    attendance_record_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAdministrator,
) -> AttendanceRecordRead:
    try:
        return get_attendance_record(session, attendance_record_id=attendance_record_id, institution_id=authenticated.institution.id)
    except ATTENDANCE_ERRORS as error:
        raise _map_error(error) from error


@router.patch("/{attendance_record_id}", response_model=AttendanceRecordRead)
def update_endpoint(
    attendance_record_id: UUID,
    request: AttendanceRecordUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAdministrator,
) -> AttendanceRecordRead:
    try:
        return update_attendance_record(
            session,
            attendance_record_id=attendance_record_id,
            institution_id=authenticated.institution.id,
            attendance_data=request,
        )
    except ATTENDANCE_ERRORS as error:
        raise _map_error(error) from error


@router.delete("/{attendance_record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(
    attendance_record_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: AttendanceAdministrator,
) -> Response:
    try:
        delete_attendance_record(session, attendance_record_id=attendance_record_id, institution_id=authenticated.institution.id)
    except ATTENDANCE_ERRORS as error:
        raise _map_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
