"""Tests for SignalRecorderBehavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

from custom_components.heima.runtime.behaviors.signal_recorder import SignalRecorderBehavior
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.snapshot import DecisionSnapshot

_TS = "2026-03-10T08:00:00+00:00"
_LAST_CHANGED = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)


class _FakeStore:
    def __init__(self) -> None:
        self.events: list[HeimaEvent] = []

    async def async_append(self, event: HeimaEvent) -> None:
        self.events.append(event)


class _FakeBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def async_listen(self, event_type: str, callback) -> callable:
        self._handlers.setdefault(event_type, []).append(callback)

        def _unsub():
            handlers = self._handlers.get(event_type, [])
            if callback in handlers:
                handlers.remove(callback)

        return _unsub


class _FakeHass:
    def __init__(self) -> None:
        self.tasks: list = []
        self.bus = _FakeBus()

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def flush(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks)
            self.tasks.clear()


class _FakeEntry:
    def __init__(self, options: dict | None = None) -> None:
        self.options = options or {}


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


def _snapshot(house_state: str = "home") -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="s",
        ts=_TS,
        house_state=house_state,
        anyone_home=True,
        people_count=1,
        occupied_rooms=["bathroom"],
        lighting_intents={},
        security_state="disarmed",
    )


def _state_event(
    entity_id: str,
    new_state: str,
    old_state: str | None = None,
    *,
    context_id: str | None = None,
    attributes: dict | None = None,
) -> object:
    new = MagicMock()
    new.state = new_state
    new.attributes = attributes or {}
    new.last_changed = _LAST_CHANGED
    new.context = MagicMock(id=context_id) if context_id else None

    old = None
    if old_state is not None:
        old = MagicMock()
        old.state = old_state

    event = MagicMock()
    event.data = {
        "entity_id": entity_id,
        "new_state": new,
        "old_state": old,
    }
    return event


def _behavior(
    hass: _FakeHass,
    store: _FakeStore,
    *,
    options: dict | None = None,
    apply_state: dict | None = None,
) -> SignalRecorderBehavior:
    behavior = SignalRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(options),  # type: ignore[arg-type]
        lambda: apply_state or {"scripts": {}},
    )
    behavior._last_snapshot = _snapshot()
    return behavior


async def test_signal_recorder_records_tracked_signal_state_change():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={"learning": {"context_signal_entities": ["sensor.bathroom_humidity"]}},
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(
        _state_event("sensor.bathroom_humidity", "68", "55", attributes={"unit_of_measurement": "%"})
    )
    await hass.flush()

    assert len(store.events) == 1
    event = store.events[0]
    assert event.event_type == "state_change"
    assert event.domain == "sensor"
    assert event.subject_id == "sensor.bathroom_humidity"
    assert event.data["old_state"] == "55"
    assert event.data["new_state"] == "68"
    assert event.data["unit_of_measurement"] == "%"


async def test_signal_recorder_ignores_untracked_entity():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={"learning": {"context_signal_entities": ["sensor.other"]}},
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(_state_event("sensor.bathroom_humidity", "68", "55"))
    await hass.flush()

    assert store.events == []


async def test_signal_recorder_maps_room_from_room_sources():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={
            "learning": {"context_signal_entities": ["sensor.bathroom_humidity"]},
            "rooms": [
                {
                    "room_id": "bathroom",
                    "learning_sources": ["sensor.bathroom_humidity"],
                }
            ],
        },
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(_state_event("sensor.bathroom_humidity", "68", "55"))
    await hass.flush()

    assert store.events[0].room_id == "bathroom"


async def test_signal_recorder_tracks_room_learning_sources_without_global_extra():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={
            "learning": {"context_signal_entities": []},
            "rooms": [
                {
                    "room_id": "bathroom",
                    "occupancy_sources": ["binary_sensor.bathroom_motion"],
                    "learning_sources": ["sensor.bathroom_humidity"],
                }
            ],
        },
    )
    behavior._refresh_config()

    assert behavior.diagnostics()["tracked_entities"] == ["sensor.bathroom_humidity"]

    await behavior._handle_state_changed(_state_event("sensor.bathroom_humidity", "68", "55"))
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].room_id == "bathroom"


async def test_signal_recorder_uses_context_id_as_correlation_id():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={"learning": {"context_signal_entities": ["sensor.bathroom_humidity"]}},
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(
        _state_event("sensor.bathroom_humidity", "68", "55", context_id="ctx-signal-1")
    )
    await hass.flush()

    assert store.events[0].correlation_id == "ctx-signal-1"


async def test_signal_recorder_ignores_recent_heima_script_apply_for_same_room():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={
            "learning": {"context_signal_entities": ["switch.bathroom_fan"]},
            "rooms": [{"room_id": "bathroom", "learning_sources": ["switch.bathroom_fan"]}],
        },
        apply_state={
            "scripts": {
                "script.bathroom_fan": {
                    "script_entity": "script.bathroom_fan",
                    "room_id": "bathroom",
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "script-apply:1",
                    "source": "reaction:test",
                    "origin_reaction_id": "test",
                    "origin_reaction_class": "RoomSignalAssistReaction",
                    "expected_domains": ["switch"],
                    "expected_subject_ids": ["switch.bathroom_fan"],
                    "expected_entity_ids": [],
                }
            }
        },
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(_state_event("switch.bathroom_fan", "on", "off"))
    await hass.flush()

    assert store.events == []


async def test_signal_recorder_does_not_ignore_recent_heima_script_apply_for_other_room():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={
            "learning": {"context_signal_entities": ["switch.studio_fan"]},
            "rooms": [{"room_id": "studio", "learning_sources": ["switch.studio_fan"]}],
        },
        apply_state={
            "scripts": {
                "script.bathroom_fan": {
                    "script_entity": "script.bathroom_fan",
                    "room_id": "bathroom",
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "script-apply:2",
                    "source": "reaction:test",
                    "origin_reaction_id": "test",
                    "origin_reaction_class": "RoomSignalAssistReaction",
                    "expected_domains": ["switch"],
                    "expected_subject_ids": ["switch.bathroom_fan"],
                    "expected_entity_ids": [],
                }
            }
        },
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(_state_event("switch.studio_fan", "on", "off"))
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].subject_id == "switch.studio_fan"


async def test_signal_recorder_uses_expected_domains_with_room_scope():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={
            "learning": {"context_signal_entities": ["switch.studio_fan", "sensor.studio_co2"]},
            "rooms": [
                {
                    "room_id": "studio",
                    "learning_sources": ["switch.studio_fan", "sensor.studio_co2"],
                }
            ],
        },
        apply_state={
            "scripts": {
                "script.studio_fan": {
                    "script_entity": "script.studio_fan",
                    "room_id": "studio",
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "script-apply:3",
                    "source": "reaction:test",
                    "origin_reaction_id": "test",
                    "origin_reaction_class": "RoomSignalAssistReaction",
                    "expected_domains": ["switch"],
                    "expected_subject_ids": [],
                    "expected_entity_ids": [],
                }
            }
        },
    )
    behavior._refresh_config()

    await behavior._handle_state_changed(_state_event("sensor.studio_co2", "940", "700"))
    await behavior._handle_state_changed(_state_event("switch.studio_fan", "on", "off"))
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].subject_id == "sensor.studio_co2"


async def test_signal_recorder_async_setup_subscribes_when_tracked_entities_exist():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(
        hass,
        store,
        options={"learning": {"context_signal_entities": ["sensor.bathroom_humidity"]}},
    )

    await behavior.async_setup()

    assert behavior._unsub is not None


async def test_signal_recorder_on_options_reloaded_updates_tracked_entities():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = _behavior(hass, store, options={"learning": {"context_signal_entities": ["sensor.old"]}})
    behavior._refresh_config()

    behavior.on_options_reloaded(
        {"learning": {"context_signal_entities": ["sensor.new"]}, "rooms": []}
    )

    assert behavior.diagnostics()["tracked_entities"] == ["sensor.new"]
