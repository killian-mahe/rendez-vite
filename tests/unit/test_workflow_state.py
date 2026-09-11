"""Unit tests of the workflow state machine, run outside any Temporal runtime."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest
from temporalio.exceptions import ActivityError, ApplicationError

from rendez_vite.orchestration.contracts import FETCH_SLOTS_ACTIVITY, WatchRequest, WatchState
from rendez_vite.orchestration.workflows import (
    STOP_REASON_MATCH,
    RendezViteWatchWorkflow,
    describe_failure,
    is_fatal_failure,
)
from tests.conftest import PARIS


def build_workflow(criteria):
    workflow = RendezViteWatchWorkflow()
    workflow._criteria = criteria
    return workflow


def activity_failure(cause: BaseException | None) -> ActivityError:
    error = ActivityError(
        "activity failed",
        scheduled_event_id=1,
        started_event_id=2,
        identity="test",
        activity_type=FETCH_SLOTS_ACTIVITY,
        activity_id="1",
        retry_state=None,
    )
    error.__cause__ = cause
    return error


def test_a_fresh_workflow_reports_an_empty_status():
    status = RendezViteWatchWorkflow().status()
    assert status.criteria is None
    assert status.checks_done == 0
    assert status.paused is False
    assert status.stop_requested is False
    assert status.last_check is None
    assert status.last_error is None


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        (RuntimeError("timeout"), "availability lookup: timeout"),
        (None, "availability lookup: activity failed"),
    ],
)
def test_a_tolerated_failure_names_its_root_cause(cause, expected):
    assert describe_failure("availability lookup", activity_failure(cause)) == expected


def test_the_status_reports_a_tolerated_failure(criteria):
    workflow = build_workflow(criteria)
    workflow._last_error = describe_failure("alert delivery", activity_failure(OSError("refused")))
    assert workflow.status().last_error == "alert delivery: refused"


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        (ApplicationError("nope", type="UnknownComponentError"), True),
        (ApplicationError("nope", type="ConfigurationError"), True),
        (ApplicationError("booking service down", type="SlotProviderError"), False),
        (ApplicationError("unspecified"), False),
        (RuntimeError("boom"), False),
        (None, False),
    ],
)
def test_only_a_misconfiguration_is_fatal(cause, expected):
    assert is_fatal_failure(activity_failure(cause)) is expected


def test_pause_and_resume_toggle_the_status(criteria):
    workflow = build_workflow(criteria)
    workflow.pause()
    assert workflow.status().paused is True
    workflow.resume()
    assert workflow.status().paused is False


def test_stop_is_reflected_in_the_status(criteria):
    workflow = build_workflow(criteria)
    workflow.stop()
    assert workflow.status().stop_requested is True


def test_updating_the_criteria_forgets_the_announced_slots(criteria):
    workflow = build_workflow(criteria)
    workflow._state = WatchState(seen_slot_ids=["already-announced"])
    new_criteria = replace(criteria, horizon_days=7)
    workflow.update_criteria(new_criteria)
    assert workflow.status().criteria == new_criteria
    assert workflow._state.seen_slot_ids == []


def test_the_summary_reports_the_progress(criteria, make_slot):
    workflow = build_workflow(criteria)
    workflow._state = WatchState(checks_done=4, notifications_sent=1)
    slots = [make_slot(datetime(2026, 3, 4, 9, 0, tzinfo=PARIS))]
    summary = workflow._summary(STOP_REASON_MATCH, slots)
    assert summary.checks_done == 4
    assert summary.notifications_sent == 1
    assert summary.stop_reason == STOP_REASON_MATCH
    assert summary.matched_slots == slots


def test_the_next_run_inherits_the_current_state(criteria):
    workflow = build_workflow(criteria)
    workflow._state = WatchState(checks_done=200, seen_slot_ids=["a"])
    request = WatchRequest(criteria=criteria, recipient_email="patient@test.fr")
    following = workflow._next_request(request)
    assert following.state.checks_done == 200
    assert following.state.seen_slot_ids == ["a"]
    assert following.recipient_email == "patient@test.fr"
    assert following.state is not workflow._state


def test_the_next_run_keeps_the_criteria_received_by_signal(criteria):
    workflow = build_workflow(criteria)
    updated = replace(criteria, horizon_days=3)
    workflow.update_criteria(updated)
    request = WatchRequest(criteria=criteria, recipient_email="patient@test.fr")
    assert workflow._next_request(request).criteria == updated
