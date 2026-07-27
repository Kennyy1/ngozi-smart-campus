from fastapi import FastAPI

from app.api.routes.health import router as health_router

app = FastAPI(
    title="Ngozi Smart Campus API",
    version="0.1.0",
    description="Backend and middleware API for the Ngozi Smart Campus platform.",
)

app.include_router(health_router)
