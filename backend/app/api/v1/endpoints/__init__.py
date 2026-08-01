from app.api.v1.endpoints.academic_sessions import (
    router as academic_sessions_router,
)
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.courses import router as courses_router
from app.api.v1.endpoints.course_offerings import (
    router as course_offerings_router,
)
from app.api.v1.endpoints.course_registrations import (
    router as course_registrations_router,
)
from app.api.v1.endpoints.departments import router as departments_router
from app.api.v1.endpoints.faculties import router as faculties_router
from app.api.v1.endpoints.programmes import router as programmes_router
from app.api.v1.endpoints.semesters import router as semesters_router
from app.api.v1.endpoints.students import router as students_router

__all__ = [
    "academic_levels_router",
    "academic_sessions_router",
    "auth_router",
    "courses_router",
    "course_offerings_router",
    "course_registrations_router",
    "departments_router",
    "faculties_router",
    "programmes_router",
    "semesters_router",
    "students_router",
]
from app.api.v1.endpoints.academic_levels import (
    router as academic_levels_router,
)
