from typing import ClassVar
from pathlib import Path

from pydantic import PositiveInt, SecretStr, field_validator
from sqlalchemy import URL
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPPORTED_JWT_ALGORITHMS: ClassVar[frozenset[str]] = frozenset({"HS256"})

    APP_NAME: str = "Ngozi Smart Campus API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "ngozi_smart_campus"
    DATABASE_USER: str = "ngozi_admin"
    DATABASE_PASSWORD: str = ""

    JWT_SECRET_KEY: SecretStr = SecretStr("replace-with-a-long-random-secret")
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "ngozi-smart-campus"
    JWT_AUDIENCE: str = "ngozi-smart-campus-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: PositiveInt = 15
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    COURSE_MATERIAL_STORAGE_DIR: Path = Path("runtime/course_materials")
    COURSE_MATERIAL_MAX_UPLOAD_BYTES: PositiveInt = 25 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value not in cls.SUPPORTED_JWT_ALGORITHMS:
            raise ValueError("Unsupported JWT algorithm")
        return value

    @property
    def DATABASE_URL(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.DATABASE_USER,
            password=self.DATABASE_PASSWORD,
            host=self.DATABASE_HOST,
            port=self.DATABASE_PORT,
            database=self.DATABASE_NAME,
        )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
