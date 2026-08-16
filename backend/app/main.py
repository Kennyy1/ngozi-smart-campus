from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title="Ngozi Smart Campus API",
    version="0.1.0",
    description="Backend and middleware API for the Ngozi Smart Campus platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")
