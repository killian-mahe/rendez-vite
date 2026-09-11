from __future__ import annotations

import pytest

from rendez_vite.config import Settings
from rendez_vite.domain.errors import UnknownComponentError
from rendez_vite.infrastructure.notifiers import build_notifier_registry
from rendez_vite.infrastructure.notifiers.console import ConsoleNotifier
from rendez_vite.infrastructure.notifiers.smtp import SmtpEmailNotifier
from rendez_vite.infrastructure.providers import build_provider_registry
from rendez_vite.infrastructure.providers.fake import FakeSlotProvider
from rendez_vite.infrastructure.providers.http import HttpSlotProvider
from rendez_vite.infrastructure.registry import ComponentRegistry


def test_registry_builds_the_registered_component(settings):
    registry: ComponentRegistry[str] = ComponentRegistry("thing")
    registry.register("Alpha", lambda _: "built")
    assert registry.create("alpha", settings) == "built"
    assert registry.names == ["alpha"]


def test_registry_reports_unknown_names(settings):
    registry: ComponentRegistry[str] = ComponentRegistry("thing")
    registry.register("alpha", lambda _: "built")
    with pytest.raises(UnknownComponentError, match="registered: alpha"):
        registry.create("beta", settings)


def test_registry_can_override_a_factory(settings):
    registry: ComponentRegistry[str] = ComponentRegistry("thing")
    registry.register("alpha", lambda _: "first")
    registry.register("alpha", lambda _: "second")
    assert registry.create("alpha", settings) == "second"


def test_builtin_providers(settings):
    registry = build_provider_registry()
    assert registry.names == ["fake", "http"]
    assert isinstance(registry.create("fake", settings), FakeSlotProvider)
    assert isinstance(registry.create("http", settings), HttpSlotProvider)


def test_builtin_notifiers(settings):
    registry = build_notifier_registry()
    assert registry.names == ["console", "smtp"]
    assert isinstance(registry.create("console", settings), ConsoleNotifier)
    assert isinstance(registry.create("smtp", settings), SmtpEmailNotifier)


def test_adapters_read_their_secrets():
    secret_settings = Settings(booking_api_token="token", smtp_password="hunter2")
    assert isinstance(build_provider_registry().create("http", secret_settings), HttpSlotProvider)
    assert isinstance(build_notifier_registry().create("smtp", secret_settings), SmtpEmailNotifier)
