from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.room_inventory import build_room_inventory_summary


class _FakeHass:
    pass


def test_build_room_inventory_summary_derives_entities_and_suggestions(monkeypatch):
    hass = _FakeHass()
    entity_registry = SimpleNamespace(
        entities={
            "e1": SimpleNamespace(
                entity_id="binary_sensor.studio_motion",
                area_id="studio",
                device_id=None,
            ),
            "e2": SimpleNamespace(
                entity_id="sensor.studio_lux",
                area_id="studio",
                device_id=None,
            ),
            "e3": SimpleNamespace(
                entity_id="light.studio_main",
                area_id="",
                device_id="device-1",
            ),
            "e4": SimpleNamespace(
                entity_id="sensor.outdoor_temp",
                area_id="outside",
                device_id=None,
            ),
        }
    )
    device_registry = SimpleNamespace(
        devices={
            "device-1": SimpleNamespace(area_id="studio"),
        }
    )

    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: device_registry,
    )

    summary = build_room_inventory_summary(
        hass,
        [
            {
                "room_id": "studio",
                "display_name": "Studio",
                "area_id": "studio",
                "occupancy_sources": ["binary_sensor.studio_motion"],
                "learning_sources": ["sensor.outdoor_temp"],
            }
        ],
    )

    assert summary["total_rooms"] == 1
    room = summary["rooms"][0]
    assert room["inventory_entity_total"] == 3
    assert room["inventory_entity_ids"] == [
        "binary_sensor.studio_motion",
        "light.studio_main",
        "sensor.studio_lux",
    ]
    assert room["suggested_occupancy_sources"] == ["binary_sensor.studio_motion"]
    assert room["suggested_learning_sources"] == ["sensor.studio_lux"]
    assert room["suggested_lighting_entities"] == ["light.studio_main"]
    assert room["configured_sources_not_in_area"] == ["sensor.outdoor_temp"]


def test_build_room_inventory_summary_handles_room_without_area(monkeypatch):
    hass = _FakeHass()
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: SimpleNamespace(entities={}),
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: SimpleNamespace(devices={}),
    )

    summary = build_room_inventory_summary(
        hass,
        [
            {
                "room_id": "studio",
                "display_name": "Studio",
                "occupancy_sources": [],
                "learning_sources": [],
            }
        ],
    )

    room = summary["rooms"][0]
    assert room["area_id"] is None
    assert room["inventory_entity_total"] == 0
    assert room["suggested_occupancy_sources"] == []
