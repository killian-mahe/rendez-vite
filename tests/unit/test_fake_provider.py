from __future__ import annotations

from datetime import timedelta

from rendez_vite.domain.models import SlotQuery
from rendez_vite.infrastructure.providers.fake import FakeSlotProvider
from tests.conftest import PARIS


def build_query(reference, days=3):
    return SlotQuery(
        practitioner_id="dr-house",
        reason="consultation",
        window_start=reference,
        window_end=reference + timedelta(days=days),
    )


async def test_same_query_always_returns_the_same_slots(reference):
    provider = FakeSlotProvider(release_rate=0.4)
    first = await provider.fetch_slots(build_query(reference))
    second = await provider.fetch_slots(build_query(reference))
    assert [slot.slot_id for slot in first] == [slot.slot_id for slot in second]


async def test_slots_stay_inside_the_requested_window(reference):
    query = build_query(reference)
    slots = await FakeSlotProvider(release_rate=1.0).fetch_slots(query)
    assert slots
    assert all(query.window_start <= slot.start < query.window_end for slot in slots)


async def test_slots_stay_inside_the_opening_hours(reference):
    slots = await FakeSlotProvider(release_rate=1.0).fetch_slots(build_query(reference))
    hours = {slot.start.astimezone(PARIS).hour for slot in slots}
    assert min(hours) >= 8
    assert max(hours) < 18


async def test_a_full_agenda_returns_nothing(reference):
    assert await FakeSlotProvider(release_rate=0.0).fetch_slots(build_query(reference)) == []


async def test_the_seed_changes_the_generated_agenda(reference):
    query = build_query(reference)
    first = await FakeSlotProvider(seed="a", release_rate=0.4).fetch_slots(query)
    second = await FakeSlotProvider(seed="b", release_rate=0.4).fetch_slots(query)
    assert [slot.slot_id for slot in first] != [slot.slot_id for slot in second]


async def test_generated_slots_carry_the_query_details(reference):
    slots = await FakeSlotProvider(release_rate=1.0).fetch_slots(build_query(reference, days=1))
    slot = slots[0]
    assert slot.practitioner_id == "dr-house"
    assert slot.reason == "consultation"
    assert slot.end - slot.start == timedelta(minutes=30)
    assert slot.booking_url
