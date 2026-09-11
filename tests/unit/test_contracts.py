from __future__ import annotations

import pytest

from rendez_vite.domain.errors import ConfigurationError
from rendez_vite.orchestration.contracts import WatchOptions, WatchRequest, WatchState


def test_default_options_are_usable():
    options = WatchOptions()
    assert options.check_interval_seconds == 900
    assert options.stop_on_first_match is True


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"check_interval_seconds": 30}, "at least 60s"),
        ({"max_checks": 0}, "must be positive"),
        ({"checks_before_continue_as_new": 0}, "must be positive"),
    ],
)
def test_options_validation(kwargs, message):
    with pytest.raises(ConfigurationError, match=message):
        WatchOptions(**kwargs)


@pytest.mark.parametrize("email", ["nope", "a@b", "a b@test.fr", ""])
def test_request_rejects_implausible_addresses(criteria, email):
    with pytest.raises(ConfigurationError, match="Invalid recipient"):
        WatchRequest(criteria=criteria, recipient_email=email)


def test_request_accepts_a_plausible_address(criteria):
    request = WatchRequest(criteria=criteria, recipient_email="patient@test.fr")
    assert request.state.checks_done == 0


def test_state_copy_is_independent():
    state = WatchState(checks_done=2, notifications_sent=1, seen_slot_ids=["a"])
    clone = state.copy()
    clone.seen_slot_ids.append("b")
    clone.checks_done = 99
    assert state.seen_slot_ids == ["a"]
    assert state.checks_done == 2
