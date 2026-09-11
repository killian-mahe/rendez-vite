from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from rendez_vite.domain.errors import SlotProviderError
from rendez_vite.domain.models import SlotQuery
from rendez_vite.infrastructure.providers.http import HttpSlotProvider


@pytest.fixture
def query(reference):
    return SlotQuery(
        practitioner_id="dr-house",
        reason="consultation",
        window_start=reference,
        window_end=reference + timedelta(days=30),
    )


def build_provider(handler):
    transport = httpx.MockTransport(handler)
    return HttpSlotProvider(
        "https://booking.test/api/",
        token="secret",
        client_factory=lambda: httpx.AsyncClient(transport=transport),
    )


async def test_slots_are_parsed_from_the_payload(query):
    payload = {
        "slots": [
            {
                "id": "abc",
                "start": "2026-03-04T09:00:00+01:00",
                "end": "2026-03-04T09:30:00+01:00",
                "location": "Paris",
                "booking_url": "https://booking.test/abc",
            }
        ]
    }
    provider = build_provider(lambda request: httpx.Response(200, json=payload))
    slots = await provider.fetch_slots(query)
    assert len(slots) == 1
    assert slots[0].slot_id == "abc"
    assert slots[0].location == "Paris"
    assert slots[0].practitioner_id == "dr-house"


async def test_the_window_is_sent_as_query_parameters(query):
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        seen["url"] = str(request.url.path)
        return httpx.Response(200, json={"slots": []})

    await build_provider(handler).fetch_slots(query)
    assert seen["url"] == "/api/availabilities"
    assert seen["practitioner_id"] == "dr-house"
    assert seen["from"] == query.window_start.isoformat()
    assert seen["to"] == query.window_end.isoformat()


async def test_a_bare_list_payload_is_accepted(query):
    payload = [{"start": "2026-03-04T09:00:00+01:00", "end": "2026-03-04T09:30:00+01:00"}]
    provider = build_provider(lambda request: httpx.Response(200, json=payload))
    slots = await provider.fetch_slots(query)
    assert slots[0].slot_id == "dr-house:2026-03-04T09:00:00+01:00"
    assert slots[0].reason == "consultation"


async def test_an_error_status_is_reported(query):
    provider = build_provider(lambda request: httpx.Response(503))
    with pytest.raises(SlotProviderError, match="Booking API call failed"):
        await provider.fetch_slots(query)


async def test_a_transport_failure_is_reported(query):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(SlotProviderError, match="Booking API call failed"):
        await build_provider(handler).fetch_slots(query)


async def test_a_malformed_body_is_reported(query):
    provider = build_provider(lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(SlotProviderError, match="malformed JSON"):
        await provider.fetch_slots(query)


async def test_a_payload_without_slots_is_reported(query):
    provider = build_provider(lambda request: httpx.Response(200, json={"error": "nope"}))
    with pytest.raises(SlotProviderError, match="list of slots"):
        await provider.fetch_slots(query)


@pytest.mark.parametrize(
    "entry",
    [
        {"start": "2026-03-04T09:00:00+01:00"},
        {"start": "yesterday", "end": "2026-03-04T09:30:00+01:00"},
        {"start": "2026-03-04T09:00:00+01:00", "end": "2026-03-04T08:00:00+01:00"},
    ],
)
async def test_an_unusable_entry_is_reported(query, entry):
    provider = build_provider(lambda request: httpx.Response(200, json={"slots": [entry]}))
    with pytest.raises(SlotProviderError, match="Unusable slot entry"):
        await provider.fetch_slots(query)


def test_the_default_client_carries_the_bearer_token():
    provider = HttpSlotProvider("https://booking.test/api", token="secret")
    client = provider._default_client_factory()
    assert client.headers["Authorization"] == "Bearer secret"


def test_the_default_client_works_without_a_token():
    provider = HttpSlotProvider("https://booking.test/api")
    assert "Authorization" not in provider._default_client_factory().headers
