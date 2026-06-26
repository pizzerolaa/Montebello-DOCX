from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Montebello DOCX"))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_host: str = field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    app_port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./storage/app.db"))
    storage_root: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_ROOT", "./storage")))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "100")))
    max_files_per_project: int = field(default_factory=lambda: int(os.getenv("MAX_FILES_PER_PROJECT", "10")))
    allowed_docx_mime: str = field(
        default_factory=lambda: os.getenv(
            "ALLOWED_DOCX_MIME",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )
    auth_enabled: bool = field(default_factory=lambda: _as_bool(os.getenv("AUTH_ENABLED"), default=False))
    auth_username: str = field(default_factory=lambda: os.getenv("AUTH_USERNAME", ""))
    auth_password: str = field(default_factory=lambda: os.getenv("AUTH_PASSWORD", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "replace-this-in-production"))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate(self) -> None:
        if self.app_host not in {"127.0.0.1", "localhost", "::1"} and not self.auth_enabled:
            raise RuntimeError("Authentication must be enabled when binding outside localhost.")
        if self.auth_enabled and (not self.auth_username or not self.auth_password):
            raise RuntimeError("AUTH_USERNAME and AUTH_PASSWORD are required when auth is enabled.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
