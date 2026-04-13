"""Tests for ActuationRecorderBehavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from custom_components.heima.runtime.behaviors.actuation_recorder import (
    ActuationRecorderBehavior,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.snapshot import DecisionSnapshot

_LAST_CHANGED = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)


class _FakeState:
    def __init__(self, state: str, *, last_changed: datetime | None = None) -> None:
        self.state = state
        self.attributes = {}
        self.last_changed = last_changed or _LAST_CHANGED


class _FakeStore:
    def __init__(self) -> None:
        self.events: list[HeimaEvent] = []

    async def async_append(self, event: HeimaEvent) -> None:
        self.events.append(event)


class _FakeBus:
    def async_listen(self, event_type: str, callback):  # noqa: ARG002
        return lambda: None


class _FakeStateMachine:
    def get(self, entity_id: str):  # noqa: ARG002
        return None


class _FakeHass:
    def __init__(self) -> None:
        self.tasks: list = []
        self.bus = _FakeBus()
        self.states = _FakeStateMachine()

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def flush(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks)
            self.tasks.clear()


class _FakeEntry:
    def __init__(self) -> None:
        self.options = {}


class _FakeContextBuilder:
    def build(self, snapshot: DecisionSnapshot) -> EventContext:
        return EventContext(
            weekday=0,
            minute_of_day=480,
            month=3,
            house_state=snapshot.house_state,
            occupants_count=snapshot.people_count,
            occupied_rooms=tuple(snapshot.occupied_rooms),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        )


def _snapshot() -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="s",
        ts="2026-03-10T08:00:00+00:00",
        house_state="home",
        anyone_home=True,
        people_count=1,
        occupied_rooms=["studio"],
        lighting_intents={},
        security_state="disarmed",
    )


def _state_event(entity_id: str, new_state: _FakeState, old_state: _FakeState | None) -> object:
    class _Event:
        data = {
            "entity_id": entity_id,
            "new_state": new_state,
            "old_state": old_state,
        }

    return _Event()


async def test_actuation_recorder_records_fan_on_event():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = ActuationRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
    )
    behavior._entity_to_room = {"fan.studio_fan": "studio"}  # noqa: SLF001
    behavior.on_snapshot(_snapshot())

    await behavior._handle_state_changed(  # noqa: SLF001
        _state_event("fan.studio_fan", _FakeState("on"), _FakeState("off"))
    )
    await hass.flush()

    assert len(store.events) == 1
    event = store.events[0]
    assert event.event_type == "actuation"
    assert event.domain == "fan"
    assert event.subject_id == "fan.studio_fan"
    assert event.room_id == "studio"
    assert event.data["action"] == "on"


async def test_actuation_recorder_records_climate_mode_event():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = ActuationRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
    )
    behavior._entity_to_room = {"climate.studio": "studio"}  # noqa: SLF001
    behavior.on_snapshot(_snapshot())

    await behavior._handle_state_changed(  # noqa: SLF001
        _state_event("climate.studio", _FakeState("cool"), _FakeState("off"))
    )
    await hass.flush()

    assert len(store.events) == 1
    event = store.events[0]
    assert event.event_type == "actuation"
    assert event.domain == "climate"
    assert event.data["action"] == "cool"


async def test_actuation_recorder_ignores_unchanged_state():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = ActuationRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
    )
    behavior._entity_to_room = {"switch.studio_aux": "studio"}  # noqa: SLF001
    behavior.on_snapshot(_snapshot())

    await behavior._handle_state_changed(  # noqa: SLF001
        _state_event("switch.studio_aux", _FakeState("on"), _FakeState("on"))
    )
    await hass.flush()

    assert store.events == []
