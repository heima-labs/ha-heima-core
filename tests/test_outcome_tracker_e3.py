from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

from custom_components.heima.runtime.behaviors.event_recorder import EventRecorderBehavior
from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.inference.snapshot_store import HouseSnapshot
from custom_components.heima.runtime.outcome_tracker import (
    OutcomeSpec,
    OutcomeTracker,
    PendingVerification,
)
from custom_components.heima.runtime.reactions.base import HeimaReaction
from custom_components.heima.runtime.reactions.presence import PresencePatternReaction
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def now(self) -> float:
        return self.value


class FakeContextBuilder:
    def build(self, snapshot: DecisionSnapshot) -> EventContext:
        return EventContext(
            weekday=0,
            minute_of_day=0,
            month=1,
            house_state=snapshot.house_state,
            occupants_count=1 if snapshot.anyone_home else 0,
            occupied_rooms=tuple(snapshot.occupied_rooms),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        )


class FakeSnapshotStore:
    def __init__(self, snapshots: list[HouseSnapshot]) -> None:
        self._snapshots = snapshots

    def snapshots(self) -> list[HouseSnapshot]:
        return list(self._snapshots)


class NoStepOutcomeReaction(HeimaReaction):
    @property
    def outcome_spec(self) -> OutcomeSpec:
        return OutcomeSpec(expected_event_type="presence", match_data={"transition": "arrive"})

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        return []


class StepNoOutcomeReaction(HeimaReaction):
    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        return [_step()]


class StepOutcomeReaction(HeimaReaction):
    @property
    def outcome_spec(self) -> OutcomeSpec:
        return OutcomeSpec(expected_event_type="presence", match_data={"transition": "arrive"})

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        return [_step()]


class FakeEventRecorder:
    def __init__(self, events: list[HeimaEvent]) -> None:
        self._events = events

    @property
    def cycle_events(self) -> list[HeimaEvent]:
        return list(self._events)


def _context() -> EventContext:
    return EventContext(
        weekday=0,
        minute_of_day=600,
        month=5,
        house_state="home",
        occupants_count=1,
        occupied_rooms=("studio",),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


def _event(event_type: str, data: dict[str, Any]) -> HeimaEvent:
    return HeimaEvent(
        ts="2026-05-04T10:00:00+00:00",
        event_type=event_type,
        context=_context(),
        source=None,
        data=data,
    )


def _house_snapshot() -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-05-04T10:00:00+00:00",
        weekday=0,
        minute_of_day=600,
        anyone_home=False,
        named_present=(),
        room_occupancy={},
        house_state="away",
    )


def _pending(*, match_data: dict[str, Any] | None = None) -> PendingVerification:
    return PendingVerification(
        reaction_id="reaction.presence",
        expected_event_type="presence",
        expected_within_s=1800.0,
        fired_at_ts=100.0,
        snapshot_at_fire=_house_snapshot(),
        match_data=dict(match_data or {}),
    )


def _snapshot(
    *,
    anyone_home: bool = False,
    occupied_rooms: tuple[str, ...] = (),
    house_state: str = "away",
) -> DecisionSnapshot:
    return replace(
        DecisionSnapshot.empty(),
        ts="2026-05-04T10:00:00+00:00",
        anyone_home=anyone_home,
        occupied_rooms=occupied_rooms,
        house_state=house_state,
    )


def _step() -> ApplyStep:
    return ApplyStep(domain="heating", target="climate.living", action="climate.set_temperature")


def _make_engine():
    from custom_components.heima.runtime.engine import HeimaEngine

    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.async_services.return_value = {}
    entry = MagicMock()
    entry.entry_id = "test"
    entry.options = {}
    return HeimaEngine(hass, entry)


def test_match_data_empty_matches_any_event() -> None:
    tracker = OutcomeTracker(now_provider=Clock().now)
    tracker.register_pending(_pending())

    resolved = tracker.check_pending([_event("presence", {"transition": "depart"})])

    assert len(resolved) == 1
    assert resolved[0].outcome == "positive"


def test_match_data_subset_matches() -> None:
    tracker = OutcomeTracker(now_provider=Clock().now)
    tracker.register_pending(_pending(match_data={"transition": "arrive"}))

    resolved = tracker.check_pending([_event("presence", {"transition": "arrive", "extra": "x"})])

    assert len(resolved) == 1
    assert resolved[0].outcome == "positive"


def test_match_data_subset_no_match() -> None:
    tracker = OutcomeTracker(now_provider=Clock().now)
    pending = _pending(match_data={"transition": "arrive"})
    tracker.register_pending(pending)

    resolved = tracker.check_pending([_event("presence", {"transition": "depart"})])

    assert resolved == ()
    assert tracker.pending() == (pending,)


def test_presence_pattern_reaction_outcome_spec_has_match_data() -> None:
    reaction = PresencePatternReaction(steps=[_step()])

    assert reaction.outcome_spec.match_data == {"transition": "arrive"}


def test_event_recorder_cycle_events_populated() -> None:
    behavior = EventRecorderBehavior(MagicMock(), MagicMock(), FakeContextBuilder())
    behavior.on_snapshot(_snapshot(anyone_home=False))
    behavior.on_snapshot(_snapshot(anyone_home=True))

    assert any(
        event.event_type == "presence" and event.data == {"transition": "arrive"}
        for event in behavior.cycle_events
    )


def test_event_recorder_cycle_events_reset_each_call() -> None:
    behavior = EventRecorderBehavior(MagicMock(), MagicMock(), FakeContextBuilder())
    behavior.on_snapshot(_snapshot(anyone_home=False))
    behavior.on_snapshot(_snapshot(anyone_home=True))
    first_cycle_events = behavior.cycle_events
    behavior.on_snapshot(_snapshot(anyone_home=True))

    assert first_cycle_events
    assert behavior.cycle_events == []


def test_check_pending_resolves_positive_with_match_data() -> None:
    tracker = OutcomeTracker(now_provider=Clock().now)
    tracker.register_pending(_pending(match_data={"transition": "arrive"}))

    resolved = tracker.check_pending([_event("presence", {"transition": "arrive"})])

    assert len(resolved) == 1
    assert resolved[0].outcome == "positive"
    assert tracker.pending() == ()


def test_check_pending_no_resolve_wrong_match_data() -> None:
    tracker = OutcomeTracker(now_provider=Clock().now)
    pending = _pending(match_data={"transition": "arrive"})
    tracker.register_pending(pending)

    resolved = tracker.check_pending([_event("presence", {"transition": "depart"})])

    assert resolved == ()
    assert tracker.pending() == (pending,)


def test_reaction_with_outcome_spec_no_register_when_no_steps() -> None:
    engine = _make_engine()
    tracker = OutcomeTracker()
    engine.set_outcome_tracker(tracker)
    engine.set_snapshot_store(FakeSnapshotStore([_house_snapshot()]))
    engine.register_reaction(NoStepOutcomeReaction())

    assert engine._dispatch_reactions([DecisionSnapshot.empty()]) == []
    assert tracker.pending() == ()


def test_reaction_with_outcome_spec_registers_when_steps_fire() -> None:
    engine = _make_engine()
    tracker = OutcomeTracker()
    engine.set_outcome_tracker(tracker)
    engine.set_snapshot_store(FakeSnapshotStore([_house_snapshot()]))
    engine.register_reaction(StepOutcomeReaction())

    steps = engine._dispatch_reactions([DecisionSnapshot.empty()])

    assert len(steps) == 1
    pending = tracker.pending()
    assert len(pending) == 1
    assert pending[0].expected_event_type == "presence"
    assert pending[0].match_data == {"transition": "arrive"}


def test_no_outcome_spec_no_pending() -> None:
    engine = _make_engine()
    tracker = OutcomeTracker()
    engine.set_outcome_tracker(tracker)
    engine.set_snapshot_store(FakeSnapshotStore([_house_snapshot()]))
    engine.register_reaction(StepNoOutcomeReaction())

    steps = engine._dispatch_reactions([DecisionSnapshot.empty()])

    assert len(steps) == 1
    assert tracker.pending() == ()


def test_engine_check_pending_uses_event_recorder_cycle_events() -> None:
    engine = _make_engine()
    tracker = OutcomeTracker()
    tracker.register_pending(_pending(match_data={"transition": "arrive"}))
    engine.set_outcome_tracker(tracker)
    engine._event_recorder = FakeEventRecorder([_event("presence", {"transition": "arrive"})])

    engine._check_reaction_outcomes()

    assert tracker.pending() == ()
    assert tracker.records()[0].outcome == "positive"
