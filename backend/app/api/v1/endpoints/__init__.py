from app.api.v1.endpoints.academic_sessions import (
    router as academic_sessions_router,
)
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.departments import router as departments_router
from app.api.v1.endpoints.faculties import router as faculties_router
from app.api.v1.endpoints.programmes import router as programmes_router
from app.api.v1.endpoints.semesters import router as semesters_router

__all__ = [
    "academic_sessions_router",
    "auth_router",
    "departments_router",
    "faculties_router",
    "programmes_router",
    "semesters_router",
]
