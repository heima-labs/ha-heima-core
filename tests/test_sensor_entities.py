from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.entities.sensor import HeimaGenericSensor
from custom_components.heima.runtime.state_store import CanonicalState


def _sensor_with_state(key: str, value, attrs: dict | None = None) -> HeimaGenericSensor:
    state = CanonicalState()
    state.set_sensor(key, value)
    if attrs is not None:
        state.set_sensor_attributes(key, attrs)
    coordinator = SimpleNamespace(engine=SimpleNamespace(state=state))
    entry = SimpleNamespace(entry_id="entry-1")
    return HeimaGenericSensor(coordinator, entry, key, f"Sensor {key}")


def test_generic_sensor_exposes_native_value_from_state_store():
    entity = _sensor_with_state("heima_reactions_active", 3)

    assert entity.native_value == 3


def test_generic_sensor_exposes_extra_state_attributes_from_state_store():
    entity = _sensor_with_state(
        "heima_reactions_active",
        2,
        {
            "reactions": {
                "r1": {"muted": False},
                "r2": {"muted": True},
            },
            "total": 2,
            "muted_total": 1,
        },
    )

    assert entity.extra_state_attributes == {
        "reactions": {
            "r1": {"muted": False},
            "r2": {"muted": True},
        },
        "total": 2,
        "muted_total": 1,
    }
