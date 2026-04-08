"""Tests for HeatingRecorderBehavior (learning system P3)."""

from __future__ import annotations

import asyncio

from custom_components.heima.runtime.behaviors.heating_recorder import HeatingRecorderBehavior
from custom_components.heima.runtime.context_builder import ContextBuilder
from custom_components.heima.runtime.event_store import HeimaEvent
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _FakeStore:
    def __init__(self) -> None:
        self.events = []

    async def async_append(self, event):
        self.events.append(event)


class _FakeState:
    def __init__(self, state: str, attributes: dict | None = None) -> None:
        self.state = state
        self.attributes = attributes or {}


class _FakeStates:
    def __init__(self, states: dict) -> None:
        self._states = states

    def get(self, entity_id: str):
        return self._states.get(entity_id)


class _FakeHass:
    def __init__(self, states: dict | None = None) -> None:
        self.tasks = []
        self.states = _FakeStates(states or {})

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


def _builder(hass, *, signal_entities: list[str] | None = None) -> ContextBuilder:
    return ContextBuilder(hass, {"context_signal_entities": signal_entities or []})


def _snapshot(
    *,
    ts: str = "2026-03-10T08:00:00+00:00",
    house_state: str = "home",
    heating_setpoint: float | None = 21.0,
    heating_source: str = "heima",
) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="s",
        ts=ts,
        house_state=house_state,
        anyone_home=True,
        people_count=1,
        occupied_rooms=[],
        lighting_intents={},
        security_state="disarmed",
        heating_setpoint=heating_setpoint,
        heating_source=heating_source,
        heating_provenance=None,
    )


async def test_heating_recorder_records_on_setpoint_change():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass))  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(ts="2026-03-10T08:00:00+00:00", heating_setpoint=20.0))
    behavior.on_snapshot(_snapshot(ts="2026-03-10T09:00:00+00:00", heating_setpoint=22.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 2
    assert all(isinstance(e, HeimaEvent) for e in store.events)
    assert store.events[0].data["temperature_set"] == 20.0
    assert store.events[1].data["temperature_set"] == 22.0


async def test_heating_recorder_no_event_on_stable():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass))  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="home"))
    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="home"))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1


async def test_heating_recorder_no_event_when_setpoint_none():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass))  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=None))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 0


async def test_heating_recorder_records_on_house_state_change():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass))  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="home"))
    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="away"))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 2
    assert store.events[0].context.house_state == "home"
    assert store.events[1].context.house_state == "away"


async def test_heating_recorder_reads_signal_entities():
    states = {
        "sensor.outdoor_temp": _FakeState("12.5"),
    }
    hass = _FakeHass(states=states)
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass, signal_entities=["sensor.outdoor_temp"]))  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1
    assert store.events[0].context.signals.get("sensor.outdoor_temp") == "12.5"


async def test_heating_recorder_skips_unavailable_entity():
    hass = _FakeHass(states={})
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass, signal_entities=["sensor.missing"]))  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1
    assert "sensor.missing" not in store.events[0].context.signals


async def test_heating_recorder_reads_weather_condition():
    states = {
        "weather.home": _FakeState(
            "sunny",
            attributes={"temperature": 15.0},
        ),
    }
    hass = _FakeHass(states=states)
    store = _FakeStore()
    builder = ContextBuilder(hass, {"weather_entity": "weather.home"})
    behavior = HeatingRecorderBehavior(hass, store, builder)  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1
    ctx = store.events[0].context
    assert ctx.weather_condition == "sunny"
    assert ctx.outdoor_temp == 15.0


async def test_heating_recorder_includes_provenance_when_present():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, _builder(hass))  # type: ignore[arg-type]

    behavior.on_snapshot(
        _snapshot(
            heating_setpoint=21.0,
            heating_source="heima",
            ts="2026-03-10T08:00:00+00:00",
        )
    )
    behavior._previous_setpoint = None
    behavior._previous_house_state = None
    behavior.on_snapshot(
        DecisionSnapshot(
            snapshot_id="s2",
            ts="2026-03-10T09:00:00+00:00",
            house_state="home",
            anyone_home=True,
            people_count=1,
            occupied_rooms=[],
            lighting_intents={},
            security_state="disarmed",
            heating_setpoint=21.0,
            heating_source="heima",
            heating_provenance={
                "source": "reaction:heat_pref_test",
                "origin_reaction_id": "heat_pref_test",
                "origin_reaction_class": "HeatingPreferenceReaction",
                "expected_domains": ["climate"],
                "expected_subject_ids": ["climate.test_thermostat"],
            },
        )
    )
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert store.events[-1].data["provenance"] == {
        "source": "reaction:heat_pref_test",
        "origin_reaction_id": "heat_pref_test",
        "origin_reaction_class": "HeatingPreferenceReaction",
        "expected_domains": ["climate"],
        "expected_subject_ids": ["climate.test_thermostat"],
    }
