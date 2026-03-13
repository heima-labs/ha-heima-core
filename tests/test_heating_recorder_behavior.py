"""Tests for HeatingRecorderBehavior (learning system P3)."""

from __future__ import annotations

import asyncio

from custom_components.heima.runtime.behaviors.heating_recorder import HeatingRecorderBehavior
from custom_components.heima.runtime.event_store import HeatingEvent
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
    )


async def test_heating_recorder_records_on_setpoint_change():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store)  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(ts="2026-03-10T08:00:00+00:00", heating_setpoint=20.0))
    behavior.on_snapshot(_snapshot(ts="2026-03-10T09:00:00+00:00", heating_setpoint=22.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 2
    assert all(isinstance(e, HeatingEvent) for e in store.events)
    assert store.events[0].temperature_set == 20.0
    assert store.events[1].temperature_set == 22.0


async def test_heating_recorder_no_event_on_stable():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store)  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="home"))
    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="home"))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    # First snapshot always records (prev_setpoint is None), second is stable → no new event
    assert len(store.events) == 1


async def test_heating_recorder_no_event_when_setpoint_none():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store)  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=None))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 0


async def test_heating_recorder_records_on_house_state_change():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store)  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="home"))
    behavior.on_snapshot(_snapshot(heating_setpoint=21.0, house_state="away"))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    # Both snapshots differ (first has prev_setpoint=None, second differs by house_state)
    assert len(store.events) == 2
    assert store.events[0].house_state == "home"
    assert store.events[1].house_state == "away"


async def test_heating_recorder_reads_env_entities():
    states = {
        "sensor.outdoor_temp": _FakeState("12.5"),
    }
    hass = _FakeHass(states=states)
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, context_entities=["sensor.outdoor_temp"])  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1
    assert store.events[0].env.get("sensor.outdoor_temp") == "12.5"


async def test_heating_recorder_skips_unavailable_entity():
    hass = _FakeHass(states={})  # entity not present
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, context_entities=["sensor.missing"])  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1
    assert "sensor.missing" not in store.events[0].env


async def test_heating_recorder_expands_weather_entity():
    states = {
        "weather.home": _FakeState(
            "sunny",
            attributes={"temperature": 15.0, "humidity": 60, "wind_speed": 10.5},
        ),
    }
    hass = _FakeHass(states=states)
    store = _FakeStore()
    behavior = HeatingRecorderBehavior(hass, store, context_entities=["weather.home"])  # type: ignore[arg-type]

    behavior.on_snapshot(_snapshot(heating_setpoint=21.0))
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert len(store.events) == 1
    env = store.events[0].env
    assert env.get("weather.home") == "sunny"
    assert env.get("weather.home.temperature") == "15.0"
    assert env.get("weather.home.humidity") == "60"
    assert env.get("weather.home.wind_speed") == "10.5"
