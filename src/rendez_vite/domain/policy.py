"""Decision rules applied to each availability check."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from rendez_vite.domain.filters import SlotFilter
from rendez_vite.domain.models import AppointmentSlot

DEFAULT_TRACKED_SLOTS = 500


@dataclass(frozen=True)
class WatchDecision:
    """Outcome of a single availability check."""

    matches: list[AppointmentSlot]
    seen_slot_ids: list[str]
    should_stop: bool

    @property
    def should_notify(self) -> bool:
        """Tell whether the check produced something worth an e-mail."""
        return bool(self.matches)


class SlotWatchPolicy:
    """Turn a batch of availabilities into a notify-and-stop decision.

    The policy is pure: it never performs I/O, which makes it safe to run inside a
    Temporal workflow and trivial to unit test.
    """

    def __init__(
        self,
        slot_filter: SlotFilter,
        *,
        stop_on_first_match: bool = True,
        max_tracked_slots: int = DEFAULT_TRACKED_SLOTS,
    ) -> None:
        """Build the policy.

        Parameters
        ----------
        slot_filter
            Rule deciding whether a slot is acceptable.
        stop_on_first_match
            Whether the watch ends as soon as a matching slot has been announced.
        max_tracked_slots
            Upper bound on remembered slot identifiers, keeping the workflow state small.
        """
        self._filter = slot_filter
        self._stop_on_first_match = stop_on_first_match
        self._max_tracked_slots = max_tracked_slots

    def evaluate(
        self,
        slots: Iterable[AppointmentSlot],
        reference: datetime,
        seen_slot_ids: Sequence[str] = (),
    ) -> WatchDecision:
        """Select the slots worth announcing among the ones just fetched.

        Parameters
        ----------
        slots
            Availabilities returned by the booking service.
        reference
            Instant the relative rules are evaluated against, usually "now".
        seen_slot_ids
            Identifiers already announced during previous checks.

        Returns
        -------
        WatchDecision
            Newly matching slots sorted by start time, the updated memory of announced
            slots, and whether the watch should end.
        """
        known = set(seen_slot_ids)
        matches: dict[str, AppointmentSlot] = {}
        for slot in slots:
            if slot.slot_id in known or slot.slot_id in matches:
                continue
            if self._filter.matches(slot, reference):
                matches[slot.slot_id] = slot

        ordered = sorted(matches.values(), key=lambda slot: (slot.start, slot.slot_id))
        updated = [*seen_slot_ids, *(slot.slot_id for slot in ordered)]
        return WatchDecision(
            matches=ordered,
            seen_slot_ids=updated[-self._max_tracked_slots :],
            should_stop=bool(ordered) and self._stop_on_first_match,
        )
