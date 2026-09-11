"""Slot providers and their registry."""

from __future__ import annotations

from rendez_vite.config import Settings
from rendez_vite.domain.ports import SlotProvider
from rendez_vite.infrastructure.providers.fake import FakeSlotProvider
from rendez_vite.infrastructure.providers.http import HttpSlotProvider
from rendez_vite.infrastructure.registry import ComponentRegistry

__all__ = ["FakeSlotProvider", "HttpSlotProvider", "build_provider_registry"]


def _build_fake(settings: Settings) -> SlotProvider:
    """Build the deterministic provider from the settings.

    Parameters
    ----------
    settings
        Application settings.

    Returns
    -------
    SlotProvider
        The configured provider.
    """
    return FakeSlotProvider(
        seed=settings.fake_seed,
        release_rate=settings.fake_release_rate,
        timezone=settings.fake_timezone,
    )


def _build_http(settings: Settings) -> SlotProvider:
    """Build the HTTP provider from the settings.

    Parameters
    ----------
    settings
        Application settings.

    Returns
    -------
    SlotProvider
        The configured provider.
    """
    token = settings.booking_api_token.get_secret_value() if settings.booking_api_token else None
    return HttpSlotProvider(
        settings.booking_api_base_url,
        token=token,
        timeout=settings.booking_api_timeout_seconds,
    )


def build_provider_registry() -> ComponentRegistry[SlotProvider]:
    """Return a registry holding the built-in slot providers.

    Returns
    -------
    ComponentRegistry
        Registry exposing the ``fake`` and ``http`` providers.
    """
    registry: ComponentRegistry[SlotProvider] = ComponentRegistry("slot provider")
    registry.register("fake", _build_fake)
    registry.register("http", _build_http)
    return registry
