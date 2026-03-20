"""Tests for RoomSignalAssistReaction."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.signal_assist import RoomSignalAssistReaction
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, occupied_rooms: list[str], ts: str) -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    return replace(base, ts=ts, occupied_rooms=occupied_rooms)


def _set_state(hass, entity_id: str, state: str) -> None:
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state=state) if eid == entity_id else None


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
    steps = reaction.evaluate([
        _snapshot(occupied_rooms=["bathroom"], ts=ts1),
        _snapshot(occupied_rooms=["bathroom"], ts=ts2),
    ])
    assert len(steps) == 1
    assert steps[0].action == "script.turn_on"


def test_signal_assist_reaction_waits_for_temperature_corroboration():
    hass = MagicMock()
    states = {
        "sensor.bathroom_humidity": "55",
        "sensor.bathroom_temperature": "21.0",
    }
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
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
    assert reaction.evaluate([
        _snapshot(occupied_rooms=["bathroom"], ts=ts1),
        _snapshot(occupied_rooms=["bathroom"], ts=ts2),
    ]) == []

    states["sensor.bathroom_temperature"] = "22.0"
    steps = reaction.evaluate([
        _snapshot(occupied_rooms=["bathroom"], ts=ts2),
        _snapshot(occupied_rooms=["bathroom"], ts=ts3),
    ])
    assert len(steps) == 1
    assert steps[0].action == "script.turn_on"


def test_signal_assist_reaction_supports_generic_primary_and_corroboration_signals():
    hass = MagicMock()
    states = {
        "sensor.studio_temperature": "24.0",
        "sensor.studio_humidity": "50.0",
    }
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    reaction = RoomSignalAssistReaction(
        hass=hass,
        room_id="studio",
        trigger_signal_entities=["sensor.studio_temperature"],
        primary_signal_entities=["sensor.studio_temperature"],
        primary_rise_threshold=1.5,
        primary_signal_name="temperature",
        corroboration_signal_entities=["sensor.studio_humidity"],
        corroboration_rise_threshold=5.0,
        corroboration_signal_name="humidity",
        steps=[ApplyStep(domain="script", target="script.cool_room", action="script.turn_on")],
        followup_window_s=0,
    )
    ts1 = datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2026, 3, 20, 15, 2, tzinfo=timezone.utc).isoformat()
    ts3 = datetime(2026, 3, 20, 15, 4, tzinfo=timezone.utc).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)]) == []

    states["sensor.studio_temperature"] = "25.8"
    assert reaction.evaluate([
        _snapshot(occupied_rooms=["studio"], ts=ts1),
        _snapshot(occupied_rooms=["studio"], ts=ts2),
    ]) == []

    states["sensor.studio_humidity"] = "56.0"
    steps = reaction.evaluate([
        _snapshot(occupied_rooms=["studio"], ts=ts2),
        _snapshot(occupied_rooms=["studio"], ts=ts3),
    ])
    assert len(steps) == 1
    assert steps[0].target == "script.cool_room"
