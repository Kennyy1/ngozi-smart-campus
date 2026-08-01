from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.course_registration import (
    CourseRegistrationCreate,
    CourseRegistrationRead,
    CourseRegistrationUpdate,
    RegistrationStatus,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.course_registration_service import (
    CourseOfferingCapacityError,
    CourseRegistrationNotFoundError,
    CourseRegistrationOfferingNotFoundError,
    CourseRegistrationOfferingUnavailableError,
    CourseRegistrationStudentNotFoundError,
    CourseRegistrationWindowError,
    DuplicateCourseRegistrationError,
    StudentCourseCompatibilityError,
    create_course_registration,
    delete_course_registration,
    get_course_registration,
    list_course_registrations,
    update_course_registration,
)


router = APIRouter(prefix="/course-registrations", tags=["Course Registrations"])
CourseRegistrationAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post("", response_model=CourseRegistrationRead, status_code=status.HTTP_201_CREATED)
def create_course_registration_endpoint(
    request: CourseRegistrationCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseRegistrationAdministrator,
) -> CourseRegistrationRead:
    try:
        return create_course_registration(
            session,
            institution_id=authenticated.institution.id,
            course_registration_data=request,
        )
    except CourseRegistrationStudentNotFoundError as error:
        raise _student_not_found_error() from error
    except CourseRegistrationOfferingNotFoundError as error:
        raise _offering_not_found_error() from error
    except DuplicateCourseRegistrationError as error:
        raise _duplicate_error() from error
    except CourseOfferingCapacityError as error:
        raise _capacity_error() from error
    except CourseRegistrationOfferingUnavailableError as error:
        raise _offering_unavailable_error() from error
    except CourseRegistrationWindowError as error:
        raise _window_error() from error
    except StudentCourseCompatibilityError as error:
        raise _compatibility_error() from error


@router.get("", response_model=list[CourseRegistrationRead])
def list_course_registrations_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseRegistrationAdministrator,
    student_id: UUID | None = None,
    course_offering_id: UUID | None = None,
    registration_status: RegistrationStatus | None = None,
) -> list[CourseRegistrationRead]:
    return list_course_registrations(
        session,
        institution_id=authenticated.institution.id,
        student_id=student_id,
        course_offering_id=course_offering_id,
        registration_status=registration_status,
    )


@router.get("/{course_registration_id}", response_model=CourseRegistrationRead)
def get_course_registration_endpoint(
    course_registration_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseRegistrationAdministrator,
) -> CourseRegistrationRead:
    try:
        return get_course_registration(
            session,
            course_registration_id=course_registration_id,
            institution_id=authenticated.institution.id,
        )
    except CourseRegistrationNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{course_registration_id}", response_model=CourseRegistrationRead)
def update_course_registration_endpoint(
    course_registration_id: UUID,
    request: CourseRegistrationUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseRegistrationAdministrator,
) -> CourseRegistrationRead:
    try:
        return update_course_registration(
            session,
            course_registration_id=course_registration_id,
            institution_id=authenticated.institution.id,
            course_registration_data=request,
        )
    except CourseRegistrationNotFoundError as error:
        raise _not_found_error() from error
    except CourseRegistrationStudentNotFoundError as error:
        raise _student_not_found_error() from error
    except CourseRegistrationOfferingNotFoundError as error:
        raise _offering_not_found_error() from error
    except DuplicateCourseRegistrationError as error:
        raise _duplicate_error() from error
    except CourseOfferingCapacityError as error:
        raise _capacity_error() from error
    except CourseRegistrationOfferingUnavailableError as error:
        raise _offering_unavailable_error() from error
    except CourseRegistrationWindowError as error:
        raise _window_error() from error
    except StudentCourseCompatibilityError as error:
        raise _compatibility_error() from error


@router.delete("/{course_registration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_registration_endpoint(
    course_registration_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseRegistrationAdministrator,
) -> Response:
    try:
        delete_course_registration(
            session,
            course_registration_id=course_registration_id,
            institution_id=authenticated.institution.id,
        )
    except CourseRegistrationNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course Registration not found")


def _student_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Student not found")


def _offering_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course Offering not found")


def _duplicate_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Course Registration already exists")


def _capacity_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Course Offering is at capacity")


def _offering_unavailable_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Course Offering registration is unavailable")


def _window_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Registration is outside the allowed window")


def _compatibility_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Student is not compatible with this Course")
