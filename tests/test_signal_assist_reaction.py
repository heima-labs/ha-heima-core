"""Tests for RoomSignalAssistReaction."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.signal_assist import (
    RoomSignalAssistReaction,
    build_room_cooling_assist_reaction,
    build_room_signal_assist_reaction,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, occupied_rooms: list[str], ts: str) -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    return replace(base, ts=ts, occupied_rooms=occupied_rooms)


def _set_state(hass, entity_id: str, state: str) -> None:
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=state) if eid == entity_id else None
    )


def test_signal_assist_reaction_fires_on_humidity_burst_without_temp_requirement():
    hass = MagicMock()
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="bathroom",
        trigger_signal_entities=["sensor.bathroom_humidity"],
        steps=[ApplyStep(domain="script", target="script.fan_on", action="script.turn_on")],
        humidity_rise_threshold=8.0,
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 8, 5, tzinfo=timezone.utc).isoformat()

    _set_state(hass, "sensor.bathroom_humidity", "55")
    assert reaction.evaluate([_snapshot(occupied_rooms=["bathroom"], ts=ts1)]) == []

    _set_state(hass, "sensor.bathroom_humidity", "64")
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["bathroom"], ts=ts1),
            _snapshot(occupied_rooms=["bathroom"], ts=ts2),
        ]
    )
    assert len(steps) == 1
    assert steps[0].action == "script.turn_on"


def test_signal_assist_reaction_waits_for_temperature_corroboration():
    hass = MagicMock()
    states = {
        "sensor.bathroom_humidity": "55",
        "sensor.bathroom_temperature": "21.0",
    }
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="bathroom",
        trigger_signal_entities=["sensor.bathroom_humidity"],
        temperature_signal_entities=["sensor.bathroom_temperature"],
        steps=[ApplyStep(domain="script", target="script.fan_on", action="script.turn_on")],
        humidity_rise_threshold=8.0,
        temperature_rise_threshold=0.8,
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 8, 2, tzinfo=timezone.utc).isoformat()
    ts3 = datetime(2026, 3, 20, 8, 4, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["bathroom"], ts=ts1)]) == []

    states["sensor.bathroom_humidity"] = "64"
    assert (
        reaction.evaluate(
            [
                _snapshot(occupied_rooms=["bathroom"], ts=ts1),
                _snapshot(occupied_rooms=["bathroom"], ts=ts2),
            ]
        )
        == []
    )

    states["sensor.bathroom_temperature"] = "22.0"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["bathroom"], ts=ts2),
            _snapshot(occupied_rooms=["bathroom"], ts=ts3),
        ]
    )
    assert len(steps) == 1
    assert steps[0].action == "script.turn_on"


def test_room_cooling_assist_reaction_uses_burst_recent_for_primary_and_corroboration():
    hass = MagicMock()
    burst_state = {
        ("studio", "room_temperature"): False,
        ("studio", "room_humidity"): False,
    }

    def _burst_getter(room_id: str, signal_name: str, *, window_s: int) -> bool:
        assert window_s == 900
        return burst_state.get((room_id, signal_name), False)

    reaction = RoomSignalAssistReaction(
        hass=hass,
        burst_getter=_burst_getter,
        use_burst_accessor=True,
        room_id="studio",
        primary_signal_entities=["sensor.studio_temperature"],
        primary_signal_name="room_temperature",
        corroboration_signal_entities=["sensor.studio_humidity"],
        corroboration_signal_name="room_humidity",
        steps=[ApplyStep(domain="script", target="script.cool_room", action="script.turn_on")],
        followup_window_s=900,
    )
    ts1 = datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 15, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)]) == []

    burst_state[("studio", "room_temperature")] = True
    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2)]) == []

    burst_state[("studio", "room_humidity")] = True
    steps = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2)])
    assert len(steps) == 1
    assert steps[0].target == "script.cool_room"


def test_room_cooling_assist_reaction_supports_burst_without_corroboration():
    hass = MagicMock()
    burst_state = {("office", "room_temperature"): False}

    def _burst_getter(room_id: str, signal_name: str, *, window_s: int) -> bool:
        assert window_s == 900
        return burst_state.get((room_id, signal_name), False)

    reaction = RoomSignalAssistReaction(
        hass=hass,
        burst_getter=_burst_getter,
        use_burst_accessor=True,
        room_id="office",
        primary_signal_entities=["sensor.office_temperature"],
        primary_signal_name="room_temperature",
        steps=[ApplyStep(domain="script", target="script.cool_office", action="script.turn_on")],
        followup_window_s=900,
    )
    ts1 = datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 15, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts1)]) == []

    burst_state[("office", "room_temperature")] = True
    steps = reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts2)])
    assert len(steps) == 1
    assert steps[0].target == "script.cool_office"


def test_room_cooling_assist_reaction_counts_suppression_during_cooldown():
    hass = MagicMock()
    burst_state = {
        ("studio", "room_temperature"): True,
        ("studio", "room_humidity"): True,
    }

    def _burst_getter(room_id: str, signal_name: str, *, window_s: int) -> bool:
        assert window_s == 900
        return burst_state.get((room_id, signal_name), False)

    reaction = RoomSignalAssistReaction(
        hass=hass,
        burst_getter=_burst_getter,
        use_burst_accessor=True,
        room_id="studio",
        primary_signal_entities=["sensor.studio_temperature"],
        primary_signal_name="room_temperature",
        corroboration_signal_entities=["sensor.studio_humidity"],
        corroboration_signal_name="room_humidity",
        steps=[ApplyStep(domain="script", target="script.cool_room", action="script.turn_on")],
        followup_window_s=900,
    )
    ts1 = datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 15, 2, tzinfo=timezone.utc).isoformat()

    first = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)])
    assert len(first) == 1

    second = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2)])
    assert second == []
    assert reaction.diagnostics()["suppressed_count"] == 1


def test_signal_assist_reaction_supports_above_mode():
    hass = MagicMock()
    states = {"sensor.office_co2": "780.0"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="office",
        primary_signal_entities=["sensor.office_co2"],
        primary_threshold=800.0,
        primary_threshold_mode="above",
        primary_signal_name="co2",
        steps=[
            ApplyStep(domain="script", target="script.ventilate_office", action="script.turn_on")
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 15, 2, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts1)]) == []

    states["sensor.office_co2"] = "820.0"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["office"], ts=ts1),
            _snapshot(occupied_rooms=["office"], ts=ts2),
        ]
    )
    assert len(steps) == 1
    assert steps[0].target == "script.ventilate_office"


def test_signal_assist_reaction_supports_switch_on_mode():
    hass = MagicMock()
    states = {"binary_sensor.projector_active": "off"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="living",
        primary_signal_entities=["binary_sensor.projector_active"],
        primary_threshold=1.0,
        primary_threshold_mode="switch_on",
        primary_signal_name="projector",
        steps=[
            ApplyStep(domain="script", target="script.projector_scene", action="script.turn_on")
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 21, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 21, 1, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []
    states["binary_sensor.projector_active"] = "on"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )
    assert len(steps) == 1
    assert steps[0].target == "script.projector_scene"


def test_signal_assist_reaction_supports_switch_off_mode():
    hass = MagicMock()
    states = {"binary_sensor.projector_active": "on"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="living",
        primary_signal_entities=["binary_sensor.projector_active"],
        primary_threshold=1.0,
        primary_threshold_mode="switch_off",
        primary_signal_name="projector",
        steps=[ApplyStep(domain="script", target="script.restore_lights", action="script.turn_on")],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 22, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 22, 1, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["living"], ts=ts1)]) == []
    states["binary_sensor.projector_active"] = "off"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["living"], ts=ts1),
            _snapshot(occupied_rooms=["living"], ts=ts2),
        ]
    )
    assert len(steps) == 1
    assert steps[0].target == "script.restore_lights"


def test_signal_assist_reaction_supports_state_change_mode():
    hass = MagicMock()
    states = {"binary_sensor.window_open": "off"}
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=states[eid]) if eid in states else None
    )
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="studio",
        primary_signal_entities=["binary_sensor.window_open"],
        primary_threshold=1.0,
        primary_threshold_mode="state_change",
        primary_signal_name="window",
        steps=[ApplyStep(domain="script", target="script.window_changed", action="script.turn_on")],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 23, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 23, 1, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)]) == []
    states["binary_sensor.window_open"] = "on"
    steps = reaction.evaluate(
        [
            _snapshot(occupied_rooms=["studio"], ts=ts1),
            _snapshot(occupied_rooms=["studio"], ts=ts2),
        ]
    )
    assert len(steps) == 1
    assert steps[0].target == "script.window_changed"


def test_signal_assist_reaction_supports_canonical_primary_bucket_steady_state():
    hass = MagicMock()
    bucket_state = {"bathroom:room_humidity": "ok"}

    def _bucket_getter(room_id: str, signal_name: str) -> str | None:
        return bucket_state.get(f"{room_id}:{signal_name}")

    reaction = RoomSignalAssistReaction(
        hass=hass,
        bucket_getter=_bucket_getter,
        room_id="bathroom",
        primary_signal_entities=["sensor.bathroom_humidity"],
        primary_signal_name="room_humidity",
        primary_bucket="high",
        primary_bucket_labels=["low", "ok", "high"],
        steps=[ApplyStep(domain="script", target="script.fan_on", action="script.turn_on")],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 8, 1, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["bathroom"], ts=ts1)]) == []

    bucket_state["bathroom:room_humidity"] = "high"
    steps = reaction.evaluate([_snapshot(occupied_rooms=["bathroom"], ts=ts2)])
    assert len(steps) == 1
    assert steps[0].target == "script.fan_on"

    assert reaction.evaluate([_snapshot(occupied_rooms=["bathroom"], ts=ts2)]) == []


def test_signal_assist_reaction_supports_primary_bucket_lte_matching():
    hass = MagicMock()
    bucket_state = {"bathroom:room_humidity": "ok"}

    def _bucket_getter(room_id: str, signal_name: str) -> str | None:
        return bucket_state.get(f"{room_id}:{signal_name}")

    reaction = RoomSignalAssistReaction(
        hass=hass,
        bucket_getter=_bucket_getter,
        room_id="bathroom",
        primary_signal_entities=["sensor.bathroom_humidity"],
        primary_signal_name="room_humidity",
        primary_bucket="high",
        primary_bucket_match_mode="lte",
        primary_bucket_labels=["low", "ok", "high"],
        steps=[ApplyStep(domain="script", target="script.fan_on", action="script.turn_on")],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()

    steps = reaction.evaluate([_snapshot(occupied_rooms=["bathroom"], ts=ts1)])
    assert len(steps) == 1
    assert steps[0].target == "script.fan_on"


def test_signal_assist_reaction_requires_canonical_corroboration_bucket_when_configured():
    hass = MagicMock()
    bucket_state = {
        "office:room_co2": "elevated",
        "office:room_humidity": "ok",
    }

    def _bucket_getter(room_id: str, signal_name: str) -> str | None:
        return bucket_state.get(f"{room_id}:{signal_name}")

    reaction = RoomSignalAssistReaction(
        hass=hass,
        bucket_getter=_bucket_getter,
        room_id="office",
        primary_signal_entities=["sensor.office_co2"],
        primary_signal_name="room_co2",
        primary_bucket="elevated",
        primary_bucket_labels=["ok", "elevated", "high"],
        corroboration_signal_entities=["sensor.office_humidity"],
        corroboration_signal_name="room_humidity",
        corroboration_bucket="high",
        corroboration_bucket_labels=["low", "ok", "high"],
        steps=[
            ApplyStep(domain="script", target="script.ventilate_office", action="script.turn_on")
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 8, 1, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts1)]) == []

    bucket_state["office:room_humidity"] = "high"
    steps = reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts2)])
    assert len(steps) == 1
    assert steps[0].target == "script.ventilate_office"


def test_signal_assist_reaction_supports_corroboration_bucket_gte_matching():
    hass = MagicMock()
    bucket_state = {
        "office:room_co2": "high",
        "office:room_temperature": "hot",
    }

    def _bucket_getter(room_id: str, signal_name: str) -> str | None:
        return bucket_state.get(f"{room_id}:{signal_name}")

    reaction = RoomSignalAssistReaction(
        hass=hass,
        bucket_getter=_bucket_getter,
        room_id="office",
        primary_signal_entities=["sensor.office_co2"],
        primary_signal_name="room_co2",
        primary_bucket="elevated",
        primary_bucket_match_mode="gte",
        primary_bucket_labels=["ok", "elevated", "high"],
        corroboration_signal_entities=["sensor.office_temperature"],
        corroboration_signal_name="room_temperature",
        corroboration_bucket="warm",
        corroboration_bucket_match_mode="gte",
        corroboration_bucket_labels=["cool", "ok", "warm", "hot"],
        steps=[
            ApplyStep(domain="script", target="script.ventilate_office", action="script.turn_on")
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()

    steps = reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts1)])
    assert len(steps) == 1
    assert steps[0].target == "script.ventilate_office"


def test_signal_assist_reaction_resets_steady_state_when_corroboration_bucket_misses():
    hass = MagicMock()
    bucket_state = {
        "office:room_co2": "high",
        "office:room_temperature": "ok",
    }

    def _bucket_getter(room_id: str, signal_name: str) -> str | None:
        return bucket_state.get(f"{room_id}:{signal_name}")

    reaction = RoomSignalAssistReaction(
        hass=hass,
        bucket_getter=_bucket_getter,
        room_id="office",
        primary_signal_entities=["sensor.office_co2"],
        primary_signal_name="room_co2",
        primary_bucket="elevated",
        primary_bucket_match_mode="gte",
        primary_bucket_labels=["ok", "elevated", "high"],
        corroboration_signal_entities=["sensor.office_temperature"],
        corroboration_signal_name="room_temperature",
        corroboration_bucket="warm",
        corroboration_bucket_match_mode="gte",
        corroboration_bucket_labels=["cool", "ok", "warm", "hot"],
        steps=[
            ApplyStep(domain="script", target="script.ventilate_office", action="script.turn_on")
        ],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["office"], ts=ts1)]) == []
    assert reaction.diagnostics()["steady_condition_active"] is False


def test_build_room_signal_assist_reaction_allows_burst_trigger_without_primary_bucket():
    engine = SimpleNamespace(
        _hass=MagicMock(),
        signal_bucket=lambda room_id, signal_name: None,
        signal_burst_recent=lambda room_id, signal_name, *, window_s: False,
        _entry=SimpleNamespace(
            options={
                "rooms": [
                    {
                        "room_id": "bathroom",
                        "signals": [
                            {
                                "signal_name": "room_humidity",
                                "bucket_labels": ["low", "ok", "high"],
                            }
                        ],
                    }
                ]
            }
        ),
    )

    reaction = build_room_signal_assist_reaction(
        engine,
        "rx1",
        {
            "reaction_type": "room_signal_assist",
            "room_id": "bathroom",
            "primary_trigger_mode": "burst",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "primary_signal_name": "room_humidity",
            "steps": [{"domain": "script", "target": "script.fan_on", "action": "script.turn_on"}],
        },
    )

    assert reaction is not None
    assert reaction.diagnostics()["uses_burst_accessor"] is True


def test_build_room_cooling_assist_reaction_requires_primary_signal_entities():
    engine = SimpleNamespace(
        _hass=MagicMock(),
        signal_bucket=lambda room_id, signal_name: None,
        signal_burst_recent=lambda room_id, signal_name, *, window_s: False,
        _entry=SimpleNamespace(options={"rooms": []}),
    )

    reaction = build_room_cooling_assist_reaction(
        engine,
        "rx2",
        {
            "reaction_type": "room_cooling_assist",
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "steps": [{"domain": "script", "target": "script.cool_room", "action": "script.turn_on"}],
        },
    )

    assert reaction is None
