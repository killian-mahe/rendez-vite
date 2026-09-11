"""Notification sender writing to the application log."""

from __future__ import annotations

import logging

from rendez_vite.domain.models import EmailMessage

logger = logging.getLogger(__name__)


class ConsoleNotifier:
    """Log the message instead of sending it, for local runs and dry runs."""

    def __init__(self, log: logging.Logger | None = None) -> None:
        """Build the notifier.

        Parameters
        ----------
        log
            Logger the messages are written to, overridden in tests.
        """
        self._log = log or logger

    async def send(self, message: EmailMessage) -> None:
        """Write the message to the log.

        Parameters
        ----------
        message
            Rendered message to display.
        """
        self._log.info(
            "Notification for %s: %s\n%s", message.recipient, message.subject, message.body
        )
