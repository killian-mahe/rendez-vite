"""Entities and value objects describing appointments and search criteria."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import IntEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rendez_vite.domain.errors import ConfigurationError

_DEFAULT_TIMEZONE = "Europe/Paris"


class Weekday(IntEnum):
    """Day of the week, using the same numbering as :meth:`datetime.date.weekday`."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6

    @classmethod
    def parse(cls, value: str) -> Weekday:
        """Build a weekday from its English or French three-letter abbreviation.

        Parameters
        ----------
        value
            Abbreviation or full name, case insensitive (``mon``, ``lun``, ``monday``).

        Returns
        -------
        Weekday
            The matching weekday.

        Raises
        ------
        ConfigurationError
            If the abbreviation is unknown.
        """
        key = value.strip().lower()
        try:
            return _WEEKDAY_ALIASES[key]
        except KeyError:
            raise ConfigurationError(f"Unknown weekday: {value!r}") from None


_WEEKDAY_ALIASES: dict[str, Weekday] = {
    alias: day
    for day, aliases in {
        Weekday.MONDAY: ("mon", "monday", "lun", "lundi", "0"),
        Weekday.TUESDAY: ("tue", "tuesday", "mar", "mardi", "1"),
        Weekday.WEDNESDAY: ("wed", "wednesday", "mer", "mercredi", "2"),
        Weekday.THURSDAY: ("thu", "thursday", "jeu", "jeudi", "3"),
        Weekday.FRIDAY: ("fri", "friday", "ven", "vendredi", "4"),
        Weekday.SATURDAY: ("sat", "saturday", "sam", "samedi", "5"),
        Weekday.SUNDAY: ("sun", "sunday", "dim", "dimanche", "6"),
    }.items()
    for alias in aliases
}


def parse_clock_time(value: str) -> time:
    """Parse a ``HH:MM`` string into a :class:`datetime.time`.

    Parameters
    ----------
    value
        Wall-clock time such as ``"08:30"``.

    Returns
    -------
    datetime.time
        The parsed time of day.

    Raises
    ------
    ConfigurationError
        If the string does not follow the ``HH:MM`` format.
    """
    try:
        hours, minutes = (int(part) for part in value.split(":", maxsplit=1))
        return time(hour=hours, minute=minutes)
    except ValueError:
        raise ConfigurationError(f"Invalid HH:MM time: {value!r}") from None


def resolve_timezone(name: str) -> ZoneInfo:
    """Resolve an IANA timezone name.

    Parameters
    ----------
    name
        IANA identifier such as ``"Europe/Paris"``.

    Returns
    -------
    zoneinfo.ZoneInfo
        The resolved timezone.

    Raises
    ------
    ConfigurationError
        If the identifier is unknown on this system.
    """
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigurationError(f"Unknown timezone: {name!r}") from None


@dataclass(frozen=True)
class TimeOfDayRange:
    """Inclusive wall-clock window a slot must start within."""

    start: str = "00:00"
    end: str = "23:59"

    def __post_init__(self) -> None:
        """Validate that the window is well formed.

        Raises
        ------
        ConfigurationError
            If a bound is malformed or if the window ends before it starts.
        """
        if self.start_time > self.end_time:
            raise ConfigurationError(f"Time range starts after it ends: {self.start}-{self.end}")

    @property
    def start_time(self) -> time:
        """Return the lower bound as a :class:`datetime.time`."""
        return parse_clock_time(self.start)

    @property
    def end_time(self) -> time:
        """Return the upper bound as a :class:`datetime.time`."""
        return parse_clock_time(self.end)

    def contains(self, moment: time) -> bool:
        """Tell whether a wall-clock time falls inside the window.

        Parameters
        ----------
        moment
            Time of day to test.

        Returns
        -------
        bool
            ``True`` when the time is within the inclusive bounds.
        """
        return self.start_time <= moment <= self.end_time


@dataclass(frozen=True)
class AppointmentSlot:
    """A bookable appointment offered by a practitioner."""

    slot_id: str
    practitioner_id: str
    reason: str
    start: datetime
    end: datetime
    location: str = ""
    booking_url: str = ""

    def __post_init__(self) -> None:
        """Validate the slot boundaries.

        Raises
        ------
        ConfigurationError
            If a datetime is naive or if the slot does not end after it starts.
        """
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ConfigurationError(f"Slot {self.slot_id!r} must use timezone-aware datetimes")
        if self.end <= self.start:
            raise ConfigurationError(f"Slot {self.slot_id!r} ends before it starts")

    def local_start(self, timezone: str) -> datetime:
        """Return the start instant expressed in the given timezone.

        Parameters
        ----------
        timezone
            IANA timezone identifier.

        Returns
        -------
        datetime.datetime
            The localised start of the slot.
        """
        return self.start.astimezone(resolve_timezone(timezone))


@dataclass(frozen=True)
class SearchCriteria:
    """Everything the user is looking for in an appointment."""

    practitioner_id: str
    reason: str
    timezone: str = _DEFAULT_TIMEZONE
    horizon_days: int = 30
    min_lead_time_hours: int = 0
    weekdays: list[Weekday] = field(default_factory=lambda: list(Weekday))
    time_range: TimeOfDayRange = field(default_factory=TimeOfDayRange)

    def __post_init__(self) -> None:
        """Validate the criteria as a whole.

        Raises
        ------
        ConfigurationError
            If an identifier is empty, a duration is out of range or no weekday is selected.
        """
        if not self.practitioner_id.strip():
            raise ConfigurationError("A practitioner identifier is required")
        if not self.reason.strip():
            raise ConfigurationError("A consultation reason is required")
        if self.horizon_days < 1:
            raise ConfigurationError("The search horizon must cover at least one day")
        if self.min_lead_time_hours < 0:
            raise ConfigurationError("The minimum lead time cannot be negative")
        if not self.weekdays:
            raise ConfigurationError("At least one weekday must be selected")
        resolve_timezone(self.timezone)

    def window(self, reference: datetime) -> tuple[datetime, datetime]:
        """Compute the absolute search window to ask a booking service for.

        Parameters
        ----------
        reference
            Instant the window is computed from, usually "now".

        Returns
        -------
        tuple of datetime.datetime
            Inclusive start and exclusive end of the window.
        """
        return (
            reference + timedelta(hours=self.min_lead_time_hours),
            reference + timedelta(days=self.horizon_days),
        )


@dataclass(frozen=True)
class SlotQuery:
    """Request sent to a booking service to list availabilities."""

    practitioner_id: str
    reason: str
    window_start: datetime
    window_end: datetime

    @classmethod
    def from_criteria(cls, criteria: SearchCriteria, reference: datetime) -> SlotQuery:
        """Derive a query from user criteria.

        Parameters
        ----------
        criteria
            The user's search criteria.
        reference
            Instant the search window is computed from.

        Returns
        -------
        SlotQuery
            The query to hand over to a slot provider.
        """
        window_start, window_end = criteria.window(reference)
        return cls(
            practitioner_id=criteria.practitioner_id,
            reason=criteria.reason,
            window_start=window_start,
            window_end=window_end,
        )


@dataclass(frozen=True)
class EmailMessage:
    """A rendered message ready to be handed over to a notification sender."""

    recipient: str
    subject: str
    body: str


@dataclass(frozen=True)
class SlotAlert:
    """The matching slots to announce to a user."""

    recipient: str
    criteria: SearchCriteria
    slots: list[AppointmentSlot]
