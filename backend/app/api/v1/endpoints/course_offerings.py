from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.course_offering import (
    CourseOfferingCreate,
    CourseOfferingRead,
    CourseOfferingStatus,
    CourseOfferingUpdate,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.course_offering_service import (
    CourseOfferingAcademicSessionNotFoundError,
    CourseOfferingCourseNotFoundError,
    CourseOfferingHierarchyMismatchError,
    CourseOfferingNotFoundError,
    CourseOfferingSemesterNotFoundError,
    DuplicateCourseOfferingError,
    InvalidRegistrationWindowError,
    create_course_offering,
    delete_course_offering,
    get_course_offering,
    list_course_offerings,
    update_course_offering,
)


router = APIRouter(prefix="/course-offerings", tags=["Course Offerings"])
CourseOfferingAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post("", response_model=CourseOfferingRead, status_code=status.HTTP_201_CREATED)
def create_course_offering_endpoint(
    request: CourseOfferingCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseOfferingAdministrator,
) -> CourseOfferingRead:
    try:
        return create_course_offering(
            session,
            institution_id=authenticated.institution.id,
            course_offering_data=request,
        )
    except CourseOfferingCourseNotFoundError as error:
        raise _course_not_found_error() from error
    except CourseOfferingAcademicSessionNotFoundError as error:
        raise _academic_session_not_found_error() from error
    except CourseOfferingSemesterNotFoundError as error:
        raise _semester_not_found_error() from error
    except CourseOfferingHierarchyMismatchError as error:
        raise _hierarchy_not_found_error() from error
    except DuplicateCourseOfferingError as error:
        raise _duplicate_error() from error
    except InvalidRegistrationWindowError as error:
        raise _registration_window_error() from error


@router.get("", response_model=list[CourseOfferingRead])
def list_course_offerings_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseOfferingAdministrator,
    course_id: UUID | None = None,
    academic_session_id: UUID | None = None,
    semester_id: UUID | None = None,
    registration_open: bool | None = None,
    status: CourseOfferingStatus | None = None,
) -> list[CourseOfferingRead]:
    return list_course_offerings(
        session,
        institution_id=authenticated.institution.id,
        course_id=course_id,
        academic_session_id=academic_session_id,
        semester_id=semester_id,
        registration_open=registration_open,
        status=status,
    )


@router.get("/{course_offering_id}", response_model=CourseOfferingRead)
def get_course_offering_endpoint(
    course_offering_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseOfferingAdministrator,
) -> CourseOfferingRead:
    try:
        return get_course_offering(
            session,
            course_offering_id=course_offering_id,
            institution_id=authenticated.institution.id,
        )
    except CourseOfferingNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{course_offering_id}", response_model=CourseOfferingRead)
def update_course_offering_endpoint(
    course_offering_id: UUID,
    request: CourseOfferingUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseOfferingAdministrator,
) -> CourseOfferingRead:
    try:
        return update_course_offering(
            session,
            course_offering_id=course_offering_id,
            institution_id=authenticated.institution.id,
            course_offering_data=request,
        )
    except CourseOfferingNotFoundError as error:
        raise _not_found_error() from error
    except CourseOfferingCourseNotFoundError as error:
        raise _course_not_found_error() from error
    except CourseOfferingAcademicSessionNotFoundError as error:
        raise _academic_session_not_found_error() from error
    except CourseOfferingSemesterNotFoundError as error:
        raise _semester_not_found_error() from error
    except CourseOfferingHierarchyMismatchError as error:
        raise _hierarchy_not_found_error() from error
    except DuplicateCourseOfferingError as error:
        raise _duplicate_error() from error
    except InvalidRegistrationWindowError as error:
        raise _registration_window_error() from error


@router.delete("/{course_offering_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_offering_endpoint(
    course_offering_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseOfferingAdministrator,
) -> Response:
    try:
        delete_course_offering(
            session,
            course_offering_id=course_offering_id,
            institution_id=authenticated.institution.id,
        )
    except CourseOfferingNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course Offering not found")


def _course_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course not found")


def _academic_session_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Academic Session not found")


def _semester_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Semester not found")


def _hierarchy_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course Offering hierarchy not found")


def _duplicate_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Course Offering already exists")


def _registration_window_error() -> HTTPException:
    return HTTPException(status_code=422, detail="Invalid registration window")
