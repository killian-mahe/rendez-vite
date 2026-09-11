from __future__ import annotations

from datetime import datetime

import pytest

from rendez_vite.domain.models import SlotAlert
from rendez_vite.infrastructure.rendering import PlainTextAlertRenderer
from tests.conftest import PARIS


def build_alert(criteria, slots):
    return SlotAlert(recipient="patient@test", criteria=criteria, slots=slots)


def test_a_single_slot_is_announced_in_the_singular(criteria, make_slot):
    slot = make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS), location="Paris")
    message = PlainTextAlertRenderer().render(build_alert(criteria, [slot]))
    assert message.recipient == "patient@test"
    assert "1 créneau disponible" in message.subject
    assert "consultation" in message.subject
    assert "mercredi 4 mars 2026 à 09:00 (Paris)" in message.body


def test_several_slots_are_announced_in_the_plural(criteria, make_slot):
    slots = [
        make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS), slot_id="a"),
        make_slot(datetime(2026, 3, 9, 11, 30, tzinfo=PARIS), slot_id="b"),
    ]
    message = PlainTextAlertRenderer().render(build_alert(criteria, slots))
    assert "2 créneaux disponibles" in message.subject
    assert "2 créneaux disponibles correspondent à vos critères" in message.body
    assert "lundi 9 mars 2026 à 11:30" in message.body


def test_the_booking_link_is_included_when_known(criteria, make_slot):
    slot = make_slot(
        datetime(2026, 3, 4, 9, 0, tzinfo=PARIS), booking_url="https://booking.test/abc"
    )
    body = PlainTextAlertRenderer().render(build_alert(criteria, [slot])).body
    assert "Réserver : https://booking.test/abc" in body


def test_dates_are_shown_in_the_criteria_timezone(criteria, make_slot):
    from dataclasses import replace

    slot = make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS))
    utc_criteria = replace(criteria, timezone="UTC")
    body = PlainTextAlertRenderer().render(build_alert(utc_criteria, [slot])).body
    assert "à 08:00" in body


@pytest.mark.parametrize(("month", "label"), [(1, "janvier"), (8, "août"), (12, "décembre")])
def test_month_names_do_not_depend_on_the_system_locale(criteria, make_slot, month, label):
    slot = make_slot(datetime(2026, month, 2, 9, 0, tzinfo=PARIS))
    assert label in PlainTextAlertRenderer().render(build_alert(criteria, [slot])).body
