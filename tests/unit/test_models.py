from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from rendez_vite.domain.errors import ConfigurationError
from rendez_vite.domain.models import (
    AppointmentSlot,
    SearchCriteria,
    SlotQuery,
    TimeOfDayRange,
    Weekday,
    parse_clock_time,
    resolve_timezone,
)
from tests.conftest import PARIS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mon", Weekday.MONDAY),
        ("LUNDI", Weekday.MONDAY),
        (" sam ", Weekday.SATURDAY),
        ("6", Weekday.SUNDAY),
        ("Wednesday", Weekday.WEDNESDAY),
    ],
)
def test_weekday_parse_accepts_aliases(value, expected):
    assert Weekday.parse(value) is expected


def test_weekday_parse_rejects_unknown_day():
    with pytest.raises(ConfigurationError, match="Unknown weekday"):
        Weekday.parse("funday")


def test_parse_clock_time():
    assert parse_clock_time("08:30") == time(8, 30)


@pytest.mark.parametrize("value", ["8h30", "08", "aa:bb", "08:xx"])
def test_parse_clock_time_rejects_malformed_values(value):
    with pytest.raises(ConfigurationError, match="Invalid HH:MM"):
        parse_clock_time(value)


def test_resolve_timezone_rejects_unknown_zone():
    with pytest.raises(ConfigurationError, match="Unknown timezone"):
        resolve_timezone("Mars/Olympus_Mons")


def test_time_range_contains_bounds():
    window = TimeOfDayRange(start="08:00", end="12:00")
    assert window.contains(time(8, 0))
    assert window.contains(time(12, 0))
    assert not window.contains(time(12, 1))
    assert not window.contains(time(7, 59))


def test_time_range_rejects_inverted_window():
    with pytest.raises(ConfigurationError, match="starts after it ends"):
        TimeOfDayRange(start="18:00", end="09:00")


def test_slot_requires_aware_datetimes():
    with pytest.raises(ConfigurationError, match="timezone-aware"):
        AppointmentSlot(
            slot_id="s1",
            practitioner_id="p",
            reason="r",
            start=datetime(2026, 3, 2, 9, 0),
            end=datetime(2026, 3, 2, 9, 30, tzinfo=UTC),
        )


def test_slot_requires_positive_duration(reference):
    with pytest.raises(ConfigurationError, match="ends before it starts"):
        AppointmentSlot(
            slot_id="s1",
            practitioner_id="p",
            reason="r",
            start=reference,
            end=reference,
        )


def test_slot_local_start_uses_target_timezone(make_slot, reference):
    slot = make_slot(reference)
    local = slot.local_start("Europe/Paris")
    assert local.hour == 10
    assert local.tzinfo == PARIS


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("practitioner_id", "  ", "practitioner identifier"),
        ("reason", "", "consultation reason"),
        ("horizon_days", 0, "at least one day"),
        ("min_lead_time_hours", -1, "cannot be negative"),
        ("weekdays", [], "At least one weekday"),
        ("timezone", "Nowhere/Land", "Unknown timezone"),
    ],
)
def test_criteria_validation(field, value, message):
    kwargs = {"practitioner_id": "dr-house", "reason": "consultation", field: value}
    with pytest.raises(ConfigurationError, match=message):
        SearchCriteria(**kwargs)


def test_criteria_defaults_to_every_weekday():
    assert SearchCriteria(practitioner_id="p", reason="r").weekdays == list(Weekday)


def test_criteria_window(reference):
    criteria = SearchCriteria(
        practitioner_id="p", reason="r", horizon_days=10, min_lead_time_hours=6
    )
    start, end = criteria.window(reference)
    assert start == reference + timedelta(hours=6)
    assert end == reference + timedelta(days=10)


def test_slot_query_from_criteria(criteria, reference):
    query = SlotQuery.from_criteria(criteria, reference)
    assert query.practitioner_id == criteria.practitioner_id
    assert query.reason == criteria.reason
    assert query.window_start == reference
    assert query.window_end == reference + timedelta(days=30)
