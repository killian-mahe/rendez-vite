"""Composable predicates turning search criteria into slot selection rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta

from rendez_vite.domain.models import AppointmentSlot, SearchCriteria, TimeOfDayRange, Weekday


class SlotFilter(ABC):
    """A single acceptance rule applied to a candidate slot."""

    @abstractmethod
    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:
        """Tell whether the slot satisfies the rule.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Instant the relative rules are evaluated against, usually "now".

        Returns
        -------
        bool
            ``True`` when the slot is acceptable.
        """


class AllOfFilter(SlotFilter):
    """Conjunction of filters: every child rule must accept the slot."""

    def __init__(self, filters: Iterable[SlotFilter]) -> None:
        """Build the conjunction.

        Parameters
        ----------
        filters
            Child rules, all of which must accept a slot.
        """
        self._filters: tuple[SlotFilter, ...] = tuple(filters)

    @property
    def filters(self) -> tuple[SlotFilter, ...]:
        """Return the child rules."""
        return self._filters

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:
        """Tell whether every child rule accepts the slot.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Instant the relative rules are evaluated against.

        Returns
        -------
        bool
            ``True`` when all child rules accept the slot.
        """
        return all(child.matches(slot, reference) for child in self._filters)


class PractitionerFilter(SlotFilter):
    """Keep the slots of one practitioner."""

    def __init__(self, practitioner_id: str) -> None:
        """Build the rule.

        Parameters
        ----------
        practitioner_id
            Identifier the slot must be attached to.
        """
        self._practitioner_id = practitioner_id

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:  # noqa: ARG002
        """Tell whether the slot belongs to the expected practitioner.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Unused, kept for interface compatibility.

        Returns
        -------
        bool
            ``True`` when the practitioner matches.
        """
        return slot.practitioner_id == self._practitioner_id


class ReasonFilter(SlotFilter):
    """Keep the slots matching a consultation reason, ignoring case and spacing."""

    def __init__(self, reason: str) -> None:
        """Build the rule.

        Parameters
        ----------
        reason
            Consultation reason to look for.
        """
        self._reason = self._normalise(reason)

    @staticmethod
    def _normalise(value: str) -> str:
        """Lower-case a reason and collapse its whitespace.

        Parameters
        ----------
        value
            Raw reason.

        Returns
        -------
        str
            Comparable form of the reason.
        """
        return " ".join(value.lower().split())

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:  # noqa: ARG002
        """Tell whether the slot is offered for the expected reason.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Unused, kept for interface compatibility.

        Returns
        -------
        bool
            ``True`` when the reasons are equivalent.
        """
        return self._normalise(slot.reason) == self._reason


class HorizonFilter(SlotFilter):
    """Reject slots starting beyond the search horizon."""

    def __init__(self, horizon_days: int) -> None:
        """Build the rule.

        Parameters
        ----------
        horizon_days
            Number of days the user is willing to wait.
        """
        self._horizon = timedelta(days=horizon_days)

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:
        """Tell whether the slot starts within the horizon.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Instant the horizon is measured from.

        Returns
        -------
        bool
            ``True`` when the slot starts before the horizon ends.
        """
        return slot.start <= reference + self._horizon


class LeadTimeFilter(SlotFilter):
    """Reject slots happening too soon to be reached in time."""

    def __init__(self, min_lead_time_hours: int) -> None:
        """Build the rule.

        Parameters
        ----------
        min_lead_time_hours
            Minimum delay between now and the appointment.
        """
        self._lead_time = timedelta(hours=min_lead_time_hours)

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:
        """Tell whether the slot leaves enough lead time.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Instant the lead time is measured from.

        Returns
        -------
        bool
            ``True`` when the slot is far enough in the future.
        """
        return slot.start >= reference + self._lead_time


class WeekdayFilter(SlotFilter):
    """Keep the slots falling on one of the selected weekdays."""

    def __init__(self, weekdays: Sequence[Weekday], timezone: str) -> None:
        """Build the rule.

        Parameters
        ----------
        weekdays
            Accepted days of the week.
        timezone
            Timezone the days are evaluated in, so that the user's calendar wins.
        """
        self._weekdays = frozenset(weekdays)
        self._timezone = timezone

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:  # noqa: ARG002
        """Tell whether the slot falls on an accepted weekday.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Unused, kept for interface compatibility.

        Returns
        -------
        bool
            ``True`` when the local weekday is accepted.
        """
        return Weekday(slot.local_start(self._timezone).weekday()) in self._weekdays


class TimeOfDayFilter(SlotFilter):
    """Keep the slots starting inside the preferred wall-clock window."""

    def __init__(self, time_range: TimeOfDayRange, timezone: str) -> None:
        """Build the rule.

        Parameters
        ----------
        time_range
            Accepted wall-clock window.
        timezone
            Timezone the window is evaluated in.
        """
        self._time_range = time_range
        self._timezone = timezone

    def matches(self, slot: AppointmentSlot, reference: datetime) -> bool:  # noqa: ARG002
        """Tell whether the slot starts inside the preferred window.

        Parameters
        ----------
        slot
            Candidate appointment.
        reference
            Unused, kept for interface compatibility.

        Returns
        -------
        bool
            ``True`` when the local start time is within the window.
        """
        return self._time_range.contains(slot.local_start(self._timezone).time())


FilterFactory = Callable[[SearchCriteria], SlotFilter]

FILTER_FACTORIES: tuple[FilterFactory, ...] = (
    lambda criteria: PractitionerFilter(criteria.practitioner_id),
    lambda criteria: ReasonFilter(criteria.reason),
    lambda criteria: LeadTimeFilter(criteria.min_lead_time_hours),
    lambda criteria: HorizonFilter(criteria.horizon_days),
    lambda criteria: WeekdayFilter(criteria.weekdays, criteria.timezone),
    lambda criteria: TimeOfDayFilter(criteria.time_range, criteria.timezone),
)


def build_slot_filter(
    criteria: SearchCriteria,
    factories: Iterable[FilterFactory] = FILTER_FACTORIES,
) -> SlotFilter:
    """Assemble the selection rule matching a set of criteria.

    Parameters
    ----------
    criteria
        The user's search criteria.
    factories
        Rule builders to apply; extending the criteria means adding a factory here
        rather than editing the existing rules.

    Returns
    -------
    SlotFilter
        A conjunction of every produced rule.
    """
    return AllOfFilter(factory(criteria) for factory in factories)
