from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from rendez_vite.domain.filters import (
    AllOfFilter,
    HorizonFilter,
    LeadTimeFilter,
    PractitionerFilter,
    ReasonFilter,
    SlotFilter,
    TimeOfDayFilter,
    WeekdayFilter,
    build_slot_filter,
)
from rendez_vite.domain.models import TimeOfDayRange, Weekday
from tests.conftest import PARIS


def test_practitioner_filter(make_slot, reference):
    slot = make_slot(reference, practitioner_id="dr-house")
    assert PractitionerFilter("dr-house").matches(slot, reference)
    assert not PractitionerFilter("dr-wilson").matches(slot, reference)


@pytest.mark.parametrize(
    ("wanted", "offered", "expected"),
    [
        ("consultation", "Consultation", True),
        ("premiere  visite", "Première visite", False),
        ("suivi annuel", " Suivi   Annuel ", True),
        ("consultation", "téléconsultation", False),
    ],
)
def test_reason_filter_normalises_case_and_spacing(make_slot, reference, wanted, offered, expected):
    slot = make_slot(reference, reason=offered)
    assert ReasonFilter(wanted).matches(slot, reference) is expected


def test_horizon_filter(make_slot, reference):
    rule = HorizonFilter(horizon_days=7)
    assert rule.matches(make_slot(reference + timedelta(days=7)), reference)
    assert not rule.matches(make_slot(reference + timedelta(days=7, seconds=1)), reference)


def test_lead_time_filter(make_slot, reference):
    rule = LeadTimeFilter(min_lead_time_hours=24)
    assert rule.matches(make_slot(reference + timedelta(hours=24)), reference)
    assert not rule.matches(make_slot(reference + timedelta(hours=23)), reference)


def test_weekday_filter_uses_the_user_timezone(make_slot, reference):
    # Sunday 23:30 UTC is already Monday in Paris.
    sunday_night = datetime(2026, 3, 8, 23, 30, tzinfo=UTC)
    slot = make_slot(sunday_night)
    assert WeekdayFilter([Weekday.MONDAY], "Europe/Paris").matches(slot, reference)
    assert not WeekdayFilter([Weekday.SUNDAY], "Europe/Paris").matches(slot, reference)
    assert WeekdayFilter([Weekday.SUNDAY], "UTC").matches(slot, reference)


def test_time_of_day_filter_uses_the_user_timezone(make_slot, reference):
    rule = TimeOfDayFilter(TimeOfDayRange(start="08:00", end="12:00"), "Europe/Paris")
    assert rule.matches(make_slot(reference), reference)  # 10:00 Paris
    assert not rule.matches(make_slot(reference + timedelta(hours=3)), reference)


def test_all_of_filter_is_true_without_children(make_slot, reference):
    assert AllOfFilter([]).matches(make_slot(reference), reference)


def test_all_of_filter_requires_every_child(make_slot, reference):
    rule = AllOfFilter([PractitionerFilter("dr-house"), ReasonFilter("consultation")])
    assert rule.matches(make_slot(reference), reference)
    assert not rule.matches(make_slot(reference, reason="autre"), reference)


def test_build_slot_filter_accepts_a_matching_slot(criteria, make_slot, reference):
    # Wednesday 4 March 2026, 09:00 Paris.
    slot = make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS))
    assert build_slot_filter(criteria).matches(slot, reference)


@pytest.mark.parametrize(
    ("start", "overrides"),
    [
        (datetime(2026, 3, 7, 9, 0, tzinfo=PARIS), {}),  # Saturday, excluded weekday
        (datetime(2026, 3, 4, 15, 0, tzinfo=PARIS), {}),  # outside the morning window
        (datetime(2026, 5, 4, 9, 0, tzinfo=PARIS), {}),  # beyond the 30-day horizon
        (datetime(2026, 3, 4, 9, 0, tzinfo=PARIS), {"practitioner_id": "dr-wilson"}),
        (datetime(2026, 3, 4, 9, 0, tzinfo=PARIS), {"reason": "vaccin"}),
    ],
)
def test_build_slot_filter_rejects_non_matching_slots(
    criteria, make_slot, reference, start, overrides
):
    assert not build_slot_filter(criteria).matches(make_slot(start, **overrides), reference)


def test_build_slot_filter_is_open_to_new_rules(criteria, make_slot, reference):
    class NeverMatches(SlotFilter):
        def matches(self, slot, reference):
            return False

    rule = build_slot_filter(criteria, factories=[lambda _: NeverMatches()])
    assert not rule.matches(make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS)), reference)
