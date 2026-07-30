from fastapi import APIRouter

from app.api.v1.endpoints import auth_router, faculties_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(faculties_router)
