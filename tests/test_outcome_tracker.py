from __future__ import annotations

from custom_components.heima.runtime.contracts import HeimaEvent as RuntimeEvent
from custom_components.heima.runtime.inference.snapshot_store import HouseSnapshot
from custom_components.heima.runtime.outcome_tracker import (
    OutcomeSpec,
    OutcomeTracker,
    PendingVerification,
)


class Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _snapshot() -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-05-03T10:00:00+00:00",
        weekday=6,
        minute_of_day=600,
        anyone_home=True,
        named_present=("stefano",),
        room_occupancy={"studio": True},
        detected_activities=("pc_active",),
        house_state="work",
    )


def test_register_pending_from_reaction_fired() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)

    pending = tracker.on_reaction_fired(
        reaction_id="reaction.work_lights",
        reaction_type="ConsecutiveStateReaction",
        expected_event_type="lighting",
        snapshot_at_fire=_snapshot(),
    )

    assert pending.expected_within_s == 600.0
    assert pending.fired_at_ts == 100.0
    assert tracker.pending() == (pending,)
    assert tracker.diagnostics()["pending_count"] == 1


def test_custom_timeout_uses_outcome_spec() -> None:
    tracker = OutcomeTracker()

    assert (
        tracker.timeout_for(
            "CustomReaction", outcome_spec=OutcomeSpec("activity.started", timeout_s=42)
        )
        == 42.0
    )
    assert tracker.timeout_for("CustomReaction") == 900.0
    assert tracker.timeout_for("PresencePatternReaction") == 1800.0


def test_positive_outcome_resolves_pending_and_resets_negative_streak() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)
    tracker.register_pending(
        PendingVerification(
            reaction_id="reaction.work_lights",
            expected_event_type="lighting",
            expected_within_s=600.0,
            fired_at_ts=clock.now(),
            snapshot_at_fire=_snapshot(),
        )
    )

    resolved = tracker.check_pending([{"event_type": "lighting", "room_id": "studio"}])

    assert len(resolved) == 1
    assert resolved[0].outcome == "positive"
    assert resolved[0].reaction_id == "reaction.work_lights"
    assert resolved[0].context["matched_event"]["room_id"] == "studio"
    assert tracker.pending() == ()
    assert tracker.records() == resolved
    assert tracker.negative_streak("reaction.work_lights") == 0
    assert tracker.positive_streak("reaction.work_lights") == 1


def test_unmatched_pending_remains_before_timeout() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)
    pending = tracker.on_reaction_fired(
        reaction_id="reaction.arrival",
        expected_event_type="presence",
        expected_within_s=1800.0,
        snapshot_at_fire=_snapshot(),
    )
    clock.advance(1799.0)

    assert tracker.check_pending(["lighting"]) == ()
    assert tracker.pending() == (pending,)
    assert tracker.records() == ()


def test_timeout_records_negative_and_increments_streak() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)

    for index in range(2):
        tracker.on_reaction_fired(
            reaction_id="reaction.arrival",
            expected_event_type="presence",
            expected_within_s=1800.0,
            fired_at_ts=clock.now(),
            snapshot_at_fire=_snapshot(),
        )
        clock.advance(1800.0 + index)
        resolved = tracker.check_pending([])
        assert len(resolved) == 1
        assert resolved[0].outcome == "negative"

    assert tracker.negative_streak("reaction.arrival") == 2
    assert tracker.positive_streak("reaction.arrival") == 0
    assert tracker.diagnostics()["negative_streaks"] == {"reaction.arrival": 2}


def test_ready_for_degradation_after_five_consecutive_negatives() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)

    for index in range(5):
        tracker.on_reaction_fired(
            reaction_id="reaction.unreliable",
            expected_event_type="heating",
            expected_within_s=1.0,
            fired_at_ts=clock.now(),
            snapshot_at_fire=_snapshot(),
        )
        clock.advance(1.0 + index)
        tracker.check_pending([])

    assert tracker.ready_for_degradation("reaction.unreliable") is True


def test_ready_for_boost_after_ten_consecutive_positives() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)

    for _ in range(OutcomeTracker.POSITIVE_BOOST_THRESHOLD):
        tracker.on_reaction_fired(
            reaction_id="reaction.reliable",
            expected_event_type="lighting",
            expected_within_s=1.0,
            fired_at_ts=clock.now(),
            snapshot_at_fire=_snapshot(),
        )
        resolved = tracker.check_pending(["lighting"])
        assert len(resolved) == 1

    assert tracker.positive_streak("reaction.reliable") == 10
    assert tracker.ready_for_boost("reaction.reliable") is True


def test_negative_outcome_resets_positive_streak_before_boost_threshold() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)

    for _ in range(OutcomeTracker.POSITIVE_BOOST_THRESHOLD - 1):
        tracker.on_reaction_fired(
            reaction_id="reaction.reliable",
            expected_event_type="lighting",
            expected_within_s=1.0,
            fired_at_ts=clock.now(),
            snapshot_at_fire=_snapshot(),
        )
        tracker.check_pending(["lighting"])

    tracker.on_reaction_fired(
        reaction_id="reaction.reliable",
        expected_event_type="lighting",
        expected_within_s=1.0,
        fired_at_ts=clock.now(),
        snapshot_at_fire=_snapshot(),
    )
    clock.advance(1.0)
    tracker.check_pending([])

    assert tracker.positive_streak("reaction.reliable") == 0
    assert tracker.ready_for_boost("reaction.reliable") is False


def test_event_type_matching_supports_runtime_events() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)
    tracker.on_reaction_fired(
        reaction_id="reaction.activity",
        expected_event_type="activity.started",
        snapshot_at_fire=_snapshot(),
    )
    event = RuntimeEvent(
        type="activity.started",
        key="activity:shower_running",
        severity="info",
        title="Shower started",
        message="Shower is running",
        context={"activity": "shower_running"},
    )

    resolved = tracker.check_pending([event])

    assert len(resolved) == 1
    assert resolved[0].outcome == "positive"
    assert resolved[0].context["matched_event"]["type"] == "activity.started"


def test_reset_clears_tracker_state() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)
    tracker.on_reaction_fired(
        reaction_id="reaction.cleanup",
        expected_event_type="lighting",
        expected_within_s=1.0,
        snapshot_at_fire=_snapshot(),
    )
    clock.advance(1.0)
    tracker.check_pending([])

    tracker.reset()

    assert tracker.pending() == ()
    assert tracker.records() == ()
    assert tracker.negative_streak("reaction.cleanup") == 0
    assert tracker.positive_streak("reaction.cleanup") == 0


def test_diagnostics_include_positive_streaks() -> None:
    clock = Clock()
    tracker = OutcomeTracker(now_provider=clock.now)
    tracker.on_reaction_fired(
        reaction_id="reaction.reliable",
        expected_event_type="lighting",
        snapshot_at_fire=_snapshot(),
    )
    tracker.check_pending(["lighting"])

    diagnostics = tracker.diagnostics()

    assert diagnostics["positive_streaks"] == {"reaction.reliable": 1}
    assert diagnostics["positive_boost_threshold"] == OutcomeTracker.POSITIVE_BOOST_THRESHOLD
