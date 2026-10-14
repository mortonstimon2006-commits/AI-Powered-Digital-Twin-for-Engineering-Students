"""Typed, validated application configuration.

Values come from environment variables (or the repository-level `.env` in development).
Unsafe combinations are rejected at startup for staging/production rather than silently
accepted, so a misconfigured deployment fails closed.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Environment(StrEnum):
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


class EmailBackend(StrEnum):
    file = "file"
    smtp = "smtp"
    none = "none"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    twinpath_env: Environment = Environment.development
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")

    # --- database ---
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # --- security ---
    secret_key: SecretStr
    field_encryption_key: SecretStr
    allowed_origins: str = "http://localhost:5173"
    cookie_secure: bool = True
    session_absolute_hours: int = Field(default=168, ge=1, le=24 * 30)
    session_idle_hours: int = Field(default=12, ge=1, le=24 * 7)
    enable_api_docs: bool | None = None
    trust_proxy_headers: bool = False

    # --- email ---
    email_backend: EmailBackend = EmailBackend.file
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "TwinPath AI <no-reply@example.invalid>"
    require_email_verification: bool = False
    public_app_url: str = "http://localhost:5173"

    # --- local LLM ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_num_ctx: int = Field(default=4096, ge=1024, le=32768)
    ollama_timeout_seconds: int = Field(default=180, ge=10, le=900)
    mentor_max_concurrent: int = Field(default=1, ge=1, le=8)
    mentor_max_queue: int = Field(default=4, ge=0, le=64)
    mentor_max_question_chars: int = Field(default=2000, ge=100, le=8000)

    # --- storage ---
    data_dir: Path = BACKEND_DIR / "var"
    max_upload_mb: int = Field(default=5, ge=1, le=25)
    document_retention_days: int = Field(default=180, ge=1, le=3650)
    chat_retention_days: int = Field(default=180, ge=1, le=3650)

    # --- ml ---
    model_artifact_dir: Path = BACKEND_DIR / "artifacts" / "models"

    @field_validator("data_dir", "model_artifact_dir", mode="after")
    @classmethod
    def _resolve_relative(cls, v: Path) -> Path:
        return v if v.is_absolute() else (BACKEND_DIR / v).resolve()

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.twinpath_env in (Environment.staging, Environment.production)

    @property
    def api_docs_enabled(self) -> bool:
        if self.enable_api_docs is not None:
            return self.enable_api_docs
        return not self.is_production_like

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix pins the cookie to this exact host, path=/ and Secure.
        return "__Host-tp_session" if self.cookie_secure else "tp_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-tp_csrf" if self.cookie_secure else "tp_csrf"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @model_validator(mode="after")
    def _fail_closed_in_production(self) -> Settings:
        if len(self.secret_key.get_secret_value()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if self.is_production_like:
            problems: list[str] = []
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true")
            if any(not o.startswith("https://") for o in self.origins):
                problems.append("ALLOWED_ORIGINS must all be https://")
            if self.email_backend == EmailBackend.file:
                problems.append("EMAIL_BACKEND=file is development-only")
            if self.require_email_verification and self.email_backend != EmailBackend.smtp:
                problems.append("REQUIRE_EMAIL_VERIFICATION needs EMAIL_BACKEND=smtp")
            if "change-me" in self.database_url.get_secret_value():
                problems.append("DATABASE_URL still contains a placeholder password")
            if problems:
                raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
