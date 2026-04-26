from __future__ import annotations

from datetime import UTC, datetime

from custom_components.heima.runtime.reactions.scheduled_routine import (
    ScheduledRoutineReaction,
    present_scheduled_routine_label,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, house_state: str = "home", anyone_home: bool = False) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="snap-1",
        ts="2026-04-14T18:00:00+00:00",
        house_state=house_state,
        anyone_home=anyone_home,
        people_count=1 if anyone_home else 0,
        occupied_rooms=[],
        lighting_intents={},
        security_state="disarmed",
        context_signals={},
    )


def test_scheduled_routine_respects_house_state_and_anyone_home(monkeypatch):
    monkeypatch.setattr(
        "custom_components.heima.runtime.reactions.scheduled_routine.dt_util.now",
        lambda: datetime(2026, 4, 14, 20, 0, tzinfo=UTC),
    )
    reaction = ScheduledRoutineReaction(
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=0,
        house_state_in=["vacation"],
        skip_if_anyone_home=True,
        steps=[
            {
                "domain": "script",
                "target": "script.evening_routine",
                "action": "script.turn_on",
                "params": {"entity_id": "script.evening_routine"},
            }
        ],
        reaction_id="routine-1",
    )

    assert reaction.evaluate([_snapshot(house_state="home", anyone_home=False)]) == []
    assert reaction.evaluate([_snapshot(house_state="vacation", anyone_home=True)]) == []
    steps = reaction.evaluate([_snapshot(house_state="vacation", anyone_home=False)])
    assert len(steps) == 1
    assert steps[0].action == "script.turn_on"


def test_scheduled_routine_fires_once_per_day(monkeypatch):
    monkeypatch.setattr(
        "custom_components.heima.runtime.reactions.scheduled_routine.dt_util.now",
        lambda: datetime(2026, 4, 14, 20, 0, tzinfo=UTC),
    )
    reaction = ScheduledRoutineReaction(
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=0,
        steps=[
            {
                "domain": "switch",
                "target": "switch.fountain",
                "action": "switch.turn_on",
                "params": {"entity_id": "switch.fountain"},
            }
        ],
        reaction_id="routine-2",
    )

    first = reaction.evaluate([_snapshot()])
    second = reaction.evaluate([_snapshot()])
    assert len(first) == 1
    assert second == []


def test_present_scheduled_routine_label():
    label = present_scheduled_routine_label(
        "routine-1",
        {
            "reaction_type": "scheduled_routine",
            "weekday": 1,
            "scheduled_min": 1200,
            "routine_kind": "scene",
            "target_entities": ["scene.movie_time"],
        },
        {},
    )

    assert label == "Routine Tuesday ~20:00 · scene.movie_time"
