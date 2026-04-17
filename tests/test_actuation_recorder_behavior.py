"""Tests for ActuationRecorderBehavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

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
    def __init__(self) -> None:
        self.listeners: list[tuple[str, object]] = []
        self.unsubscribed = 0

    def async_listen(self, event_type: str, callback):  # noqa: ARG002
        self.listeners.append((event_type, callback))

        def _unsub() -> None:
            self.unsubscribed += 1

        return _unsub


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


def _state_event_with_context(
    entity_id: str,
    new_state: _FakeState,
    old_state: _FakeState | None,
    *,
    event_context: dict | None = None,
) -> object:
    class _Event:
        data = {
            "entity_id": entity_id,
            "new_state": new_state,
            "old_state": old_state,
            "context": event_context,
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


async def test_actuation_recorder_ignores_non_actuator_entities():
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
        _state_event("light.studio", _FakeState("on"), _FakeState("off"))
    )
    await hass.flush()

    assert store.events == []


async def test_actuation_recorder_ignores_event_without_snapshot_or_room():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = ActuationRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
    )

    await behavior._handle_state_changed(  # noqa: SLF001
        _state_event("switch.studio_aux", _FakeState("on"), _FakeState("off"))
    )
    await hass.flush()
    assert store.events == []

    behavior.on_snapshot(_snapshot())
    await behavior._handle_state_changed(  # noqa: SLF001
        _state_event("switch.studio_aux", _FakeState("on"), _FakeState("off"))
    )
    await hass.flush()
    assert store.events == []


async def test_actuation_recorder_ignores_unsupported_switch_state():
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
        _state_event("switch.studio_aux", _FakeState("unavailable"), _FakeState("off"))
    )
    await hass.flush()

    assert store.events == []


async def test_actuation_recorder_uses_new_state_context_id_as_correlation_id():
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
    new_state = _FakeState("off")
    new_state.context = SimpleNamespace(id="ctx-new")

    await behavior._handle_state_changed(  # noqa: SLF001
        _state_event_with_context(
            "switch.studio_aux",
            new_state,
            _FakeState("on"),
            event_context={"id": "ctx-event"},
        )
    )
    await hass.flush()

    assert store.events[0].correlation_id == "ctx-new"


async def test_actuation_recorder_falls_back_to_event_context_id():
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
        _state_event_with_context(
            "switch.studio_aux",
            _FakeState("off"),
            _FakeState("on"),
            event_context={"id": "ctx-event"},
        )
    )
    await hass.flush()

    assert store.events[0].correlation_id == "ctx-event"


def test_actuation_recorder_syncs_listener_subscription():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = ActuationRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
    )

    behavior._entity_to_room = {"fan.studio_fan": "studio"}  # noqa: SLF001
    behavior._sync_listener_subscription()  # noqa: SLF001
    assert len(hass.bus.listeners) == 1

    behavior._entity_to_room = {}  # noqa: SLF001
    behavior._sync_listener_subscription()  # noqa: SLF001
    assert hass.bus.unsubscribed == 1


def test_actuation_recorder_builds_entity_room_map_from_entity_and_device_area(monkeypatch):
    hass = _FakeHass()
    entry = _FakeEntry()
    entry.options = {
        "rooms": [
            {"room_id": "studio", "area_id": "area_studio"},
            {"room_id": "living", "area_id": "area_living"},
        ]
    }
    behavior = ActuationRecorderBehavior(
        hass,  # type: ignore[arg-type]
        _FakeStore(),  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        entry,  # type: ignore[arg-type]
    )
    entity_registry = SimpleNamespace(
        entities={
            "fan.studio_fan": SimpleNamespace(
                entity_id="fan.studio_fan",
                area_id="area_studio",
                device_id=None,
            ),
            "switch.living_aux": SimpleNamespace(
                entity_id="switch.living_aux",
                area_id=None,
                device_id="dev-1",
            ),
            "sensor.ignore": SimpleNamespace(
                entity_id="sensor.ignore",
                area_id="area_studio",
                device_id=None,
            ),
        }
    )
    device_registry = SimpleNamespace(
        devices={"dev-1": SimpleNamespace(area_id="area_living")}
    )

    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: device_registry,
    )

    result = behavior._build_entity_room_map()  # noqa: SLF001

    assert result == {
        "fan.studio_fan": "studio",
        "switch.living_aux": "living",
    }
