"""Helpers for reconciling HA-backed people and rooms into Heima options."""

from __future__ import annotations

from typing import Any

from homeassistant.util import slugify

from .const import OPT_PEOPLE_NAMED, OPT_ROOMS


def reconcile_ha_backed_options(
    options: dict[str, Any],
    *,
    ha_people: list[dict[str, str]],
    ha_areas: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Return reconciled options, summary, and whether options changed."""
    updated = dict(options)
    people, people_summary = _reconcile_people(list(updated.get(OPT_PEOPLE_NAMED, [])), ha_people)
    rooms, rooms_summary = _reconcile_rooms(list(updated.get(OPT_ROOMS, [])), ha_areas)
    updated[OPT_PEOPLE_NAMED] = people
    updated[OPT_ROOMS] = rooms
    changed = updated != dict(options)
    return (
        updated,
        {
            "people": people_summary,
            "rooms": rooms_summary,
        },
        changed,
    )


def _reconcile_people(
    people: list[dict[str, Any]],
    ha_people: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inventory = {
        str(item.get("entity_id") or "").strip(): str(item.get("display_name") or "").strip()
        for item in ha_people
        if str(item.get("entity_id") or "").strip()
    }
    existing_entities = {
        str(person.get("person_entity") or "").strip()
        for person in people
        if str(person.get("person_entity") or "").strip()
    }
    existing_slugs = {
        str(person.get("slug") or "").strip()
        for person in people
        if str(person.get("slug") or "").strip()
    }

    reconciled: list[dict[str, Any]] = []
    orphaned: list[str] = []
    for person in people:
        item = dict(person)
        person_entity = str(item.get("person_entity") or "").strip()
        item["source"] = "ha_person_registry"
        if person_entity and person_entity in inventory:
            ha_name = inventory[person_entity]
            previous_ha_name = str(item.get("ha_source_name") or "").strip()
            if not str(item.get("display_name") or "").strip() or (
                not bool(item.get("heima_reviewed"))
                and str(item.get("display_name") or "").strip() in {"", previous_ha_name}
            ):
                item["display_name"] = ha_name
            item["ha_source_name"] = ha_name
            item["ha_sync_status"] = "configured" if bool(item.get("heima_reviewed")) else "new"
        else:
            item["ha_sync_status"] = "orphaned"
            orphaned.append(str(item.get("slug") or person_entity or "unknown"))
        reconciled.append(item)

    new_people: list[str] = []
    for person_entity, display_name in inventory.items():
        if person_entity in existing_entities:
            continue
        slug = person_entity.split(".", 1)[1]
        if slug in existing_slugs:
            suffix = 2
            while f"{slug}_{suffix}" in existing_slugs:
                suffix += 1
            slug = f"{slug}_{suffix}"
        existing_slugs.add(slug)
        new_people.append(display_name or slug)
        reconciled.append(
            {
                "slug": slug,
                "display_name": display_name or slug,
                "presence_method": "ha_person",
                "person_entity": person_entity,
                "arrive_hold_s": 10,
                "leave_hold_s": 120,
                "enable_override": False,
                "source": "ha_person_registry",
                "ha_source_name": display_name or slug,
                "ha_sync_status": "new",
                "heima_reviewed": False,
            }
        )

    return (
        reconciled,
        {
            "new_labels": new_people,
            "orphaned_labels": orphaned,
            "total": len(reconciled),
            "new_total": sum(1 for item in reconciled if item.get("ha_sync_status") == "new"),
            "configured_total": sum(
                1 for item in reconciled if item.get("ha_sync_status") == "configured"
            ),
            "orphaned_total": sum(
                1 for item in reconciled if item.get("ha_sync_status") == "orphaned"
            ),
        },
    )


def _reconcile_rooms(
    rooms: list[dict[str, Any]],
    ha_areas: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inventory = {
        str(item.get("area_id") or "").strip(): str(item.get("display_name") or "").strip()
        for item in ha_areas
        if str(item.get("area_id") or "").strip()
    }
    existing_area_ids = {
        str(room.get("area_id") or "").strip()
        for room in rooms
        if str(room.get("area_id") or "").strip()
    }
    existing_room_ids = {
        str(room.get("room_id") or "").strip()
        for room in rooms
        if str(room.get("room_id") or "").strip()
    }

    reconciled: list[dict[str, Any]] = []
    orphaned: list[str] = []
    for room in rooms:
        item = dict(room)
        area_id = str(item.get("area_id") or "").strip()
        if not area_id:
            matched_area_id = _match_area_id_for_room(item, inventory)
            if matched_area_id:
                area_id = matched_area_id
                item["area_id"] = matched_area_id
        item["source"] = "ha_area_registry"
        if area_id and area_id in inventory:
            ha_name = inventory[area_id]
            previous_ha_name = str(item.get("ha_source_name") or "").strip()
            if not str(item.get("display_name") or "").strip() or (
                not bool(item.get("heima_reviewed"))
                and str(item.get("display_name") or "").strip() in {"", previous_ha_name}
            ):
                item["display_name"] = ha_name
            item["ha_source_name"] = ha_name
            item["ha_sync_status"] = "configured" if bool(item.get("heima_reviewed")) else "new"
        else:
            item["ha_sync_status"] = "orphaned"
            orphaned.append(str(item.get("display_name") or item.get("room_id") or "unknown"))
        reconciled.append(item)

    new_rooms: list[str] = []
    for area_id, display_name in inventory.items():
        if area_id in existing_area_ids:
            continue
        room_id = area_id
        if room_id in existing_room_ids:
            suffix = 2
            while f"{room_id}_{suffix}" in existing_room_ids:
                suffix += 1
            room_id = f"{room_id}_{suffix}"
        existing_room_ids.add(room_id)
        new_rooms.append(display_name or room_id)
        reconciled.append(
            {
                "room_id": room_id,
                "display_name": display_name or room_id,
                "area_id": area_id,
                "occupancy_mode": "none",
                "occupancy_sources": [],
                "learning_sources": [],
                "logic": "any_of",
                "on_dwell_s": 5,
                "off_dwell_s": 120,
                "max_on_s": None,
                "source": "ha_area_registry",
                "ha_source_name": display_name or room_id,
                "ha_sync_status": "new",
                "heima_reviewed": False,
            }
        )

    return (
        reconciled,
        {
            "new_labels": new_rooms,
            "orphaned_labels": orphaned,
            "total": len(reconciled),
            "new_total": sum(1 for item in reconciled if item.get("ha_sync_status") == "new"),
            "configured_total": sum(
                1 for item in reconciled if item.get("ha_sync_status") == "configured"
            ),
            "orphaned_total": sum(
                1 for item in reconciled if item.get("ha_sync_status") == "orphaned"
            ),
        },
    )


def _match_area_id_for_room(room: dict[str, Any], inventory: dict[str, str]) -> str | None:
    room_id = str(room.get("room_id") or "").strip()
    display_name = str(room.get("display_name") or "").strip()
    candidates = []
    if room_id:
        candidates.append(room_id)
        candidates.append(slugify(room_id))
    if display_name:
        candidates.append(slugify(display_name))
    seen: set[str] = set()
    for candidate in candidates:
        candidate = str(candidate or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if candidate in inventory:
            return candidate
    return None
