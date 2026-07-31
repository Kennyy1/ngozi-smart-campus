from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.departments import router as departments_router
from app.api.v1.endpoints.faculties import router as faculties_router
from app.api.v1.endpoints.programmes import router as programmes_router

__all__ = [
    "auth_router",
    "departments_router",
    "faculties_router",
    "programmes_router",
]
