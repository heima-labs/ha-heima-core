"""Tests for RoomLightingAssistReaction."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.reactions.lighting_assist import (
    RoomLightingAssistReaction,
    build_room_lighting_assist_reaction,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, occupied_rooms: list[str], ts: str) -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    return replace(base, ts=ts, occupied_rooms=occupied_rooms)


def test_room_lighting_assist_reaction_fires_when_bucket_matches_exact_target():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "ok"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="off") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
        reaction_id="darkness-test",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []

    bucket_state["living:room_lux"] = "dim"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )
    assert len(steps) == 1
    assert steps[0].action == "light.turn_on"
    assert steps[0].params["entity_id"] == "light.living_main"
    assert steps[0].params["brightness"] == 144
    assert steps[0].params["color_temp_kelvin"] == 2900


def test_room_lighting_assist_reaction_with_lte_match_fires_when_bucket_skips_past_target():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "bright"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="off") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
        reaction_id="darkness-lte",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []

    bucket_state["living:room_lux"] = "dark"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )

    assert len(steps) == 1
    assert steps[0].action == "light.turn_on"


def test_room_lighting_assist_reaction_with_exact_match_does_not_fire_when_bucket_skips_target():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "bright"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="off") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="eq",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
        reaction_id="darkness-eq",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []

    bucket_state["living:room_lux"] = "dark"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )

    assert steps == []


def test_room_lighting_assist_reaction_respects_room_occupancy():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "ok"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="off") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 128,
                "color_temp_kelvin": 3000,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts1)]) == []

    bucket_state["living:room_lux"] = "dim"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=[], ts=ts1),
            _snapshot(occupied_rooms=[], ts=ts2),
        ]
    )
    assert steps == []


def test_room_lighting_assist_reaction_fires_when_room_is_already_dark_on_entry():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "dim"}
    states = {"light.living_main": "off"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
        reaction_id="darkness-steady",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()

    steps = reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)])

    assert len(steps) == 1
    assert steps[0].action == "light.turn_on"
    assert steps[0].params["entity_id"] == "light.living_main"


def test_room_lighting_assist_reaction_does_not_refire_while_same_dark_episode_persists():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "dim"}
    states = {"light.living_main": "off"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
        reaction_id="darkness-steady",
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 1, tzinfo=timezone.utc).isoformat()

    first = reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)])
    assert len(first) == 1

    states["light.living_main"] = "on"
    second = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )
    assert second == []


def test_room_lighting_assist_reaction_does_not_fire_when_apply_already_satisfied():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "dim"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="on") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []
    assert reaction.diagnostics()["steady_condition_active"] is False


def test_room_lighting_assist_reaction_counts_suppression_during_cooldown():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "dim"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="off") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
                "rgb_color": None,
            }
        ],
        followup_window_s=999,
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 23, 18, 1, tzinfo=timezone.utc).isoformat()

    first = reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)])
    assert len(first) == 1

    reaction._steady_condition_active = False  # noqa: SLF001
    second = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )
    assert second == []
    assert reaction.diagnostics()["suppressed_count"] == 1


def test_room_lighting_assist_reaction_builds_turn_off_steps():
    hass = MagicMock()
    bucket_state = {"living:room_lux": "dim"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state="on") if eid == "light.living_main" else None
    )
    reaction = RoomLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        room_id="living",
        primary_signal_entities=["sensor.living_room_lux"],
        primary_bucket="dim",
        entity_steps=[
            {
                "entity_id": "light.living_main",
                "action": "off",
            }
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 23, 18, 0, tzinfo=timezone.utc).isoformat()

    steps = reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)])

    assert len(steps) == 1
    assert steps[0].action == "light.turn_off"
    assert steps[0].params["entity_id"] == "light.living_main"


def test_build_room_lighting_assist_reaction_requires_primary_bucket():
    engine = SimpleNamespace(
        _hass=MagicMock(),
        signal_bucket=lambda room_id, signal_name: None,
        _entry=SimpleNamespace(
            options={
                "rooms": [
                    {
                        "room_id": "living",
                        "signals": [
                            {
                                "signal_name": "room_lux",
                                "bucket_labels": ["dark", "dim", "ok", "bright"],
                            }
                        ],
                    }
                ]
            }
        ),
    )

    reaction = build_room_lighting_assist_reaction(
        engine,
        "darkness-test",
        {
            "room_id": "living",
            "primary_signal_entities": ["sensor.living_room_lux"],
            "primary_signal_name": "room_lux",
            "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
        },
    )

    assert reaction is None
