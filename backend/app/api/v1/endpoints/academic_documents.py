from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.academic_document import (
    AcademicDocumentCreate, AcademicDocumentRead, AcademicDocumentRevoke,
    AcademicDocumentStatus, AcademicDocumentType, AcademicDocumentUpdate,
    PublicAcademicDocumentVerification,
)
from app.services.academic_document_service import (
    AcademicDocumentIdentifierConflictError, AcademicDocumentNotFoundError,
    AcademicDocumentProgrammeNotFoundError, AcademicDocumentSourceNotFoundError,
    AcademicDocumentStudentNotFoundError, DuplicateAcademicDocumentDraftError,
    InvalidAcademicDocumentSourceError, InvalidAcademicDocumentTransitionError,
    create_academic_document, get_academic_document,
    get_academic_document_by_reference, get_academic_document_by_verification_code,
    issue_academic_document, list_academic_documents, refresh_academic_document,
    revoke_academic_document, update_academic_document, verify_public_academic_document,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.transcript_service import TranscriptProgrammeNotFoundError, TranscriptStudentNotFoundError


router = APIRouter(prefix="/academic-documents", tags=["Academic Documents"])
public_router = APIRouter(prefix="/public", tags=["Public Academic Document Verification"])
DocumentAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, (AcademicDocumentNotFoundError, AcademicDocumentStudentNotFoundError, AcademicDocumentSourceNotFoundError, TranscriptStudentNotFoundError)):
        return HTTPException(404, "Academic Document or source not found")
    if isinstance(error, (AcademicDocumentProgrammeNotFoundError, TranscriptProgrammeNotFoundError)):
        return HTTPException(409, "Student Programme is not configured")
    if isinstance(error, DuplicateAcademicDocumentDraftError):
        return HTTPException(409, "An active draft already exists for this source")
    if isinstance(error, AcademicDocumentIdentifierConflictError):
        return HTTPException(409, "Academic Document identifier conflict")
    if isinstance(error, InvalidAcademicDocumentSourceError):
        return HTTPException(409, "Academic Document source is not valid")
    return HTTPException(409, "Invalid Academic Document lifecycle transition")


@router.post("", response_model=AcademicDocumentRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: AcademicDocumentCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try:
        return create_academic_document(session, institution_id=authenticated.institution.id, user_id=authenticated.user.id, document_data=request)
    except (AcademicDocumentStudentNotFoundError, AcademicDocumentProgrammeNotFoundError, AcademicDocumentSourceNotFoundError, InvalidAcademicDocumentSourceError, DuplicateAcademicDocumentDraftError, AcademicDocumentIdentifierConflictError, TranscriptStudentNotFoundError, TranscriptProgrammeNotFoundError) as error:
        raise _map_error(error) from error


@router.get("", response_model=list[AcademicDocumentRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator, student_id: UUID | None = None, programme_id: UUID | None = None, document_type: AcademicDocumentType | None = None, status: AcademicDocumentStatus | None = None, document_reference: str | None = None, graduation_record_id: UUID | None = None, issued_by_user_id: UUID | None = None) -> object:
    return list_academic_documents(session, institution_id=authenticated.institution.id, student_id=student_id, programme_id=programme_id, document_type=document_type, status=status, document_reference=document_reference, graduation_record_id=graduation_record_id, issued_by_user_id=issued_by_user_id)


@router.get("/by-reference/{document_reference}", response_model=AcademicDocumentRead)
def by_reference_endpoint(document_reference: str, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return get_academic_document_by_reference(session, institution_id=authenticated.institution.id, document_reference=document_reference)
    except AcademicDocumentNotFoundError as error: raise _map_error(error) from error


@router.get("/by-verification-code/{verification_code}", response_model=AcademicDocumentRead)
def by_verification_code_endpoint(verification_code: str, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return get_academic_document_by_verification_code(session, institution_id=authenticated.institution.id, verification_code=verification_code)
    except AcademicDocumentNotFoundError as error: raise _map_error(error) from error


@router.get("/{document_id}", response_model=AcademicDocumentRead)
def get_endpoint(document_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return get_academic_document(session, institution_id=authenticated.institution.id, document_id=document_id)
    except AcademicDocumentNotFoundError as error: raise _map_error(error) from error


@router.patch("/{document_id}", response_model=AcademicDocumentRead)
def update_endpoint(document_id: UUID, request: AcademicDocumentUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return update_academic_document(session, institution_id=authenticated.institution.id, document_id=document_id, document_data=request)
    except AcademicDocumentNotFoundError as error: raise _map_error(error) from error


@router.post("/{document_id}/refresh", response_model=AcademicDocumentRead)
def refresh_endpoint(document_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return refresh_academic_document(session, institution_id=authenticated.institution.id, document_id=document_id, user_id=authenticated.user.id)
    except (AcademicDocumentNotFoundError, AcademicDocumentStudentNotFoundError, AcademicDocumentProgrammeNotFoundError, AcademicDocumentSourceNotFoundError, InvalidAcademicDocumentSourceError, InvalidAcademicDocumentTransitionError, TranscriptStudentNotFoundError, TranscriptProgrammeNotFoundError) as error: raise _map_error(error) from error


@router.post("/{document_id}/issue", response_model=AcademicDocumentRead)
def issue_endpoint(document_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return issue_academic_document(session, institution_id=authenticated.institution.id, document_id=document_id, user_id=authenticated.user.id)
    except (AcademicDocumentNotFoundError, AcademicDocumentStudentNotFoundError, AcademicDocumentSourceNotFoundError, InvalidAcademicDocumentSourceError, InvalidAcademicDocumentTransitionError, TranscriptStudentNotFoundError, TranscriptProgrammeNotFoundError) as error: raise _map_error(error) from error


@router.post("/{document_id}/revoke", response_model=AcademicDocumentRead)
def revoke_endpoint(document_id: UUID, request: AcademicDocumentRevoke, session: Annotated[Session, Depends(get_db_session)], authenticated: DocumentAdministrator) -> object:
    try: return revoke_academic_document(session, institution_id=authenticated.institution.id, document_id=document_id, user_id=authenticated.user.id, request=request)
    except (AcademicDocumentNotFoundError, InvalidAcademicDocumentTransitionError) as error: raise _map_error(error) from error


@public_router.get("/academic-document-verification/{verification_code}", response_model=PublicAcademicDocumentVerification)
def public_verification_endpoint(verification_code: str, session: Annotated[Session, Depends(get_db_session)]) -> object:
    try: return verify_public_academic_document(session, verification_code=verification_code)
    except AcademicDocumentNotFoundError as error: raise HTTPException(404, "Academic Document verification not found") from error
