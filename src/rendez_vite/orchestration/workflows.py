"""The long-running workflow watching a practitioner's agenda."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from rendez_vite.domain.filters import build_slot_filter
    from rendez_vite.domain.models import AppointmentSlot, SearchCriteria, SlotAlert, SlotQuery
    from rendez_vite.domain.policy import SlotWatchPolicy
    from rendez_vite.orchestration.contracts import (
        FETCH_SLOTS_ACTIVITY,
        PAUSE_SIGNAL,
        RESUME_SIGNAL,
        SEND_ALERT_ACTIVITY,
        STATUS_QUERY,
        STOP_SIGNAL,
        UPDATE_CRITERIA_SIGNAL,
        WATCH_WORKFLOW,
        FetchSlotsRequest,
        FetchSlotsResult,
        SendAlertRequest,
        WatchOptions,
        WatchRequest,
        WatchState,
        WatchStatus,
        WatchSummary,
    )

_FATAL_ERROR_TYPES = ("ConfigurationError", "UnknownComponentError")

_FETCH_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=list(_FATAL_ERROR_TYPES),
)
_NOTIFY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=10,
    non_retryable_error_types=list(_FATAL_ERROR_TYPES),
)
_FETCH_TIMEOUT = timedelta(seconds=30)
_NOTIFY_TIMEOUT = timedelta(seconds=60)

STOP_REASON_MATCH = "matching slot announced"
STOP_REASON_SIGNAL = "stop requested"
STOP_REASON_MAX_CHECKS = "maximum number of checks reached"


def is_fatal_failure(error: ActivityError) -> bool:
    """Tell whether an activity failure is worth giving up the whole watch for.

    Parameters
    ----------
    error
        Failure raised by an activity once its retries are exhausted.

    Returns
    -------
    bool
        ``True`` for a misconfiguration, which waiting or retrying would not fix.
    """
    cause = error.cause
    return isinstance(cause, ApplicationError) and cause.type in _FATAL_ERROR_TYPES


def describe_failure(step: str, error: ActivityError) -> str:
    """Summarise a tolerated failure for the status query.

    Parameters
    ----------
    step
        Step that failed, as shown to the user.
    error
        The failure being tolerated.

    Returns
    -------
    str
        One line naming the step and its root cause.
    """
    return f"{step}: {error.cause or error}"


@workflow.defn(name=WATCH_WORKFLOW)
class RendezViteWatchWorkflow:
    """Poll a booking service until a slot matching the user's criteria shows up.

    The workflow owns the *when* (scheduling, retries, history rollover) and delegates
    the *what* to the domain policy and the *how* to the activities.
    """

    def __init__(self) -> None:
        """Initialise the in-memory state of a workflow run."""
        self._criteria: SearchCriteria | None = None
        self._state = WatchState()
        self._paused = False
        self._stop_requested = False
        self._last_check: datetime | None = None
        self._last_match_count = 0
        self._last_error: str | None = None

    @workflow.run
    async def run(self, request: WatchRequest) -> WatchSummary:
        """Watch the practitioner's agenda until a stop condition is met.

        Parameters
        ----------
        request
            Criteria, recipient, watch options and the state inherited from a previous
            run when the history was rolled over.

        Returns
        -------
        WatchSummary
            How many checks ran, how many alerts were sent and why the watch ended.
        """
        self._criteria = request.criteria
        self._state = request.state.copy()
        options = request.options
        checks_this_run = 0
        matched: list[AppointmentSlot] = []

        while True:
            await workflow.wait_condition(lambda: not self._paused or self._stop_requested)
            if self._stop_requested:
                return self._summary(STOP_REASON_SIGNAL, matched)

            matched = await self._run_check(request, options)
            checks_this_run += 1

            if matched and options.stop_on_first_match:
                return self._summary(STOP_REASON_MATCH, matched)
            if options.max_checks is not None and self._state.checks_done >= options.max_checks:
                return self._summary(STOP_REASON_MAX_CHECKS, matched)

            await self._sleep_until_next_check(options)
            # Rolled over after the wait, so the polling interval holds across runs.
            if checks_this_run >= options.checks_before_continue_as_new and not (
                self._paused or self._stop_requested
            ):
                workflow.continue_as_new(self._next_request(request))

    async def _run_check(
        self, request: WatchRequest, options: WatchOptions
    ) -> list[AppointmentSlot]:
        """Run a single availability check and announce what it found.

        Parameters
        ----------
        request
            The original watch request, used for the recipient address.
        options
            Watch options driving the provider and notifier selection.

        Returns
        -------
        list of AppointmentSlot
            The slots announced during this check, empty when nothing matched or when a
            transient failure got in the way.
        """
        criteria = self._criteria
        assert criteria is not None  # noqa: S101 - set before the loop starts
        reference = workflow.now()
        self._state.checks_done += 1
        self._last_check = reference

        slots = await self._fetch_slots(criteria, options, reference)
        if slots is None:
            return []

        policy = SlotWatchPolicy(
            build_slot_filter(criteria),
            stop_on_first_match=options.stop_on_first_match,
        )
        decision = policy.evaluate(slots, reference, self._state.seen_slot_ids)
        self._last_match_count = len(decision.matches)
        if not decision.should_notify:
            return []
        if not await self._announce(request, criteria, options, decision.matches):
            return []

        # Recorded only once the alert is out, so a failed delivery is retried next round.
        self._state.seen_slot_ids = decision.seen_slot_ids
        self._state.notifications_sent += 1
        return decision.matches

    async def _fetch_slots(
        self, criteria: SearchCriteria, options: WatchOptions, reference: datetime
    ) -> list[AppointmentSlot] | None:
        """Ask the booking service for the availabilities of the search window.

        Parameters
        ----------
        criteria
            Criteria the search window is derived from.
        options
            Watch options naming the provider to use.
        reference
            Instant the search window is computed from.

        Returns
        -------
        list of AppointmentSlot or None
            The offered slots, or ``None`` when the lookup failed and the watch should
            simply try again at the next interval.

        Raises
        ------
        temporalio.exceptions.ActivityError
            If the lookup failed because of a misconfiguration.
        """
        try:
            result: FetchSlotsResult = await workflow.execute_activity(
                FETCH_SLOTS_ACTIVITY,
                FetchSlotsRequest(
                    provider=options.provider,
                    query=SlotQuery.from_criteria(criteria, reference),
                ),
                result_type=FetchSlotsResult,
                start_to_close_timeout=_FETCH_TIMEOUT,
                retry_policy=_FETCH_RETRY,
            )
        except ActivityError as error:
            if is_fatal_failure(error):
                raise
            self._record_failure("availability lookup", error)
            return None
        self._last_error = None
        return result.slots

    async def _announce(
        self,
        request: WatchRequest,
        criteria: SearchCriteria,
        options: WatchOptions,
        slots: list[AppointmentSlot],
    ) -> bool:
        """Send an alert for the given slots.

        Parameters
        ----------
        request
            The watch request, used for the recipient address.
        criteria
            Criteria the slots were selected with, shown in the message.
        options
            Watch options naming the notifier to use.
        slots
            Slots to announce.

        Returns
        -------
        bool
            ``True`` when the alert went out.

        Raises
        ------
        temporalio.exceptions.ActivityError
            If the delivery failed because of a misconfiguration.
        """
        try:
            await workflow.execute_activity(
                SEND_ALERT_ACTIVITY,
                SendAlertRequest(
                    notifier=options.notifier,
                    alert=SlotAlert(
                        recipient=request.recipient_email,
                        criteria=criteria,
                        slots=slots,
                    ),
                ),
                start_to_close_timeout=_NOTIFY_TIMEOUT,
                retry_policy=_NOTIFY_RETRY,
            )
        except ActivityError as error:
            if is_fatal_failure(error):
                raise
            self._record_failure("alert delivery", error)
            return False
        return True

    def _record_failure(self, step: str, error: ActivityError) -> None:
        """Remember a tolerated failure so that the status query can report it.

        Parameters
        ----------
        step
            Step that failed, as shown to the user.
        error
            The failure being tolerated.
        """
        self._last_error = describe_failure(step, error)
        workflow.logger.warning("%s failed, trying again at the next check: %s", step, error.cause)

    async def _sleep_until_next_check(self, options: WatchOptions) -> None:
        """Wait for the next check, waking up early on a stop signal.

        Parameters
        ----------
        options
            Watch options holding the polling interval.
        """
        with contextlib.suppress(TimeoutError):
            await workflow.wait_condition(
                lambda: self._stop_requested,
                timeout=timedelta(seconds=options.check_interval_seconds),
            )

    def _next_request(self, request: WatchRequest) -> WatchRequest:
        """Build the request carrying the current state into the next run.

        Parameters
        ----------
        request
            The request of the current run.

        Returns
        -------
        WatchRequest
            The request to continue as new with.
        """
        criteria = self._criteria or request.criteria
        return WatchRequest(
            criteria=criteria,
            recipient_email=request.recipient_email,
            options=request.options,
            state=self._state.copy(),
        )

    def _summary(self, reason: str, matched: list[AppointmentSlot]) -> WatchSummary:
        """Build the final result of the watch.

        Parameters
        ----------
        reason
            Why the watch ended.
        matched
            Slots announced during the last check.

        Returns
        -------
        WatchSummary
            The workflow result.
        """
        return WatchSummary(
            checks_done=self._state.checks_done,
            notifications_sent=self._state.notifications_sent,
            stop_reason=reason,
            matched_slots=matched,
        )

    @workflow.signal(name=UPDATE_CRITERIA_SIGNAL)
    def update_criteria(self, criteria: SearchCriteria) -> None:
        """Replace the search criteria without restarting the watch.

        Parameters
        ----------
        criteria
            The new criteria; previously announced slots are forgotten so that they can
            be re-evaluated against the new rules.
        """
        self._criteria = criteria
        self._state.seen_slot_ids = []

    @workflow.signal(name=PAUSE_SIGNAL)
    def pause(self) -> None:
        """Suspend the checks until the watch is resumed."""
        self._paused = True

    @workflow.signal(name=RESUME_SIGNAL)
    def resume(self) -> None:
        """Resume a paused watch."""
        self._paused = False

    @workflow.signal(name=STOP_SIGNAL)
    def stop(self) -> None:
        """Ask the watch to end after the current check."""
        self._stop_requested = True

    @workflow.query(name=STATUS_QUERY)
    def status(self) -> WatchStatus:
        """Return a snapshot of the watch.

        Returns
        -------
        WatchStatus
            Progress counters and the criteria currently in use.
        """
        return WatchStatus(
            criteria=self._criteria,
            checks_done=self._state.checks_done,
            notifications_sent=self._state.notifications_sent,
            paused=self._paused,
            stop_requested=self._stop_requested,
            last_check=self._last_check,
            last_match_count=self._last_match_count,
            last_error=self._last_error,
        )
