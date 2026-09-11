"""Application settings, read from the environment or a ``.env`` file."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration of the worker, the adapters and the CLI."""

    model_config = SettingsConfigDict(
        env_prefix="RENDEZ_VITE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "rendez-vite"
    temporal_tls: bool = False
    temporal_api_key: SecretStr | None = None

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True
    smtp_sender: str = "rendez-vite@localhost"
    smtp_timeout_seconds: float = 10.0

    booking_api_base_url: str = "https://example.invalid/api"
    booking_api_token: SecretStr | None = None
    booking_api_timeout_seconds: float = 10.0

    fake_seed: str = "rendez-vite"
    fake_release_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    fake_timezone: str = "Europe/Paris"

    default_provider: str = "fake"
    default_notifier: str = "console"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once.

    Returns
    -------
    Settings
        The cached settings instance.
    """
    return Settings()
