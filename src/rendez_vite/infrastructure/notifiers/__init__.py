"""Notification senders and their registry."""

from __future__ import annotations

from rendez_vite.config import Settings
from rendez_vite.domain.ports import NotificationSender
from rendez_vite.infrastructure.notifiers.console import ConsoleNotifier
from rendez_vite.infrastructure.notifiers.smtp import SmtpEmailNotifier
from rendez_vite.infrastructure.registry import ComponentRegistry

__all__ = ["ConsoleNotifier", "SmtpEmailNotifier", "build_notifier_registry"]


def _build_console(settings: Settings) -> NotificationSender:  # noqa: ARG001
    """Build the logging notifier.

    Parameters
    ----------
    settings
        Application settings, unused by this adapter.

    Returns
    -------
    NotificationSender
        The configured notifier.
    """
    return ConsoleNotifier()


def _build_smtp(settings: Settings) -> NotificationSender:
    """Build the SMTP notifier from the settings.

    Parameters
    ----------
    settings
        Application settings.

    Returns
    -------
    NotificationSender
        The configured notifier.
    """
    return SmtpEmailNotifier(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_sender,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
        use_tls=settings.smtp_use_tls,
        timeout=settings.smtp_timeout_seconds,
    )


def build_notifier_registry() -> ComponentRegistry[NotificationSender]:
    """Return a registry holding the built-in notification senders.

    Returns
    -------
    ComponentRegistry
        Registry exposing the ``console`` and ``smtp`` senders.
    """
    registry: ComponentRegistry[NotificationSender] = ComponentRegistry("notifier")
    registry.register("console", _build_console)
    registry.register("smtp", _build_smtp)
    return registry
