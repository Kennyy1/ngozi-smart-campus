from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.official_transcript import (
    OfficialTranscriptCreate, OfficialTranscriptRead, OfficialTranscriptStatus,
    OfficialTranscriptUpdate, TranscriptRevokeRequest,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.official_transcript_service import (
    DuplicateTranscriptReferenceError, InvalidOfficialTranscriptTransitionError,
    OfficialTranscriptNotFoundError, OfficialTranscriptStudentNotFoundError,
    create_official_transcript, get_official_transcript,
    get_official_transcript_by_reference, issue_official_transcript,
    list_official_transcripts, refresh_official_transcript,
    revoke_official_transcript, update_official_transcript,
)
from app.services.transcript_service import TranscriptProgrammeNotFoundError, TranscriptStudentNotFoundError


router = APIRouter(prefix="/official-transcripts", tags=["Official Transcripts"])
TranscriptAdministrator = Annotated[AuthenticatedUserContext, Depends(require_roles("administrator", "system_super_admin"))]


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, (OfficialTranscriptNotFoundError, OfficialTranscriptStudentNotFoundError, TranscriptStudentNotFoundError)):
        return HTTPException(404, "Official Transcript or Student not found")
    if isinstance(error, TranscriptProgrammeNotFoundError):
        return HTTPException(409, "Student Programme is not configured")
    if isinstance(error, DuplicateTranscriptReferenceError):
        return HTTPException(409, "Transcript reference conflict")
    return HTTPException(409, "Invalid Official Transcript lifecycle transition")


@router.post("", response_model=OfficialTranscriptRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(request: OfficialTranscriptCreate, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return create_official_transcript(session, institution_id=authenticated.institution.id, user_id=authenticated.user.id, transcript_data=request)
    except (OfficialTranscriptStudentNotFoundError, TranscriptStudentNotFoundError, TranscriptProgrammeNotFoundError, DuplicateTranscriptReferenceError) as error: raise _map_error(error) from error


@router.get("", response_model=list[OfficialTranscriptRead])
def list_endpoint(session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator, student_id: UUID | None = None, programme_id: UUID | None = None, status: OfficialTranscriptStatus | None = None, transcript_reference: str | None = None) -> object:
    return list_official_transcripts(session, institution_id=authenticated.institution.id, student_id=student_id, programme_id=programme_id, status=status, transcript_reference=transcript_reference)


@router.get("/by-reference/{transcript_reference}", response_model=OfficialTranscriptRead)
def by_reference_endpoint(transcript_reference: str, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return get_official_transcript_by_reference(session, institution_id=authenticated.institution.id, transcript_reference=transcript_reference)
    except OfficialTranscriptNotFoundError as error: raise _map_error(error) from error


@router.get("/{transcript_id}", response_model=OfficialTranscriptRead)
def get_endpoint(transcript_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return get_official_transcript(session, institution_id=authenticated.institution.id, transcript_id=transcript_id)
    except OfficialTranscriptNotFoundError as error: raise _map_error(error) from error


@router.patch("/{transcript_id}", response_model=OfficialTranscriptRead)
def update_endpoint(transcript_id: UUID, request: OfficialTranscriptUpdate, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return update_official_transcript(session, institution_id=authenticated.institution.id, transcript_id=transcript_id, transcript_data=request)
    except OfficialTranscriptNotFoundError as error: raise _map_error(error) from error


@router.post("/{transcript_id}/refresh", response_model=OfficialTranscriptRead)
def refresh_endpoint(transcript_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return refresh_official_transcript(session, institution_id=authenticated.institution.id, transcript_id=transcript_id, user_id=authenticated.user.id)
    except (OfficialTranscriptNotFoundError, InvalidOfficialTranscriptTransitionError, TranscriptStudentNotFoundError, TranscriptProgrammeNotFoundError) as error: raise _map_error(error) from error


@router.post("/{transcript_id}/issue", response_model=OfficialTranscriptRead)
def issue_endpoint(transcript_id: UUID, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return issue_official_transcript(session, institution_id=authenticated.institution.id, transcript_id=transcript_id, user_id=authenticated.user.id)
    except (OfficialTranscriptNotFoundError, InvalidOfficialTranscriptTransitionError) as error: raise _map_error(error) from error


@router.post("/{transcript_id}/revoke", response_model=OfficialTranscriptRead)
def revoke_endpoint(transcript_id: UUID, request: TranscriptRevokeRequest, session: Annotated[Session, Depends(get_db_session)], authenticated: TranscriptAdministrator) -> object:
    try: return revoke_official_transcript(session, institution_id=authenticated.institution.id, transcript_id=transcript_id, user_id=authenticated.user.id, request=request)
    except (OfficialTranscriptNotFoundError, InvalidOfficialTranscriptTransitionError) as error: raise _map_error(error) from error
