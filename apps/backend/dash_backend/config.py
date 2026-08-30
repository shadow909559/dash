"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the DASH backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DASH_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "DASH Backend"
    env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Loopback by default. DASH must never expose its control API to the LAN
    # implicitly; set DASH_HOST=0.0.0.0 only with an explicit deployment
    # reason (see docs/Security.md) — authentication is mandatory regardless.
    # In production (Fly.io, Docker), HOST must be 0.0.0.0 to accept connections.
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"

    # Extra directories the /files API may touch (comma-separated). The user's
    # special folders are always allowed; this extends the allow-list.
    allowed_file_roots_raw: str = ""

    # Stored as comma-separated string from env, parsed via property below
    cors_origins_raw: str = "http://localhost:5173,http://10.0.2.2:8000,ws://10.0.2.2:8000,https://dash-backend.fly.dev,*"

    database_url: str = "postgresql+asyncpg://dash:dash@localhost:5432/dash"
    redis_url: str = "redis://localhost:6379/0"

    # --- Optional Supabase cloud layer --------------------------------
    # These deliberately use the unprefixed names supplied by Supabase while
    # accepting DASH_-prefixed aliases for managed deployments.  The key is
    # kept as SecretStr so it is not exposed by accidental settings logging.
    supabase_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("SUPABASE_ENABLED", "DASH_SUPABASE_ENABLED"),
    )
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "DASH_SUPABASE_URL"),
    )
    supabase_publishable_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_PUBLISHABLE_KEY", "DASH_SUPABASE_PUBLISHABLE_KEY"
        ),
    )
    # One-way cloud sync remains off unless explicitly enabled.  A service-role
    # credential is optional at startup but required by the server-side worker;
    # it must never be sent to a DASH client.
    supabase_sync_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("SUPABASE_SYNC_ENABLED", "DASH_SUPABASE_SYNC_ENABLED"),
    )
    supabase_service_role_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY", "DASH_SUPABASE_SERVICE_ROLE_KEY"
        ),
    )
    # Maps DASH's current single local owner to a provisioned Supabase Auth
    # user.  This is an explicit UUID, never derived from a device token.
    supabase_sync_owner_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SYNC_OWNER_ID", "DASH_SUPABASE_SYNC_OWNER_ID"),
    )

    # --- AI Providers -------------------------------------------------

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-20250514"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:1b"  # DASH default: fast 1B model for responsive chat
    # Model used for RAG embeddings via Ollama (/api/embed). Falls back to
    # the legacy /api/embeddings endpoint when /api/embed is unavailable.
    ollama_embedding_model: str = "nomic-embed-text"
    # Thinking models (qwen3/deepseek-r1) spend tokens+time on hidden reasoning.
    ollama_thinking: bool = False  # Disabled for fast response; enable for qwen3 thinking
    # Ollama context window; must fit system prompt + memory + history.
    ollama_num_ctx: int = Field(default=4096, gt=128)
    # How long Ollama keeps the model in memory between requests. Some
    # machines set OLLAMA_KEEP_ALIVE=0 globally, which unloads the model
    # after EVERY request and adds a full disk-load (~15-20s) to each
    # message. DASH pins keep-alive per request so chat stays warm.
    ollama_keep_alive: str = "30m"
    # Optional legacy tool-protocol override ("custom_json"); empty = native.
    tool_protocol: str = ""
    # Tool schemas sent per LLM request. 100+ schemas overflow small local
    # context windows and Ollama truncates the system prompt silently.
    max_tools_per_request: int = Field(default=24, ge=1, le=200)

    ai_provider: str = "ollama"  # "ollama", "openai", "claude", "gemini"
    # Auto-detect: if cloud API keys are set and no Ollama is available,
    # the system falls back to the first available cloud provider.

    ai_model: str | None = None  # explicit model override; falls back to provider default

    jwt_secret_key: str | None = None
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)
    password_hash_iterations: int = Field(default=390_000, gt=0)

    # Tool execution timeout (seconds)
    tool_execution_timeout_seconds: int = Field(default=60, gt=0)

    # --- Obsidian vault integration ---
    obsidian_vault_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OBSIDIAN_VAULT_PATH", "DASH_OBSIDIAN_VAULT_PATH"),
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parse the raw comma-separated string into a list."""
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.env == "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
