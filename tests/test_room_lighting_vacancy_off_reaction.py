"""Tests for RoomLightingVacancyOffReaction."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.reactions.lighting_vacancy_off import (
    RoomLightingVacancyOffReaction,
    build_room_lighting_vacancy_off_reaction,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, occupied_rooms: list[str], ts: str) -> DecisionSnapshot:
    return replace(DecisionSnapshot.empty(), ts=ts, occupied_rooms=occupied_rooms)


def test_room_lighting_vacancy_off_reaction_fires_after_delay():
    hass = MagicMock()
    states = {"light.living_main": "on"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomLightingVacancyOffReaction(
        hass=hass,
        room_id="living",
        entity_steps=[{"entity_id": "light.living_main", "action": "off"}],
        vacancy_delay_s=120,
        reaction_id="vacancy-test",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 1, tzinfo=timezone.utc).isoformat()
    ts3 = datetime(2026, 3, 23, 18, 3, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []
    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts2)]) == []
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=[], ts=ts2),
            _snapshot(occupied_rooms=[], ts=ts3),
        ]
    )
    assert len(steps) == 1
    assert steps[0].action == "light.turn_off"
    assert steps[0].params["entity_id"] == "light.living_main"


def test_room_lighting_vacancy_off_reaction_resets_when_room_reoccupied():
    hass = MagicMock()
    states = {"light.living_main": "on"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomLightingVacancyOffReaction(
        hass=hass,
        room_id="living",
        entity_steps=[{"entity_id": "light.living_main", "action": "off"}],
        vacancy_delay_s=120,
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 1, tzinfo=timezone.utc).isoformat()
    ts3 = datetime(2026, 3, 23, 18, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts1)]) == []
    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts2)]) == []
    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts3)]) == []


def test_room_lighting_vacancy_off_reaction_does_not_fire_when_lights_already_off():
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="off")
    reaction = RoomLightingVacancyOffReaction(
        hass=hass,
        room_id="living",
        entity_steps=[{"entity_id": "light.living_main", "action": "off"}],
        vacancy_delay_s=0,
        reaction_id="vacancy-test",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts1)]) == []
    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts1)]) == []
    assert reaction.diagnostics()["vacancy_episode_active"] is False


def test_room_lighting_vacancy_off_reaction_counts_suppression_during_cooldown():
    hass = MagicMock()
    states = {"light.living_main": "on"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomLightingVacancyOffReaction(
        hass=hass,
        room_id="living",
        entity_steps=[{"entity_id": "light.living_main", "action": "off"}],
        vacancy_delay_s=0,
        reaction_id="vacancy-test",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 1, tzinfo=timezone.utc).isoformat()
    ts3 = datetime(2026, 3, 23, 18, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts1)]) == []

    first = reaction.evaluate(
        [
            _snapshot(occupied_rooms=[], ts=ts1),
            _snapshot(occupied_rooms=[], ts=ts2),
        ]
    )
    assert len(first) == 1

    second = reaction.evaluate(
        [
            _snapshot(occupied_rooms=[], ts=ts1),
            _snapshot(occupied_rooms=[], ts=ts3),
        ]
    )
    assert second == []
    assert reaction.diagnostics()["suppressed_count"] == 1


def test_room_lighting_vacancy_off_builder_rejects_missing_entity_steps():
    engine = SimpleNamespace(_hass=MagicMock())

    reaction = build_room_lighting_vacancy_off_reaction(
        engine,
        "vacancy-test",
        {
            "room_id": "living",
            "vacancy_delay_s": 60,
            "entity_steps": [],
        },
    )

    assert reaction is None
