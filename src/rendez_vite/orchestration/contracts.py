"""Names and payloads shared between the workflow, the activities and the clients.

Keeping them in a dedicated module lets the workflow depend on the activity *contract*
only, never on the adapters implementing it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from rendez_vite.domain.errors import ConfigurationError
from rendez_vite.domain.models import AppointmentSlot, SearchCriteria, SlotAlert, SlotQuery

WATCH_WORKFLOW = "RendezViteWatch"
FETCH_SLOTS_ACTIVITY = "fetch_available_slots"
SEND_ALERT_ACTIVITY = "send_slot_alert"

STATUS_QUERY = "status"
UPDATE_CRITERIA_SIGNAL = "update_criteria"
PAUSE_SIGNAL = "pause"
RESUME_SIGNAL = "resume"
STOP_SIGNAL = "stop"

MIN_CHECK_INTERVAL_SECONDS = 60
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class FetchSlotsRequest:
    """Input of the availability lookup activity."""

    provider: str
    query: SlotQuery


@dataclass(frozen=True)
class FetchSlotsResult:
    """Output of the availability lookup activity."""

    slots: list[AppointmentSlot]


@dataclass(frozen=True)
class SendAlertRequest:
    """Input of the notification activity."""

    notifier: str
    alert: SlotAlert


@dataclass(frozen=True)
class WatchOptions:
    """How the watch behaves over time."""

    check_interval_seconds: int = 900
    stop_on_first_match: bool = True
    max_checks: int | None = None
    checks_before_continue_as_new: int = 200
    provider: str = "fake"
    notifier: str = "console"

    def __post_init__(self) -> None:
        """Validate the watch settings.

        Raises
        ------
        ConfigurationError
            If the polling interval is too aggressive or a bound is not positive.
        """
        if self.check_interval_seconds < MIN_CHECK_INTERVAL_SECONDS:
            raise ConfigurationError(
                f"The check interval must be at least {MIN_CHECK_INTERVAL_SECONDS}s "
                "to stay fair to the booking service"
            )
        if self.max_checks is not None and self.max_checks < 1:
            raise ConfigurationError("The maximum number of checks must be positive")
        if self.checks_before_continue_as_new < 1:
            raise ConfigurationError("The history rollover threshold must be positive")


@dataclass
class WatchState:
    """Mutable progress of a watch, carried over across history rollovers."""

    checks_done: int = 0
    notifications_sent: int = 0
    seen_slot_ids: list[str] = field(default_factory=list)

    def copy(self) -> WatchState:
        """Return an independent copy of the state.

        Returns
        -------
        WatchState
            A copy that can be mutated without touching the original.
        """
        return WatchState(
            checks_done=self.checks_done,
            notifications_sent=self.notifications_sent,
            seen_slot_ids=list(self.seen_slot_ids),
        )


@dataclass(frozen=True)
class WatchRequest:
    """Everything the watch workflow needs to start or resume."""

    criteria: SearchCriteria
    recipient_email: str
    options: WatchOptions = field(default_factory=WatchOptions)
    state: WatchState = field(default_factory=WatchState)

    def __post_init__(self) -> None:
        """Validate the recipient address.

        Raises
        ------
        ConfigurationError
            If the e-mail address is not plausible.
        """
        if not _EMAIL_PATTERN.match(self.recipient_email):
            raise ConfigurationError(f"Invalid recipient e-mail: {self.recipient_email!r}")


@dataclass(frozen=True)
class WatchStatus:
    """Snapshot of a running watch, returned by the status query."""

    criteria: SearchCriteria | None
    checks_done: int
    notifications_sent: int
    paused: bool
    stop_requested: bool
    last_check: datetime | None
    last_match_count: int
    last_error: str | None = None


@dataclass(frozen=True)
class WatchSummary:
    """Final result of a watch."""

    checks_done: int
    notifications_sent: int
    stop_reason: str
    matched_slots: list[AppointmentSlot] = field(default_factory=list)
