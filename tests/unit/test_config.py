from __future__ import annotations

from rendez_vite.config import Settings, get_settings


def test_settings_have_sensible_defaults():
    settings = Settings(_env_file=None)
    assert settings.temporal_address == "localhost:7233"
    assert settings.temporal_task_queue == "rendez-vite"
    assert settings.default_provider == "fake"


def test_settings_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("RENDEZ_VITE_TEMPORAL_ADDRESS", "temporal.internal:7233")
    monkeypatch.setenv("RENDEZ_VITE_SMTP_PASSWORD", "hunter2")
    settings = Settings(_env_file=None)
    assert settings.temporal_address == "temporal.internal:7233"
    assert settings.smtp_password is not None
    assert settings.smtp_password.get_secret_value() == "hunter2"


def test_secrets_are_not_printed():
    settings = Settings(smtp_password="hunter2")
    assert "hunter2" not in repr(settings)


def test_settings_are_loaded_once():
    assert get_settings() is get_settings()
