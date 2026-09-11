"""Activities: the only place where the workflow touches the outside world."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from temporalio import activity

from rendez_vite.config import Settings
from rendez_vite.domain.ports import AlertRenderer, NotificationSender, SlotProvider
from rendez_vite.infrastructure.registry import ComponentRegistry
from rendez_vite.orchestration.contracts import (
    FETCH_SLOTS_ACTIVITY,
    SEND_ALERT_ACTIVITY,
    FetchSlotsRequest,
    FetchSlotsResult,
    SendAlertRequest,
)


class AppointmentActivities:
    """Activity implementations, wired to the adapters through registries.

    The class receives its collaborators instead of importing them, so a test or a new
    deployment can swap a booking service or a notification channel without touching
    this code.
    """

    def __init__(
        self,
        providers: ComponentRegistry[SlotProvider],
        notifiers: ComponentRegistry[NotificationSender],
        renderer: AlertRenderer,
        settings: Settings,
    ) -> None:
        """Build the activity set.

        Parameters
        ----------
        providers
            Registry of the available booking services.
        notifiers
            Registry of the available notification channels.
        renderer
            Component turning matching slots into a message.
        settings
            Settings handed over to the adapter factories.
        """
        self._providers = providers
        self._notifiers = notifiers
        self._renderer = renderer
        self._settings = settings

    @activity.defn(name=FETCH_SLOTS_ACTIVITY)
    async def fetch_available_slots(self, request: FetchSlotsRequest) -> FetchSlotsResult:
        """Ask a booking service for the availabilities of the requested window.

        Parameters
        ----------
        request
            Provider name and lookup window.

        Returns
        -------
        FetchSlotsResult
            The slots the service currently offers.
        """
        provider = self._providers.create(request.provider, self._settings)
        slots = await provider.fetch_slots(request.query)
        activity.logger.info(
            "Provider %s returned %d slot(s) for %s",
            request.provider,
            len(slots),
            request.query.practitioner_id,
        )
        return FetchSlotsResult(slots=slots)

    @activity.defn(name=SEND_ALERT_ACTIVITY)
    async def send_slot_alert(self, request: SendAlertRequest) -> None:
        """Render the matching slots and deliver them to the user.

        Parameters
        ----------
        request
            Notifier name and slots to announce.
        """
        sender = self._notifiers.create(request.notifier, self._settings)
        await sender.send(self._renderer.render(request.alert))
        activity.logger.info(
            "Announced %d slot(s) to %s via %s",
            len(request.alert.slots),
            request.alert.recipient,
            request.notifier,
        )

    def as_list(self) -> list[Callable[..., Any]]:
        """Return the callables to register on a Temporal worker.

        Returns
        -------
        list of callable
            The bound activity methods.
        """
        return [self.fetch_available_slots, self.send_slot_alert]
