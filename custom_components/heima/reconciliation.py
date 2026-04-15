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
    reconciled: list[dict[str, Any]] = []
    claimed_entities: set[str] = set()
    claimed_slugs: set[str] = set()
    orphaned: list[str] = []
    for person in people:
        item = dict(person)
        slug = str(item.get("slug") or "").strip()
        person_entity = str(item.get("person_entity") or "").strip()
        if not person_entity:
            matched_person_entity = _match_person_entity_for_person(item, inventory)
            if matched_person_entity:
                person_entity = matched_person_entity
                item["person_entity"] = matched_person_entity
        item["presence_rule"] = str(item.get("presence_rule") or "resident").strip() or "resident"
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
        merged = False
        for index, existing in enumerate(reconciled):
            if not _people_records_overlap(existing, item):
                continue
            reconciled[index] = _merge_people_records(existing, item)
            merged = True
            break
        if merged:
            continue
        reconciled.append(item)
        if slug:
            claimed_slugs.add(slug)
        if person_entity:
            claimed_entities.add(person_entity)

    new_people: list[str] = []
    for person_entity, display_name in inventory.items():
        if person_entity in claimed_entities:
            continue
        slug = person_entity.split(".", 1)[1]
        if slug in claimed_slugs:
            suffix = 2
            while f"{slug}_{suffix}" in claimed_slugs:
                suffix += 1
            slug = f"{slug}_{suffix}"
        claimed_slugs.add(slug)
        claimed_entities.add(person_entity)
        new_people.append(display_name or slug)
        reconciled.append(
            {
                "slug": slug,
                "display_name": display_name or slug,
                "presence_method": "ha_person",
                "presence_rule": "resident",
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


def _people_records_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_slug = str(left.get("slug") or "").strip()
    right_slug = str(right.get("slug") or "").strip()
    left_entity = str(left.get("person_entity") or "").strip()
    right_entity = str(right.get("person_entity") or "").strip()
    return bool(
        (left_entity and right_entity and left_entity == right_entity)
        or (left_slug and right_slug and left_slug == right_slug)
    )


def _merge_people_records(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    keep, merge = _preferred_people_record(primary, secondary)
    result = dict(keep)

    if (
        not str(result.get("person_entity") or "").strip()
        and str(merge.get("person_entity") or "").strip()
    ):
        result["person_entity"] = str(merge.get("person_entity") or "").strip()

    if (
        not str(result.get("display_name") or "").strip()
        and str(merge.get("display_name") or "").strip()
    ):
        result["display_name"] = str(merge.get("display_name") or "").strip()

    for field in (
        "presence_method",
        "presence_rule",
        "sources",
        "group_strategy",
        "required",
        "weight_threshold",
        "source_weights",
        "arrive_hold_s",
        "leave_hold_s",
        "enable_override",
        "ha_source_name",
    ):
        if field not in result and field in merge:
            result[field] = merge[field]

    result["source"] = "ha_person_registry"
    result["heima_reviewed"] = bool(primary.get("heima_reviewed")) or bool(
        secondary.get("heima_reviewed")
    )
    if result["heima_reviewed"]:
        result["ha_sync_status"] = "configured"
    elif str(result.get("person_entity") or "").strip():
        result["ha_sync_status"] = "new"
    else:
        result["ha_sync_status"] = "orphaned"
    return result


def _preferred_people_record(
    left: dict[str, Any], right: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    left_reviewed = bool(left.get("heima_reviewed"))
    right_reviewed = bool(right.get("heima_reviewed"))
    if left_reviewed != right_reviewed:
        return (left, right) if left_reviewed else (right, left)

    left_status = str(left.get("ha_sync_status") or "").strip()
    right_status = str(right.get("ha_sync_status") or "").strip()
    if left_status != right_status:
        left_rank = 0 if left_status == "configured" else 1 if left_status == "orphaned" else 2
        right_rank = 0 if right_status == "configured" else 1 if right_status == "orphaned" else 2
        return (left, right) if left_rank <= right_rank else (right, left)

    left_slug = str(left.get("slug") or "").strip()
    right_slug = str(right.get("slug") or "").strip()
    left_has_suffix = "_" in left_slug
    right_has_suffix = "_" in right_slug
    if left_has_suffix != right_has_suffix:
        return (left, right) if not left_has_suffix else (right, left)
    return left, right


def _match_person_entity_for_person(
    person: dict[str, Any],
    inventory: dict[str, str],
) -> str | None:
    slug = str(person.get("slug") or "").strip()
    display_name = str(person.get("display_name") or "").strip()

    candidates: list[str] = []
    if slug:
        candidates.append(slug)
    if display_name:
        candidates.append(slugify(display_name))

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        matched = f"person.{normalized}"
        if matched in inventory:
            return matched

    if display_name:
        display_name_lower = display_name.casefold()
        matches = [
            entity_id
            for entity_id, ha_display_name in inventory.items()
            if str(ha_display_name or "").strip().casefold() == display_name_lower
        ]
        if len(matches) == 1:
            return matches[0]
    return None


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
                "on_dwell_s": 0,
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
