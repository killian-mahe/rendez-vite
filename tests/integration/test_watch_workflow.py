"""End-to-end tests of the watch workflow.

They run against Temporal's time-skipping test server, downloaded on first use. Where it
is not available, point ``RENDEZ_VITE_TEST_TEMPORAL_ADDRESS`` to a running server such as
``temporal server start-dev``; timers then last for real (a few minutes in total).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from temporalio import activity
from temporalio.client import Client, WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from rendez_vite.domain.models import AppointmentSlot, SearchCriteria
from rendez_vite.orchestration.contracts import (
    FETCH_SLOTS_ACTIVITY,
    PAUSE_SIGNAL,
    SEND_ALERT_ACTIVITY,
    STOP_SIGNAL,
    FetchSlotsRequest,
    FetchSlotsResult,
    SendAlertRequest,
    WatchOptions,
    WatchRequest,
    WatchSummary,
)
from rendez_vite.orchestration.workflows import (
    STOP_REASON_MATCH,
    STOP_REASON_MAX_CHECKS,
    STOP_REASON_SIGNAL,
    RendezViteWatchWorkflow,
)

pytestmark = pytest.mark.integration

CRITERIA = SearchCriteria(practitioner_id="dr-house", reason="consultation", timezone="UTC")

Batch = list[AppointmentSlot] | Exception


class StubBookingService:
    """Serve one batch per check (the last one repeats) and record the alerts."""

    def __init__(self, *batches: Batch) -> None:
        self._batches = batches
        self.requests: list[FetchSlotsRequest] = []
        self.alerts: list[SendAlertRequest] = []

    @activity.defn(name=FETCH_SLOTS_ACTIVITY)
    async def fetch(self, request: FetchSlotsRequest) -> FetchSlotsResult:
        self.requests.append(request)
        if not self._batches:
            return FetchSlotsResult(slots=[])
        batch = self._batches[min(len(self.requests), len(self._batches)) - 1]
        if isinstance(batch, Exception):
            raise batch
        return FetchSlotsResult(slots=batch)

    @activity.defn(name=SEND_ALERT_ACTIVITY)
    async def send(self, request: SendAlertRequest) -> None:
        self.alerts.append(request)


@pytest.fixture
async def env() -> AsyncIterator[WorkflowEnvironment]:
    address = os.environ.get("RENDEZ_VITE_TEST_TEMPORAL_ADDRESS")
    try:
        if address:
            environment = WorkflowEnvironment.from_client(await Client.connect(address))
        else:
            environment = await WorkflowEnvironment.start_time_skipping()
    except Exception as error:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"No Temporal server available: {error}")
    async with environment:
        yield environment


@asynccontextmanager
async def running_worker(
    env: WorkflowEnvironment, service: StubBookingService
) -> AsyncIterator[str]:
    task_queue = f"rendez-vite-it-{uuid.uuid4().hex}"
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflows=[RendezViteWatchWorkflow],
        activities=[service.fetch, service.send],
    ):
        yield task_queue


def upcoming_slot(slot_id: str, days: int = 2) -> AppointmentSlot:
    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=days)
    return AppointmentSlot(
        slot_id=slot_id,
        practitioner_id="dr-house",
        reason="consultation",
        start=start,
        end=start + timedelta(minutes=30),
    )


def watch_request(**options: Any) -> WatchRequest:
    return WatchRequest(
        criteria=CRITERIA,
        recipient_email="patient@example.org",
        options=WatchOptions(check_interval_seconds=60, **options),
    )


def new_workflow_id() -> str:
    return f"watch-{uuid.uuid4().hex}"


async def run_watch(
    env: WorkflowEnvironment, service: StubBookingService, request: WatchRequest
) -> WatchSummary:
    async with running_worker(env, service) as task_queue:
        return await env.client.execute_workflow(
            RendezViteWatchWorkflow.run, request, id=new_workflow_id(), task_queue=task_queue
        )


async def test_the_watch_ends_once_a_matching_slot_is_announced(env):
    service = StubBookingService([upcoming_slot("slot-1")])
    summary = await run_watch(env, service, watch_request())
    assert summary.stop_reason == STOP_REASON_MATCH
    assert summary.checks_done == 1
    assert summary.notifications_sent == 1
    assert [slot.slot_id for slot in summary.matched_slots] == ["slot-1"]
    assert service.alerts[0].alert.recipient == "patient@example.org"


async def test_the_watch_polls_until_the_check_budget_is_spent(env):
    service = StubBookingService()
    summary = await run_watch(env, service, watch_request(max_checks=3))
    assert summary.stop_reason == STOP_REASON_MAX_CHECKS
    assert summary.checks_done == 3
    assert len(service.requests) == 3
    assert service.alerts == []


async def test_a_continuous_watch_announces_each_slot_once(env):
    first, second = upcoming_slot("slot-1", days=2), upcoming_slot("slot-2", days=3)
    service = StubBookingService([first], [first, second])
    request = watch_request(stop_on_first_match=False, max_checks=2)
    summary = await run_watch(env, service, request)
    assert summary.notifications_sent == 2
    announced = [[slot.slot_id for slot in sent.alert.slots] for sent in service.alerts]
    assert announced == [["slot-1"], ["slot-2"]]


async def test_history_is_rolled_over_without_losing_progress(env):
    service = StubBookingService()
    request = watch_request(max_checks=3, checks_before_continue_as_new=1)
    summary = await run_watch(env, service, request)
    assert summary.stop_reason == STOP_REASON_MAX_CHECKS
    assert summary.checks_done == 3


async def test_a_failing_check_does_not_end_the_watch(env):
    service = StubBookingService(
        ApplicationError("booking service unavailable", non_retryable=True),
        [upcoming_slot("slot-1")],
    )
    summary = await run_watch(env, service, watch_request())
    assert summary.stop_reason == STOP_REASON_MATCH
    assert summary.checks_done == 2


async def test_a_misconfiguration_fails_the_watch(env):
    service = StubBookingService(
        ApplicationError("unknown provider", type="UnknownComponentError", non_retryable=True)
    )
    with pytest.raises(WorkflowFailureError):
        await run_watch(env, service, watch_request())
    assert len(service.requests) == 1


async def test_a_stop_signal_ends_the_watch_before_any_check(env):
    service = StubBookingService()
    async with running_worker(env, service) as task_queue:
        handle = await env.client.start_workflow(
            RendezViteWatchWorkflow.run,
            watch_request(),
            id=new_workflow_id(),
            task_queue=task_queue,
            start_signal=STOP_SIGNAL,
        )
        summary = await handle.result()
    assert summary.stop_reason == STOP_REASON_SIGNAL
    assert summary.checks_done == 0
    assert service.requests == []


async def test_a_paused_watch_can_be_reconfigured_then_resumed(env):
    service = StubBookingService()
    async with running_worker(env, service) as task_queue:
        handle = await env.client.start_workflow(
            RendezViteWatchWorkflow.run,
            watch_request(max_checks=1),
            id=new_workflow_id(),
            task_queue=task_queue,
            start_signal=PAUSE_SIGNAL,
        )
        status = await handle.query(RendezViteWatchWorkflow.status)
        assert status.paused is True
        assert status.checks_done == 0

        await handle.signal(
            RendezViteWatchWorkflow.update_criteria, replace(CRITERIA, horizon_days=7)
        )
        await handle.signal(RendezViteWatchWorkflow.resume)
        summary = await handle.result()

    assert summary.checks_done == 1
    query = service.requests[0].query
    assert query.window_end - query.window_start == timedelta(days=7)
