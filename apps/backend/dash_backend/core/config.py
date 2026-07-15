"""Application configuration.

All configuration is sourced from environment variables (optionally
loaded from a local .env file during development). Nothing is
hardcoded, and no secrets live in source control.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Values are read from environment variables. See `.env.example`
    at the repository root for the full list of supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---------------------------------------------------
    APP_NAME: str = "DASH Backend"
    ENVIRONMENT: str = Field(default="development")  # development | staging | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Server ------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Logging -----------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # --- CORS ----------------------------------------------------------
    # Comma-separated list of allowed origins, e.g.
    # "http://localhost:3000,http://localhost:5173"
    CORS_ORIGINS: str = Field(default="http://localhost:3000")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- Database (connection plumbing only, no models yet) ----------
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://dash:dash@localhost:5432/dash",
        description="SQLAlchemy database URL, e.g. postgresql+psycopg://user:pass@host:port/db",
    )
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # --- Redis (connection info only, not wired up yet) ---------------
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # --- AI Providers -------------------------------------------------
    OPENAI_API_KEY: str | None = Field(default=None)
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.2")
    AI_PROVIDER: str = Field(default="openai")  # "openai" or "ollama"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Using lru_cache ensures environment variables are parsed once
    and the same Settings object is reused across the app.
    """

    return Settings()