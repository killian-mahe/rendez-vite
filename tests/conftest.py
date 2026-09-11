from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from rendez_vite.config import Settings
from rendez_vite.domain.models import AppointmentSlot, SearchCriteria, TimeOfDayRange, Weekday

PARIS = ZoneInfo("Europe/Paris")

SlotFactory = Callable[..., AppointmentSlot]


@pytest.fixture
def reference() -> datetime:
    """Monday 2 March 2026, 09:00 UTC (10:00 in Paris)."""
    return datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


@pytest.fixture
def make_slot() -> SlotFactory:
    def factory(
        start: datetime,
        *,
        slot_id: str | None = None,
        practitioner_id: str = "dr-house",
        reason: str = "consultation",
        duration_minutes: int = 30,
        location: str = "",
        booking_url: str = "",
    ) -> AppointmentSlot:
        return AppointmentSlot(
            slot_id=slot_id or f"{practitioner_id}:{start.isoformat()}",
            practitioner_id=practitioner_id,
            reason=reason,
            start=start,
            end=start + timedelta(minutes=duration_minutes),
            location=location,
            booking_url=booking_url,
        )

    return factory


@pytest.fixture
def criteria() -> SearchCriteria:
    return SearchCriteria(
        practitioner_id="dr-house",
        reason="consultation",
        timezone="Europe/Paris",
        horizon_days=30,
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY],
        time_range=TimeOfDayRange(start="08:00", end="12:00"),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        smtp_host="smtp.test",
        smtp_sender="bot@test",
        booking_api_base_url="https://booking.test/api",
        fake_release_rate=0.5,
    )
