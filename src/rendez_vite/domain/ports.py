"""Ports the business core depends on, implemented by the infrastructure layer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from rendez_vite.domain.models import AppointmentSlot, EmailMessage, SlotAlert, SlotQuery


@runtime_checkable
class SlotProvider(Protocol):
    """Read availabilities from a booking service."""

    async def fetch_slots(self, query: SlotQuery) -> list[AppointmentSlot]:
        """Return the slots the service currently offers for the query window.

        Parameters
        ----------
        query
            Practitioner, reason and time window to look up.

        Returns
        -------
        list of AppointmentSlot
            Available slots, in no particular order.

        Raises
        ------
        SlotProviderError
            If the booking service cannot be reached or returns unusable data.
        """
        ...


@runtime_checkable
class NotificationSender(Protocol):
    """Deliver a rendered message to its recipient."""

    async def send(self, message: EmailMessage) -> None:
        """Deliver the message.

        Parameters
        ----------
        message
            Rendered subject and body along with its recipient.

        Raises
        ------
        NotificationError
            If the message cannot be delivered.
        """
        ...


@runtime_checkable
class AlertRenderer(Protocol):
    """Turn matching slots into a message a human can read."""

    def render(self, alert: SlotAlert) -> EmailMessage:
        """Render the alert.

        Parameters
        ----------
        alert
            Recipient, criteria and matching slots.

        Returns
        -------
        EmailMessage
            The message to send.
        """
        ...
