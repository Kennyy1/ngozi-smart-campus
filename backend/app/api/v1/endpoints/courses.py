from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_roles
from app.schemas.course import (
    CourseCreate,
    CourseRead,
    CourseStatus,
    CourseType,
    CourseUpdate,
)
from app.services.authentication import AuthenticatedUserContext
from app.services.course_service import (
    CourseAcademicLevelNotFoundError,
    CourseDepartmentNotFoundError,
    CourseHierarchyMismatchError,
    CourseNotFoundError,
    CourseProgrammeNotFoundError,
    DuplicateCourseCodeError,
    DuplicateCourseError,
    DuplicateCourseTitleError,
    create_course,
    delete_course,
    get_course,
    list_courses,
    update_course,
)


router = APIRouter(prefix="/courses", tags=["Courses"])
CourseAdministrator = Annotated[
    AuthenticatedUserContext,
    Depends(require_roles("administrator", "system_super_admin")),
]


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course_endpoint(
    request: CourseCreate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseAdministrator,
) -> CourseRead:
    try:
        return create_course(
            session,
            institution_id=authenticated.institution.id,
            course_data=request,
        )
    except CourseDepartmentNotFoundError as error:
        raise _department_not_found_error() from error
    except CourseProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except CourseAcademicLevelNotFoundError as error:
        raise _academic_level_not_found_error() from error
    except CourseHierarchyMismatchError as error:
        raise _hierarchy_not_found_error() from error
    except (
        DuplicateCourseCodeError,
        DuplicateCourseTitleError,
        DuplicateCourseError,
    ) as error:
        raise _duplicate_error(error) from error


@router.get("", response_model=list[CourseRead])
def list_courses_endpoint(
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseAdministrator,
    department_id: UUID | None = None,
    programme_id: UUID | None = None,
    academic_level_id: UUID | None = None,
    course_type: CourseType | None = None,
    status: CourseStatus | None = None,
) -> list[CourseRead]:
    return list_courses(
        session,
        institution_id=authenticated.institution.id,
        department_id=department_id,
        programme_id=programme_id,
        academic_level_id=academic_level_id,
        course_type=course_type,
        status=status,
    )


@router.get("/{course_id}", response_model=CourseRead)
def get_course_endpoint(
    course_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseAdministrator,
) -> CourseRead:
    try:
        return get_course(
            session,
            course_id=course_id,
            institution_id=authenticated.institution.id,
        )
    except CourseNotFoundError as error:
        raise _not_found_error() from error


@router.patch("/{course_id}", response_model=CourseRead)
def update_course_endpoint(
    course_id: UUID,
    request: CourseUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseAdministrator,
) -> CourseRead:
    try:
        return update_course(
            session,
            course_id=course_id,
            institution_id=authenticated.institution.id,
            course_data=request,
        )
    except CourseNotFoundError as error:
        raise _not_found_error() from error
    except CourseDepartmentNotFoundError as error:
        raise _department_not_found_error() from error
    except CourseProgrammeNotFoundError as error:
        raise _programme_not_found_error() from error
    except CourseAcademicLevelNotFoundError as error:
        raise _academic_level_not_found_error() from error
    except CourseHierarchyMismatchError as error:
        raise _hierarchy_not_found_error() from error
    except (
        DuplicateCourseCodeError,
        DuplicateCourseTitleError,
        DuplicateCourseError,
    ) as error:
        raise _duplicate_error(error) from error


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_endpoint(
    course_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    authenticated: CourseAdministrator,
) -> Response:
    try:
        delete_course(
            session,
            course_id=course_id,
            institution_id=authenticated.institution.id,
        )
    except CourseNotFoundError as error:
        raise _not_found_error() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course not found")


def _department_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Department not found")


def _programme_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Programme not found")


def _academic_level_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Academic Level not found")


def _hierarchy_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Course hierarchy not found")


def _duplicate_error(error: Exception) -> HTTPException:
    if isinstance(error, DuplicateCourseCodeError):
        detail = "Course code already exists"
    elif isinstance(error, DuplicateCourseTitleError):
        detail = "Course title already exists for this Programme and Academic Level"
    else:
        detail = "Course already exists"
    return HTTPException(status_code=409, detail=detail)
