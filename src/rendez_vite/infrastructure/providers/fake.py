"""Deterministic in-memory provider, used for demos and tests."""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timedelta

from rendez_vite.domain.models import AppointmentSlot, SlotQuery, resolve_timezone

_SLOT_MINUTES = 30
_OPENING_HOUR = 8
_CLOSING_HOUR = 18


class FakeSlotProvider:
    """Generate pseudo-random but reproducible availabilities.

    The same query always yields the same slots, which makes the provider usable both
    as a local playground and as a fixture in the test suite.
    """

    def __init__(
        self,
        *,
        seed: str = "rendez-vite",
        release_rate: float = 0.05,
        timezone: str = "Europe/Paris",
    ) -> None:
        """Build the provider.

        Parameters
        ----------
        seed
            Salt making the generated calendar stable across runs.
        release_rate
            Share of the practice's agenda that is free, between 0 and 1.
        timezone
            Timezone the practice's opening hours are expressed in.
        """
        self._seed = seed
        self._release_rate = release_rate
        self._timezone = timezone

    async def fetch_slots(self, query: SlotQuery) -> list[AppointmentSlot]:
        """Return the generated availabilities inside the query window.

        Parameters
        ----------
        query
            Practitioner, reason and time window to look up.

        Returns
        -------
        list of AppointmentSlot
            Slots offered during the practice's opening hours.
        """
        tzinfo = resolve_timezone(self._timezone)
        day = query.window_start.astimezone(tzinfo).date()
        last_day = query.window_end.astimezone(tzinfo).date()
        slots: list[AppointmentSlot] = []
        while day <= last_day:
            opening = datetime.combine(day, time(hour=_OPENING_HOUR), tzinfo=tzinfo)
            offsets = range(0, (_CLOSING_HOUR - _OPENING_HOUR) * 60, _SLOT_MINUTES)
            for offset in offsets:
                start = opening + timedelta(minutes=offset)
                if not query.window_start <= start < query.window_end:
                    continue
                if self._is_free(query, start):
                    slots.append(self._build_slot(query, start))
            day += timedelta(days=1)
        return slots

    def _is_free(self, query: SlotQuery, start: datetime) -> bool:
        """Decide whether a given time slot is free.

        Parameters
        ----------
        query
            Query the calendar is generated for.
        start
            Start of the candidate slot.

        Returns
        -------
        bool
            ``True`` when the slot is available.
        """
        material = f"{self._seed}|{query.practitioner_id}|{query.reason}|{start.isoformat()}"
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") / 2**32 < self._release_rate

    def _build_slot(self, query: SlotQuery, start: datetime) -> AppointmentSlot:
        """Build the slot exposed to the caller.

        Parameters
        ----------
        query
            Query the calendar is generated for.
        start
            Start of the slot.

        Returns
        -------
        AppointmentSlot
            The generated appointment.
        """
        return AppointmentSlot(
            slot_id=f"{query.practitioner_id}:{start:%Y%m%dT%H%M%z}",
            practitioner_id=query.practitioner_id,
            reason=query.reason,
            start=start,
            end=start + timedelta(minutes=_SLOT_MINUTES),
            location="Cabinet de démonstration",
            booking_url="https://example.invalid/booking",
        )
