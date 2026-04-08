"""HA-backed room inventory and suggested binding helpers."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .room_sources import room_learning_source_entity_ids, room_occupancy_source_entity_ids


def build_room_inventory_summary(
    hass: HomeAssistant,
    rooms: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return HA-derived inventory and suggested bindings for configured rooms."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    room_items: list[dict[str, Any]] = []
    for room in rooms:
        item = _build_room_item(room, entity_registry=entity_registry, device_registry=device_registry)
        room_items.append(item)

    return {
        "total_rooms": len(room_items),
        "rooms_with_linked_area": sum(1 for item in room_items if item.get("area_id")),
        "rooms_with_inventory": sum(1 for item in room_items if int(item.get("inventory_entity_total") or 0) > 0),
        "rooms": room_items,
    }


def _build_room_item(
    room: dict[str, Any],
    *,
    entity_registry: Any,
    device_registry: Any,
) -> dict[str, Any]:
    room_id = str(room.get("room_id") or "").strip()
    display_name = str(room.get("display_name") or room_id).strip() or room_id
    area_id = str(room.get("area_id") or "").strip()
    inventory_entities = _entities_for_area(
        area_id=area_id,
        entity_registry=entity_registry,
        device_registry=device_registry,
    )
    by_domain = Counter(entity_id.split(".", 1)[0] for entity_id in inventory_entities if "." in entity_id)
    suggested_occupancy = [eid for eid in inventory_entities if _is_suggested_occupancy_entity(eid)]
    suggested_learning = [eid for eid in inventory_entities if _is_suggested_learning_entity(eid)]
    suggested_lighting = [eid for eid in inventory_entities if eid.startswith("light.")]
    configured_occupancy = room_occupancy_source_entity_ids(room)
    configured_learning = room_learning_source_entity_ids(room)
    inventory_set = set(inventory_entities)

    return {
        "room_id": room_id,
        "display_name": display_name,
        "area_id": area_id or None,
        "ha_sync_status": str(room.get("ha_sync_status") or "").strip() or None,
        "inventory_entity_total": len(inventory_entities),
        "inventory_entities_by_domain": dict(sorted(by_domain.items())),
        "inventory_entity_ids": inventory_entities,
        "suggested_occupancy_sources": suggested_occupancy,
        "suggested_learning_sources": suggested_learning,
        "suggested_lighting_entities": suggested_lighting,
        "configured_occupancy_sources": configured_occupancy,
        "configured_learning_sources": configured_learning,
        "configured_sources_not_in_area": sorted(
            {
                *[eid for eid in configured_occupancy if eid not in inventory_set],
                *[eid for eid in configured_learning if eid not in inventory_set],
            }
        ),
    }


def _entities_for_area(
    *,
    area_id: str,
    entity_registry: Any,
    device_registry: Any,
) -> list[str]:
    if not area_id:
        return []
    entities = getattr(entity_registry, "entities", {})
    devices = getattr(device_registry, "devices", {})
    matched: list[str] = []
    for entry in entities.values():
        entity_id = str(getattr(entry, "entity_id", "") or "").strip()
        if not entity_id:
            continue
        entry_area_id = str(getattr(entry, "area_id", "") or "").strip()
        if entry_area_id == area_id:
            matched.append(entity_id)
            continue
        device_id = str(getattr(entry, "device_id", "") or "").strip()
        if not device_id:
            continue
        device_entry = devices.get(device_id)
        device_area_id = str(getattr(device_entry, "area_id", "") or "").strip()
        if device_area_id == area_id:
            matched.append(entity_id)
    return sorted(set(matched))


def _is_suggested_occupancy_entity(entity_id: str) -> bool:
    domain, _, object_id = entity_id.partition(".")
    name = object_id.lower()
    if domain == "binary_sensor":
        return any(token in name for token in ("motion", "presence", "occupancy", "mmwave", "radar"))
    if domain == "sensor":
        return any(token in name for token in ("presence", "occupancy", "mmwave", "radar"))
    return False


def _is_suggested_learning_entity(entity_id: str) -> bool:
    domain, _, object_id = entity_id.partition(".")
    name = object_id.lower()
    if domain in {"sensor", "binary_sensor"}:
        return any(
            token in name
            for token in ("lux", "illuminance", "humidity", "co2", "temperature", "temp")
        )
    if domain == "switch":
        return any(token in name for token in ("fan", "heater", "dehumid", "humidifier"))
    return False
