from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from temporalio.testing import ActivityEnvironment

from rendez_vite.config import Settings
from rendez_vite.domain.errors import UnknownComponentError
from rendez_vite.domain.models import EmailMessage, SlotAlert, SlotQuery
from rendez_vite.domain.ports import NotificationSender
from rendez_vite.infrastructure.notifiers import build_notifier_registry
from rendez_vite.infrastructure.providers import build_provider_registry
from rendez_vite.infrastructure.registry import ComponentRegistry
from rendez_vite.infrastructure.rendering import PlainTextAlertRenderer
from rendez_vite.orchestration.activities import AppointmentActivities
from rendez_vite.orchestration.contracts import (
    FETCH_SLOTS_ACTIVITY,
    SEND_ALERT_ACTIVITY,
    FetchSlotsRequest,
    SendAlertRequest,
)
from tests.conftest import PARIS


class RecordingNotifier:
    def __init__(self):
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def activities(notifier, settings):
    notifiers: ComponentRegistry[NotificationSender] = ComponentRegistry("notifier")
    notifiers.register("recording", lambda _: notifier)
    return AppointmentActivities(
        providers=build_provider_registry(),
        notifiers=notifiers,
        renderer=PlainTextAlertRenderer(),
        settings=settings,
    )


async def test_fetch_activity_returns_the_provider_slots(activities, reference):
    request = FetchSlotsRequest(
        provider="fake",
        query=SlotQuery(
            practitioner_id="dr-house",
            reason="consultation",
            window_start=reference,
            window_end=reference + timedelta(days=5),
        ),
    )
    result = await ActivityEnvironment().run(activities.fetch_available_slots, request)
    assert result.slots
    assert all(slot.practitioner_id == "dr-house" for slot in result.slots)


async def test_fetch_activity_rejects_an_unknown_provider(activities, reference):
    request = FetchSlotsRequest(
        provider="carrier-pigeon",
        query=SlotQuery(
            practitioner_id="dr-house",
            reason="consultation",
            window_start=reference,
            window_end=reference + timedelta(days=1),
        ),
    )
    with pytest.raises(UnknownComponentError):
        await ActivityEnvironment().run(activities.fetch_available_slots, request)


async def test_alert_activity_renders_and_delivers(activities, notifier, criteria, make_slot):
    slot = make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS))
    alert = SlotAlert(recipient="patient@test", criteria=criteria, slots=[slot])
    await ActivityEnvironment().run(
        activities.send_slot_alert, SendAlertRequest(notifier="recording", alert=alert)
    )
    assert len(notifier.sent) == 1
    assert notifier.sent[0].recipient == "patient@test"
    assert "créneau" in notifier.sent[0].subject


def test_activities_expose_their_temporal_names(activities):
    names = {definition.__temporal_activity_definition.name for definition in activities.as_list()}
    assert names == {FETCH_SLOTS_ACTIVITY, SEND_ALERT_ACTIVITY}


def test_builtin_registries_are_wired_in_the_default_activities():
    activities = AppointmentActivities(
        providers=build_provider_registry(),
        notifiers=build_notifier_registry(),
        renderer=PlainTextAlertRenderer(),
        settings=Settings(),
    )
    assert len(activities.as_list()) == 2
