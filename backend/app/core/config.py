import os
from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "BIDVERIFY — AI-Powered Bid Compliance Verification Platform"
    PROJECT_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Database & Connection Pooling
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bidverify_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    
    # Rate Limiting & Throttling
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 120
    AUTH_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_LOCKOUT_MINUTES: int = 15

    # JWT Security
    SECRET_KEY: str = "development-secret-key-change-in-production-min32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Storage
    STORAGE_LOCAL_DIR: str = "./storage_data"
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """Enforce production safety rules so insecure defaults fail fast."""
        if self.ENVIRONMENT.lower() == "production":
            insecure_defaults = {
                "development-secret-key-change-in-production-min32chars",
                "secret",
                "changeme",
                "password",
                "123456",
            }
            if self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production safety violation: SECRET_KEY must be a secure random key of at least 32 characters in production."
                )
            if self.DEBUG:
                self.DEBUG = False

        if self.MAX_UPLOAD_SIZE_BYTES <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_BYTES must be greater than 0.")

        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0.")

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
