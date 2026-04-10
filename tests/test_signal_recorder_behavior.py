"""Tests for EventCanonicalizer (backward-compat filename kept intentionally)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from custom_components.heima.runtime.behaviors.event_canonicalizer import EventCanonicalizer
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.snapshot import DecisionSnapshot

_LAST_CHANGED = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)


class _FakeState:
    def __init__(
        self,
        state: str,
        *,
        device_class: str | None = None,
        last_changed: datetime | None = None,
    ) -> None:
        self.state = state
        self.attributes = {"device_class": device_class} if device_class else {}
        self.last_changed = last_changed or _LAST_CHANGED


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


class _FakeStateMachine:
    def __init__(self, mapping: dict[str, _FakeState]) -> None:
        self._mapping = mapping

    def get(self, entity_id: str):
        return self._mapping.get(entity_id)


class _FakeHass:
    def __init__(self, states: dict[str, _FakeState]) -> None:
        self.tasks: list = []
        self.bus = _FakeBus()
        self.states = _FakeStateMachine(states)

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


def _state_event(entity_id: str, new_state: _FakeState) -> object:
    class _Event:
        data = {
            "entity_id": entity_id,
            "new_state": new_state,
            "old_state": None,
        }

    return _Event()


def _behavior(
    *,
    states: dict[str, _FakeState],
    options: dict,
) -> tuple[_FakeHass, _FakeStore, EventCanonicalizer]:
    hass = _FakeHass(states)
    store = _FakeStore()
    behavior = EventCanonicalizer(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(options),  # type: ignore[arg-type]
    )
    return hass, store, behavior


async def test_event_canonicalizer_tracks_room_learning_source_with_default_buckets():
    hass, _store, behavior = _behavior(
        states={"sensor.studio_lux": _FakeState("180", device_class="illuminance")},
        options={
            "rooms": [{"room_id": "studio", "learning_sources": ["sensor.studio_lux"]}],
            "learning": {},
        },
    )

    await behavior.async_setup()

    diag = behavior.diagnostics()
    assert "sensor.studio_lux" in diag["tracked_entities"]
    tracked = diag["tracked_entities"]["sensor.studio_lux"]
    assert tracked["room_id"] == "studio"
    assert tracked["signal_name"] == "room_lux"
    assert tracked["device_class"] == "illuminance"
    await hass.flush()


async def test_event_canonicalizer_emits_room_signal_threshold_on_bucket_crossing():
    state = _FakeState("180", device_class="illuminance")
    hass, store, behavior = _behavior(
        states={"sensor.studio_lux": state},
        options={
            "rooms": [{"room_id": "studio", "learning_sources": ["sensor.studio_lux"]}],
            "learning": {},
        },
    )
    behavior.on_snapshot(_snapshot())
    await behavior.async_setup()

    state.state = "20"
    state.last_changed = datetime(2026, 3, 10, 8, 5, 0, tzinfo=timezone.utc)
    await behavior._handle_state_changed(_state_event("sensor.studio_lux", state))
    await hass.flush()

    assert len(store.events) == 1
    event = store.events[0]
    assert event.event_type == "room_signal_threshold"
    assert event.room_id == "studio"
    assert event.subject_type == "signal"
    assert event.subject_id == "room_lux"
    assert event.source is None
    assert event.data["from_bucket"] == "ok"
    assert event.data["to_bucket"] == "dark"
    assert event.data["direction"] == "down"


async def test_event_canonicalizer_ignores_intra_bucket_noise():
    state = _FakeState("20", device_class="illuminance")
    hass, store, behavior = _behavior(
        states={"sensor.studio_lux": state},
        options={
            "rooms": [{"room_id": "studio", "learning_sources": ["sensor.studio_lux"]}],
            "learning": {},
        },
    )
    behavior.on_snapshot(_snapshot())
    await behavior.async_setup()

    state.state = "25"
    await behavior._handle_state_changed(_state_event("sensor.studio_lux", state))
    await hass.flush()

    assert store.events == []


async def test_event_canonicalizer_periodic_sync_emits_when_bucket_state_drifted():
    state = _FakeState("180", device_class="illuminance")
    hass, store, behavior = _behavior(
        states={"sensor.studio_lux": state},
        options={
            "rooms": [{"room_id": "studio", "learning_sources": ["sensor.studio_lux"]}],
            "learning": {},
        },
    )
    await behavior.async_setup()
    state.state = "20"

    behavior.on_snapshot(_snapshot())
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].source == "periodic_sync"
    assert store.events[0].data["to_bucket"] == "dark"


async def test_event_canonicalizer_uses_explicit_room_signal_config():
    state = _FakeState("950", device_class="carbon_dioxide")
    hass, _store, behavior = _behavior(
        states={"sensor.studio_co2": state},
        options={
            "rooms": [
                {
                    "room_id": "studio",
                    "signals": [
                        {
                            "entity_id": "sensor.studio_co2",
                            "signal_name": "room_co2",
                            "device_class": "carbon_dioxide",
                            "buckets": [
                                {"label": "ok", "upper_bound": 800},
                                {"label": "elevated", "upper_bound": 1200},
                                {"label": "high", "upper_bound": None},
                            ],
                        }
                    ],
                }
            ]
        },
    )

    await behavior.async_setup()

    diag = behavior.diagnostics()
    assert diag["tracked_entities"]["sensor.studio_co2"]["signal_name"] == "room_co2"
    assert diag["bucket_state"]["studio:room_co2"] == "elevated"
    await hass.flush()
