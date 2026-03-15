"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # Application
    # ==========================================================================
    APP_NAME: str = "Plutus"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str = "postgresql+asyncpg://plutus:plutus@localhost:5432/plutus"

    # Sync URL for Alembic (replace asyncpg with psycopg2)
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # ==========================================================================
    # Redis
    # ==========================================================================
    REDIS_URL: str = "redis://localhost:6379/0"

    # ==========================================================================
    # Security
    # ==========================================================================
    SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            if v.startswith("["):
                import json
                return json.loads(v)
            return [origin.strip() for origin in v.split(",")]
        return v

    # ==========================================================================
    # File Upload
    # ==========================================================================
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = "/app/uploads"
    ALLOWED_EXTENSIONS: list[str] = [".csv", ".xlsx", ".xls"]

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # ==========================================================================
    # Celery
    # ==========================================================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ==========================================================================
    # AI Explanation Layer
    # ==========================================================================
    AI_ENABLED: bool = True
    AI_PROVIDER: Literal["ollama", "anthropic", "openai"] = "ollama"

    # Ollama settings (default)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma:7b"

    # Anthropic settings
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # OpenAI settings
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    # ==========================================================================
    # Reconciliation Defaults
    # ==========================================================================
    # Date tolerance in days for matching
    DEFAULT_DATE_TOLERANCE_DAYS: int = 3

    # Amount tolerance as percentage (0.01 = 1%)
    DEFAULT_AMOUNT_TOLERANCE_PERCENT: float = 0.01

    # Minimum fuzzy match score to consider (0-100)
    DEFAULT_FUZZY_THRESHOLD: int = 85

    # Auto-match threshold (matches above this are auto-approved)
    DEFAULT_AUTO_MATCH_THRESHOLD: float = 0.95

    # Review threshold (matches between this and auto are sent to review)
    DEFAULT_REVIEW_THRESHOLD: float = 0.70


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
