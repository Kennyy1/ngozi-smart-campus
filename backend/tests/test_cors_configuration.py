from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.main import app


def test_vite_development_origin_is_allowed() -> None:
    assert "http://localhost:5173" in settings.cors_origins
    cors = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    assert "http://localhost:5173" in cors.kwargs["allow_origins"]
    assert cors.kwargs["allow_credentials"] is False
