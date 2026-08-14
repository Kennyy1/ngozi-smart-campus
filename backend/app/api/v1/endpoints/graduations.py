from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.graduation_record import (
    GraduationRecordConfirm, GraduationRecordCreate, GraduationRecordRead,
    GraduationRecordRevoke, GraduationRecordStatus, GraduationRecordUpdate,
)
from app.services.academic_performance_service import AcademicPerformanceStudentNotFoundError, InvalidCourseCreditUnitsError
from app.services.academic_progression_service import AcademicProgressionProgrammeNotFoundError, AcademicProgressionStudentNotFoundError
from app.services.authentication import AuthenticatedUserContext
from app.services.graduation_eligibility_service import GraduationEligibilityProgrammeNotFoundError, GraduationEligibilityStudentNotFoundError
from app.services.graduation_service import (
    DuplicateGraduationRecordError, GraduationOutcomeUnavailableError,
    GraduationProgrammeNotFoundError, GraduationRecordNotFoundError,
    GraduationReferenceConflictError, GraduationStudentIneligibleError,
    GraduationStudentNotFoundError, InvalidGraduationDateError,
    InvalidGraduationTransitionError, confirm_graduation,
    create_graduation_record, get_graduation_record,
    get_graduation_record_by_reference, list_graduation_records,
    refresh_graduation_record, revoke_graduation, update_graduation_record,
)


router = APIRouter(prefix="/graduations", tags=["Graduation Management"])
GraduationAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, (GraduationRecordNotFoundError, GraduationStudentNotFoundError, GraduationEligibilityStudentNotFoundError, AcademicProgressionStudentNotFoundError, AcademicPerformanceStudentNotFoundError)):
        return HTTPException(404, "Graduation Record or Student not found")
    if isinstance(error, (GraduationProgrammeNotFoundError, GraduationEligibilityProgrammeNotFoundError, AcademicProgressionProgrammeNotFoundError)):
        return HTTPException(409, "Student Programme is not configured")
    if isinstance(error, GraduationStudentIneligibleError):
        return HTTPException(409, "Student is not eligible for graduation")
    if isinstance(error, GraduationOutcomeUnavailableError):
        return HTTPException(409, "Graduation outcome is not available")
    if isinstance(error, DuplicateGraduationRecordError):
        return HTTPException(409, "An active Graduation Record already exists")
    if isinstance(error, GraduationReferenceConflictError):
        return HTTPException(409, "Graduation reference conflict")
    if isinstance(error, InvalidGraduationDateError):
        return HTTPException(409, "Graduation date cannot precede admission year")
    if isinstance(error, InvalidCourseCreditUnitsError):
        return HTTPException(409, "Course has invalid credit units")
    return HTTPException(409, "Invalid Graduation Record lifecycle transition")


DOMAIN_ERRORS = (
    GraduationRecordNotFoundError, GraduationStudentNotFoundError,
    GraduationProgrammeNotFoundError, GraduationStudentIneligibleError,
    GraduationOutcomeUnavailableError, DuplicateGraduationRecordError,
    GraduationReferenceConflictError, InvalidGraduationTransitionError,
    InvalidGraduationDateError, GraduationEligibilityStudentNotFoundError,
    GraduationEligibilityProgrammeNotFoundError, AcademicProgressionStudentNotFoundError,
    AcademicProgressionProgrammeNotFoundError, AcademicPerformanceStudentNotFoundError,
    InvalidCourseCreditUnitsError,
)


@router.post("", response_model=GraduationRecordRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: GraduationRecordCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return create_graduation_record(session, institution_id=authenticated.institution.id, user_id=authenticated.user.id, graduation_data=request)
    except DOMAIN_ERRORS as error:
        raise _map_error(error) from error


@router.get("", response_model=list[GraduationRecordRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator, student_id: UUID | None = None, programme_id: UUID | None = None, status: GraduationRecordStatus | None = None, graduation_reference: str | None = None, graduation_date: date | None = None, degree_classification: str | None = None) -> object:
    return list_graduation_records(session, institution_id=authenticated.institution.id, student_id=student_id, programme_id=programme_id, status=status, graduation_reference=graduation_reference, graduation_date=graduation_date, degree_classification=degree_classification)


@router.get("/by-reference/{graduation_reference}", response_model=GraduationRecordRead)
def by_reference_endpoint(graduation_reference: str, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return get_graduation_record_by_reference(session, institution_id=authenticated.institution.id, graduation_reference=graduation_reference)
    except GraduationRecordNotFoundError as error:
        raise _map_error(error) from error


@router.get("/{graduation_id}", response_model=GraduationRecordRead)
def get_endpoint(graduation_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return get_graduation_record(session, institution_id=authenticated.institution.id, graduation_id=graduation_id)
    except GraduationRecordNotFoundError as error:
        raise _map_error(error) from error


@router.patch("/{graduation_id}", response_model=GraduationRecordRead)
def update_endpoint(graduation_id: UUID, request: GraduationRecordUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return update_graduation_record(session, institution_id=authenticated.institution.id, graduation_id=graduation_id, graduation_data=request)
    except GraduationRecordNotFoundError as error:
        raise _map_error(error) from error


@router.post("/{graduation_id}/refresh", response_model=GraduationRecordRead)
def refresh_endpoint(graduation_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return refresh_graduation_record(session, institution_id=authenticated.institution.id, graduation_id=graduation_id, user_id=authenticated.user.id)
    except DOMAIN_ERRORS as error:
        raise _map_error(error) from error


@router.post("/{graduation_id}/confirm", response_model=GraduationRecordRead)
def confirm_endpoint(graduation_id: UUID, request: GraduationRecordConfirm, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return confirm_graduation(session, institution_id=authenticated.institution.id, graduation_id=graduation_id, user_id=authenticated.user.id, request=request)
    except DOMAIN_ERRORS as error:
        raise _map_error(error) from error


@router.post("/{graduation_id}/revoke", response_model=GraduationRecordRead)
def revoke_endpoint(graduation_id: UUID, request: GraduationRecordRevoke, session: Annotated[Session, Depends(get_db_session)], authenticated: GraduationAdministrator) -> object:
    try:
        return revoke_graduation(session, institution_id=authenticated.institution.id, graduation_id=graduation_id, user_id=authenticated.user.id, request=request)
    except DOMAIN_ERRORS as error:
        raise _map_error(error) from error
