"""Tests for contextual room lighting assist reaction and resolver."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.reactions.contextual_lighting_assist import (
    RoomContextualLightingAssistReaction,
    build_room_contextual_lighting_assist_reaction,
    derive_contextual_occupancy_reason,
    resolve_contextual_lighting_profile,
    time_window_matches,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, occupied_rooms: list[str], ts: str, house_state: str = "home") -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    return replace(base, ts=ts, occupied_rooms=occupied_rooms, house_state=house_state)


def test_derive_contextual_occupancy_reason_prefers_focus_for_working() -> None:
    assert (
        derive_contextual_occupancy_reason(house_state="working", occupancy_age_s=10.0) == "focus"
    )


def test_derive_contextual_occupancy_reason_distinguishes_transient_and_settled() -> None:
    assert (
        derive_contextual_occupancy_reason(house_state="home", occupancy_age_s=60.0) == "transient"
    )
    assert (
        derive_contextual_occupancy_reason(house_state="home", occupancy_age_s=599.0) == "transient"
    )
    assert (
        derive_contextual_occupancy_reason(house_state="home", occupancy_age_s=600.0) == "settled"
    )


def test_time_window_matches_midnight_crossing() -> None:
    assert time_window_matches(
        current_time=datetime(2026, 4, 18, 0, 15, tzinfo=UTC).time(),
        window={"start": "23:30", "end": "06:30"},
    )
    assert not time_window_matches(
        current_time=datetime(2026, 4, 18, 12, 15, tzinfo=UTC).time(),
        window={"start": "23:30", "end": "06:30"},
    )


def test_resolve_contextual_lighting_profile_prefers_first_matching_rule() -> None:
    profile, index, summary, reason = resolve_contextual_lighting_profile(
        house_state="home",
        current_dt=datetime(2026, 4, 18, 19, 0, tzinfo=UTC),
        occupancy_age_s=60.0,
        rules=[
            {
                "profile": "evening_relax",
                "time_window": {"start": "18:30", "end": "23:30"},
            },
            {
                "profile": "night_navigation",
                "time_window": {"start": "18:00", "end": "23:59"},
            },
        ],
        default_profile="day_generic",
    )

    assert profile == "evening_relax"
    assert index == 0
    assert "profile=evening_relax" in (summary or "")
    assert reason == "transient"


def test_resolve_contextual_lighting_profile_falls_back_to_default() -> None:
    profile, index, summary, reason = resolve_contextual_lighting_profile(
        house_state="away",
        current_dt=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
        occupancy_age_s=None,
        rules=[
            {
                "profile": "workday_focus",
                "house_state_in": ["working"],
            }
        ],
        default_profile="day_generic",
    )

    assert profile == "day_generic"
    assert index is None
    assert summary == "default_profile"
    assert reason == "generic"


def test_contextual_lighting_reaction_fires_selected_profile() -> None:
    hass = MagicMock()
    states = {
        "light.studio_desk": "off",
        "light.studio_main": "off",
    }
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    bucket_state = {"studio:room_lux": "dark"}
    reaction = RoomContextualLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        occupancy_age_getter=lambda room_id: 700.0 if room_id == "studio" else None,
        room_id="studio",
        primary_signal_entities=["sensor.studio_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        profiles={
            "workday_focus": {
                "entity_steps": [
                    {
                        "entity_id": "light.studio_desk",
                        "action": "on",
                        "brightness": 180,
                        "color_temp_kelvin": 4300,
                    }
                ]
            },
            "day_generic": {
                "entity_steps": [
                    {
                        "entity_id": "light.studio_main",
                        "action": "on",
                        "brightness": 120,
                        "color_temp_kelvin": 3200,
                    }
                ]
            },
        },
        rules=[
            {"profile": "workday_focus", "house_state_in": ["working"]},
            {"profile": "day_generic", "house_state_in": ["home"]},
        ],
        default_profile="day_generic",
        followup_window_s=0,
        reaction_id="contextual-studio",
    )
    ts = datetime(2026, 4, 18, 10, 0, tzinfo=UTC).isoformat()

    steps = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts, house_state="working")])

    assert len(steps) == 1
    assert steps[0].params["entity_id"] == "light.studio_desk"
    diagnostics = reaction.diagnostics()
    assert diagnostics["selected_profile"] == "workday_focus"
    assert diagnostics["occupancy_reason"] == "focus"
    assert diagnostics["last_applied_profile"] == "workday_focus"


def test_contextual_lighting_reaction_reapplies_when_profile_changes() -> None:
    hass = MagicMock()
    states = {
        "light.studio_desk": "on",
        "light.studio_main": "on",
    }
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomContextualLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        occupancy_age_getter=lambda room_id: 700.0,
        room_id="studio",
        primary_signal_entities=["sensor.studio_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        profiles={
            "workday_focus": {
                "entity_steps": [
                    {"entity_id": "light.studio_desk", "action": "on", "brightness": 180}
                ]
            },
            "evening_relax": {
                "entity_steps": [
                    {"entity_id": "light.studio_main", "action": "on", "brightness": 90}
                ]
            },
        },
        rules=[
            {"profile": "workday_focus", "house_state_in": ["working"]},
            {
                "profile": "evening_relax",
                "house_state_in": ["home"],
                "time_window": {"start": "18:30", "end": "23:30"},
            },
        ],
        default_profile="workday_focus",
        followup_window_s=0,
    )
    ts1 = datetime(2026, 4, 18, 10, 0, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 4, 18, 20, 0, tzinfo=UTC).isoformat()

    first = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1, house_state="working")])
    assert len(first) == 1

    second = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2, house_state="home")])
    assert len(second) == 1
    assert second[0].params["entity_id"] == "light.studio_main"
    assert reaction.diagnostics()["last_applied_profile"] == "evening_relax"


def test_contextual_lighting_reaction_reapplies_when_ambient_scale_changes() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="on")
    bucket_state = {"studio:room_lux": "dark", "studio:outdoor_lux": "bright"}
    reaction = RoomContextualLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: bucket_state.get(f"{room_id}:{signal_name}"),
        occupancy_age_getter=lambda room_id: 700.0,
        room_id="studio",
        primary_signal_entities=["sensor.studio_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        profiles={
            "day_generic": {
                "entity_steps": [
                    {"entity_id": "light.studio_desk", "action": "on", "brightness": 160}
                ]
            }
        },
        rules=[],
        default_profile="day_generic",
        ambient_modulation={
            "source_signal_name": "outdoor_lux",
            "mode": "brightness_multiplier",
            "buckets": {"bright": 0.7, "dark": 1.15},
            "clamp_min": 20,
            "clamp_max": 255,
        },
        followup_window_s=0,
    )
    ts1 = datetime(2026, 4, 18, 10, 0, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 4, 18, 10, 5, tzinfo=UTC).isoformat()

    first = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)])
    assert len(first) == 1
    assert first[0].params["brightness"] == 112
    assert reaction.diagnostics()["ambient_source_bucket"] == "bright"
    assert reaction.diagnostics()["ambient_brightness_scale"] == 0.7

    bucket_state["studio:outdoor_lux"] = "dark"
    second = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2)])
    assert len(second) == 1
    assert second[0].params["brightness"] == 184
    assert reaction.diagnostics()["ambient_source_bucket"] == "dark"
    assert reaction.diagnostics()["ambient_brightness_scale"] == 1.15


def test_contextual_lighting_reaction_reapplies_profile_switch_during_cooldown() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="on")
    reaction = RoomContextualLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        occupancy_age_getter=lambda room_id: 700.0,
        room_id="studio",
        primary_signal_entities=["sensor.studio_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        profiles={
            "workday_focus": {
                "entity_steps": [
                    {"entity_id": "light.studio_desk", "action": "on", "brightness": 180}
                ]
            },
            "evening_relax": {
                "entity_steps": [
                    {"entity_id": "light.studio_main", "action": "on", "brightness": 90}
                ]
            },
        },
        rules=[
            {"profile": "workday_focus", "house_state_in": ["working"]},
            {"profile": "evening_relax", "house_state_in": ["home"]},
        ],
        default_profile="workday_focus",
        followup_window_s=999,
    )
    ts1 = datetime(2026, 4, 18, 10, 0, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 4, 18, 20, 0, tzinfo=UTC).isoformat()

    assert (
        len(
            reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1, house_state="working")])
        )
        == 1
    )
    second = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2, house_state="home")])
    assert len(second) == 1
    assert second[0].params["entity_id"] == "light.studio_main"
    assert reaction.diagnostics()["last_applied_profile"] == "evening_relax"
    assert reaction.diagnostics()["suppressed_count"] == 0


def test_contextual_lighting_reaction_resets_last_applied_profile_when_room_empties() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="on")
    reaction = RoomContextualLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        occupancy_age_getter=lambda room_id: 700.0,
        room_id="studio",
        primary_signal_entities=["sensor.studio_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        profiles={
            "day_generic": {
                "entity_steps": [
                    {"entity_id": "light.studio_desk", "action": "on", "brightness": 140}
                ]
            }
        },
        rules=[],
        default_profile="day_generic",
        followup_window_s=0,
    )
    ts1 = datetime(2026, 4, 18, 10, 0, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 4, 18, 10, 5, tzinfo=UTC).isoformat()

    assert len(reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)])) == 1
    assert reaction.diagnostics()["last_applied_profile"] == "day_generic"

    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts2)]) == []
    assert reaction.diagnostics()["last_applied_profile"] is None


def test_contextual_lighting_reaction_resets_cooldown_when_room_empties() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="off")
    reaction = RoomContextualLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        occupancy_age_getter=lambda room_id: 700.0,
        room_id="studio",
        primary_signal_entities=["sensor.studio_lux"],
        primary_bucket="ok",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["dark", "dim", "ok", "bright"],
        profiles={
            "day_generic": {
                "entity_steps": [
                    {"entity_id": "light.studio_desk", "action": "on", "brightness": 140}
                ]
            }
        },
        rules=[],
        default_profile="day_generic",
        followup_window_s=999,
    )
    ts1 = datetime(2026, 4, 18, 10, 0, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 4, 18, 10, 1, tzinfo=UTC).isoformat()
    ts3 = datetime(2026, 4, 18, 10, 2, tzinfo=UTC).isoformat()

    assert len(reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)])) == 1
    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=ts2)]) == []
    assert len(reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts3)])) == 1


def test_build_contextual_lighting_reaction_rejects_missing_default_profile() -> None:
    engine = SimpleNamespace(
        _hass=MagicMock(),
        _entry=SimpleNamespace(
            options={
                "rooms": [
                    {
                        "room_id": "studio",
                        "signals": [
                            {
                                "signal_name": "room_lux",
                                "buckets": [
                                    {"label": "dark"},
                                    {"label": "dim"},
                                    {"label": "ok"},
                                    {"label": "bright"},
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        signal_bucket=lambda room_id, signal_name: None,
        room_occupancy_age_s=lambda room_id: None,
    )

    reaction = build_room_contextual_lighting_assist_reaction(
        engine,
        "contextual-test",
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "profiles": {
                "day_generic": {
                    "entity_steps": [{"entity_id": "light.studio_desk", "action": "on"}]
                }
            },
            "rules": [],
        },
    )

    assert reaction is None


def test_build_contextual_lighting_reaction_accepts_valid_contract() -> None:
    engine = SimpleNamespace(
        _hass=MagicMock(),
        _entry=SimpleNamespace(
            options={
                "rooms": [
                    {
                        "room_id": "studio",
                        "signals": [
                            {
                                "signal_name": "room_lux",
                                "buckets": [
                                    {"label": "dark"},
                                    {"label": "dim"},
                                    {"label": "ok"},
                                    {"label": "bright"},
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        signal_bucket=lambda room_id, signal_name: None,
        room_occupancy_age_s=lambda room_id: None,
    )

    reaction = build_room_contextual_lighting_assist_reaction(
        engine,
        "contextual-test",
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "profiles": {
                "day_generic": {
                    "entity_steps": [{"entity_id": "light.studio_desk", "action": "on"}]
                }
            },
            "rules": [],
            "default_profile": "day_generic",
        },
    )

    assert reaction is not None
    assert reaction.reaction_id == "contextual-test"
    assert reaction.diagnostics()["primary_bucket_match_mode"] == "lte"


def test_build_contextual_lighting_reaction_rejects_invalid_ambient_modulation() -> None:
    engine = SimpleNamespace(
        _hass=MagicMock(),
        _entry=SimpleNamespace(
            options={
                "rooms": [
                    {
                        "room_id": "studio",
                        "signals": [
                            {
                                "signal_name": "room_lux",
                                "buckets": [
                                    {"label": "dark"},
                                    {"label": "dim"},
                                    {"label": "ok"},
                                    {"label": "bright"},
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        signal_bucket=lambda room_id, signal_name: None,
        room_occupancy_age_s=lambda room_id: None,
    )

    reaction = build_room_contextual_lighting_assist_reaction(
        engine,
        "contextual-test",
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "profiles": {
                "day_generic": {
                    "entity_steps": [{"entity_id": "light.studio_desk", "action": "on"}]
                }
            },
            "rules": [],
            "default_profile": "day_generic",
            "ambient_modulation": {
                "source_signal_name": "outdoor_lux",
                "mode": "brightness_multiplier",
                "buckets": {"bright": "bad-number"},
            },
        },
    )

    assert reaction is None
