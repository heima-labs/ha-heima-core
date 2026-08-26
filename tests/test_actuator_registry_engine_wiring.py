"""Tests for AU3's engine wiring: _compute_room_actuators, ActuatorCache, recovery tracking."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.actuators import ActuatorCache
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.state_store import CanonicalState


class _FakeStates:
    def __init__(self, states=None):
        self._states = states or {}

    def get(self, _entity_id: str):
        return self._states.get(_entity_id)


class _FakeBus:
    def async_fire(self, _event_type: str, _data: dict) -> None:
        return None


class _FakeServices:
    def async_services(self) -> dict[str, dict]:
        return {}


def _fake_engine(cache: ActuatorCache | None) -> SimpleNamespace:
    return SimpleNamespace(_state=CanonicalState(), _actuator_cache=cache)


def _hass() -> SimpleNamespace:
    return SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())


def test_compute_room_actuators_writes_empty_sensor_without_cache():
    fake_engine = _fake_engine(None)
    HeimaEngine._compute_room_actuators(fake_engine, options={})
    assert fake_engine._state.get_sensor("rooms.actuators") == []


def test_compute_room_actuators_writes_actuators_from_cache():
    cache = ActuatorCache()
    fake_engine = _fake_engine(cache)
    options = {
        "rooms": [{"room_id": "kitchen"}],
        "room_actuators": [
            {"actuator_id": "a1", "entity_id": "cover.kitchen_shutter", "room_id": "kitchen"}
        ],
    }
    HeimaEngine._compute_room_actuators(fake_engine, options=options)
    payload = fake_engine._state.get_sensor("rooms.actuators")
    assert payload == [
        {
            "actuator_id": "a1",
            "entity_id": "cover.kitchen_shutter",
            "room_id": "kitchen",
            "opening_id": None,
            "display_name": None,
        }
    ]


def test_compute_room_actuators_reuses_cache_instance():
    cache = ActuatorCache()
    fake_engine = _fake_engine(cache)
    options = {"room_actuators": [{"actuator_id": "a1", "entity_id": "cover.x", "room_id": "k"}]}
    HeimaEngine._compute_room_actuators(fake_engine, options=options)

    changed_options = {
        "room_actuators": [{"actuator_id": "a2", "entity_id": "cover.y", "room_id": "k"}]
    }
    HeimaEngine._compute_room_actuators(fake_engine, options=changed_options)
    payload = fake_engine._state.get_sensor("rooms.actuators")

    # No mark_stale() call in between: the cache never rebuilds, matching the
    # spec's "cached; invalidated only on options/registry change" contract.
    assert payload[0]["actuator_id"] == "a1"


def test_actuator_cache_mark_stale_forces_rebuild():
    cache = ActuatorCache()
    fake_engine = _fake_engine(cache)
    options = {"room_actuators": [{"actuator_id": "a1", "entity_id": "cover.x", "room_id": "k"}]}
    HeimaEngine._compute_room_actuators(fake_engine, options=options)

    cache.mark_stale()
    changed_options = {
        "room_actuators": [{"actuator_id": "a2", "entity_id": "cover.y", "room_id": "k"}]
    }
    HeimaEngine._compute_room_actuators(fake_engine, options=changed_options)
    payload = fake_engine._state.get_sensor("rooms.actuators")

    assert payload[0]["actuator_id"] == "a2"


def test_recovery_critical_entity_ids_includes_opening_entity_id():
    hass = _hass()
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(
            entry_id="entry-a",
            options={
                "room_openings": [
                    {"opening_id": "op1", "room_id": "kitchen", "entity_id": "binary_sensor.win"}
                ]
            },
        ),
    )
    assert "binary_sensor.win" in engine._recovery_critical_entity_ids()


def test_recovery_critical_entity_ids_includes_actuator_entity_id():
    hass = _hass()
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(
            entry_id="entry-a",
            options={
                "room_actuators": [
                    {"actuator_id": "a1", "entity_id": "cover.kitchen_shutter", "room_id": "k"}
                ]
            },
        ),
    )
    assert "cover.kitchen_shutter" in engine._recovery_critical_entity_ids()
