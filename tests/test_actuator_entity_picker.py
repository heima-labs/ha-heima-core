"""Tests for the Actuators admin form's Entity ID picker candidates.

Covers websocket_api._actuator_entity_candidates() directly: reuses Phase L's discovery rule for
actuator domains (AV1), resolving area_id -> room_id itself and excluding already-registered
entity_ids (see docs/specs/core/actuator_discovery_spec.md Surface 2). Mirrors
tests/test_topology_opening_entity_picker.py's approach for the Opening picker.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.heima.websocket_api import _actuator_entity_candidates


class _FakeStates:
    def __init__(self, states=None):
        self._states = list(states or [])

    def async_all(self):
        return list(self._states)


def _entry(entity_id: str, **attrs) -> SimpleNamespace:
    return SimpleNamespace(entity_id=entity_id, **attrs)


def _area(area_id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=area_id, name=name)


def _hass() -> SimpleNamespace:
    return SimpleNamespace(states=_FakeStates())


def _patched(entity_registry, device_registry, area_registry):
    return (
        patch("custom_components.heima.websocket_api.er.async_get", return_value=entity_registry),
        patch("custom_components.heima.websocket_api.dr.async_get", return_value=device_registry),
        patch("custom_components.heima.websocket_api.ar.async_get", return_value=area_registry),
    )


def test_actuator_entity_candidates_resolves_room_via_area():
    entity_registry = SimpleNamespace(
        entities={"cover.kitchen_shutter": _entry("cover.kitchen_shutter", area_id="area_kitchen")}
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = SimpleNamespace(async_list_areas=lambda: [_area("area_kitchen", "Kitchen")])
    options = {"rooms": [{"room_id": "kitchen", "area_id": "area_kitchen"}]}

    p1, p2, p3 = _patched(entity_registry, device_registry, area_registry)
    with p1, p2, p3:
        candidates = _actuator_entity_candidates(_hass(), options)

    assert candidates == [
        {
            "entity_id": "cover.kitchen_shutter",
            "domain": "cover",
            "device_class": "",
            "room_id": "kitchen",
            "area_name": "Kitchen",
        }
    ]


def test_actuator_entity_candidates_excludes_entity_with_no_matching_room():
    entity_registry = SimpleNamespace(
        entities={"cover.attic_shutter": _entry("cover.attic_shutter", area_id="area_unmapped")}
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = SimpleNamespace(async_list_areas=lambda: [_area("area_unmapped", "Unmapped")])
    options = {"rooms": [{"room_id": "kitchen", "area_id": "area_kitchen"}]}

    p1, p2, p3 = _patched(entity_registry, device_registry, area_registry)
    with p1, p2, p3:
        candidates = _actuator_entity_candidates(_hass(), options)

    assert candidates == []


def test_actuator_entity_candidates_excludes_non_actuator_domain():
    entity_registry = SimpleNamespace(
        entities={"light.kitchen_lamp": _entry("light.kitchen_lamp", area_id="area_kitchen")}
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = SimpleNamespace(async_list_areas=lambda: [_area("area_kitchen", "Kitchen")])
    options = {"rooms": [{"room_id": "kitchen", "area_id": "area_kitchen"}]}

    p1, p2, p3 = _patched(entity_registry, device_registry, area_registry)
    with p1, p2, p3:
        candidates = _actuator_entity_candidates(_hass(), options)

    assert candidates == []


def test_actuator_entity_candidates_excludes_already_registered_entity_id():
    entity_registry = SimpleNamespace(
        entities={"cover.kitchen_shutter": _entry("cover.kitchen_shutter", area_id="area_kitchen")}
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = SimpleNamespace(async_list_areas=lambda: [_area("area_kitchen", "Kitchen")])
    options = {
        "rooms": [{"room_id": "kitchen", "area_id": "area_kitchen"}],
        "room_actuators": [
            {
                "actuator_id": "existing-1",
                "entity_id": "cover.kitchen_shutter",
                "room_id": "kitchen",
                "opening_id": None,
                "display_name": None,
            }
        ],
    }

    p1, p2, p3 = _patched(entity_registry, device_registry, area_registry)
    with p1, p2, p3:
        candidates = _actuator_entity_candidates(_hass(), options)

    assert candidates == []


def test_actuator_entity_candidates_returns_empty_when_registries_unavailable():
    with patch(
        "custom_components.heima.websocket_api.er.async_get", side_effect=RuntimeError("boom")
    ):
        candidates = _actuator_entity_candidates(_hass(), {"rooms": []})

    assert candidates == []
