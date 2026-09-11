from __future__ import annotations

from datetime import timedelta

from rendez_vite.domain.filters import PractitionerFilter, SlotFilter
from rendez_vite.domain.policy import SlotWatchPolicy, WatchDecision


class AcceptAll(SlotFilter):
    def matches(self, slot, reference):
        return True


def test_no_slot_means_no_decision(reference):
    decision = SlotWatchPolicy(AcceptAll()).evaluate([], reference)
    assert decision.matches == []
    assert decision.should_notify is False
    assert decision.should_stop is False


def test_only_matching_slots_are_kept(make_slot, reference):
    slots = [
        make_slot(reference + timedelta(days=1), practitioner_id="dr-house"),
        make_slot(reference + timedelta(days=2), practitioner_id="dr-wilson"),
    ]
    decision = SlotWatchPolicy(PractitionerFilter("dr-house")).evaluate(slots, reference)
    assert [slot.practitioner_id for slot in decision.matches] == ["dr-house"]


def test_matches_are_sorted_by_start(make_slot, reference):
    later = make_slot(reference + timedelta(days=3), slot_id="late")
    sooner = make_slot(reference + timedelta(days=1), slot_id="soon")
    decision = SlotWatchPolicy(AcceptAll()).evaluate([later, sooner], reference)
    assert [slot.slot_id for slot in decision.matches] == ["soon", "late"]


def test_already_announced_slots_are_skipped(make_slot, reference):
    slot = make_slot(reference + timedelta(days=1), slot_id="known")
    decision = SlotWatchPolicy(AcceptAll()).evaluate([slot], reference, seen_slot_ids=["known"])
    assert decision.matches == []
    assert decision.seen_slot_ids == ["known"]


def test_duplicates_inside_one_batch_are_announced_once(make_slot, reference):
    slot = make_slot(reference + timedelta(days=1), slot_id="dup")
    decision = SlotWatchPolicy(AcceptAll()).evaluate([slot, slot], reference)
    assert len(decision.matches) == 1
    assert decision.seen_slot_ids == ["dup"]


def test_watch_stops_on_first_match_by_default(make_slot, reference):
    slot = make_slot(reference + timedelta(days=1))
    assert SlotWatchPolicy(AcceptAll()).evaluate([slot], reference).should_stop is True


def test_watch_can_keep_running_after_a_match(make_slot, reference):
    slot = make_slot(reference + timedelta(days=1))
    policy = SlotWatchPolicy(AcceptAll(), stop_on_first_match=False)
    assert policy.evaluate([slot], reference).should_stop is False


def test_memory_of_announced_slots_is_bounded(make_slot, reference):
    slots = [
        make_slot(reference + timedelta(days=1, minutes=index), slot_id=f"s{index}")
        for index in range(5)
    ]
    policy = SlotWatchPolicy(AcceptAll(), max_tracked_slots=3)
    decision = policy.evaluate(slots, reference, seen_slot_ids=["old"])
    assert decision.seen_slot_ids == ["s2", "s3", "s4"]


def test_decision_reports_whether_a_notification_is_needed(make_slot, reference):
    empty = WatchDecision(matches=[], seen_slot_ids=[], should_stop=False)
    filled = WatchDecision(matches=[make_slot(reference)], seen_slot_ids=[], should_stop=False)
    assert empty.should_notify is False
    assert filled.should_notify is True
