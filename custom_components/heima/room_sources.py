"""Helpers for room occupancy and learning source configuration."""

from __future__ import annotations

from typing import Any


def normalize_entity_id_list(raw_entities: Any) -> list[str]:
    """Normalize selector outputs or raw lists to a stable list[str]."""
    if raw_entities is None:
        return []
    if isinstance(raw_entities, dict):
        return [str(key).strip() for key, enabled in raw_entities.items() if enabled and str(key).strip()]
    if isinstance(raw_entities, (list, tuple, set)):
        return [str(entity_id).strip() for entity_id in raw_entities if str(entity_id).strip()]
    if isinstance(raw_entities, str):
        clean = raw_entities.strip()
        return [clean] if clean else []
    clean = str(raw_entities).strip()
    return [clean] if clean else []


def normalize_room_signal_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize room occupancy/learning sources with backward-compatible migration."""
    data = dict(payload)

    explicit_occupancy = "occupancy_sources" in data
    explicit_learning = "learning_sources" in data

    if explicit_occupancy:
        occupancy_sources = normalize_entity_id_list(data.get("occupancy_sources"))
    else:
        occupancy_sources = _migrate_legacy_occupancy_sources(data.get("sources"))

    if explicit_learning:
        learning_sources = normalize_entity_id_list(data.get("learning_sources"))
    else:
        learning_sources = _migrate_legacy_learning_sources(data.get("sources"))

    data["occupancy_sources"] = _dedupe(occupancy_sources)
    data["learning_sources"] = _dedupe(learning_sources)
    data.pop("sources", None)
    return data


def room_occupancy_source_entity_ids(room_or_sources: Any) -> list[str]:
    """Return occupancy sources for a room, with legacy migration fallback."""
    if isinstance(room_or_sources, dict):
        if "occupancy_sources" in room_or_sources:
            return _dedupe(normalize_entity_id_list(room_or_sources.get("occupancy_sources")))
        return _dedupe(_migrate_legacy_occupancy_sources(room_or_sources.get("sources")))
    return _dedupe(normalize_entity_id_list(room_or_sources))


def room_learning_source_entity_ids(room_or_sources: Any) -> list[str]:
    """Return learning sources for a room, with legacy migration fallback."""
    if isinstance(room_or_sources, dict):
        if "learning_sources" in room_or_sources:
            return _dedupe(normalize_entity_id_list(room_or_sources.get("learning_sources")))
        return _dedupe(_migrate_legacy_learning_sources(room_or_sources.get("sources")))
    return _dedupe(normalize_entity_id_list(room_or_sources))


def room_all_source_entity_ids(room_cfg: dict[str, Any]) -> list[str]:
    """Return all room-level sources used for occupancy or learning."""
    return _dedupe(
        [
            *room_occupancy_source_entity_ids(room_cfg),
            *room_learning_source_entity_ids(room_cfg),
        ]
    )


def _migrate_legacy_occupancy_sources(raw_sources: Any) -> list[str]:
    migrated: list[str] = []
    for item in normalize_entity_id_list_or_structured(raw_sources):
        if isinstance(item, dict):
            entity_id = str(item.get("entity_id", "")).strip()
            if entity_id:
                migrated.append(entity_id)
        else:
            clean = str(item).strip()
            if clean:
                migrated.append(clean)
    return migrated


def _migrate_legacy_learning_sources(raw_sources: Any) -> list[str]:
    migrated: list[str] = []
    for item in normalize_entity_id_list_or_structured(raw_sources):
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("entity_id", "")).strip()
        if entity_id and bool(item.get("learning_enabled")):
            migrated.append(entity_id)
    return migrated


def normalize_entity_id_list_or_structured(raw_entities: Any) -> list[Any]:
    """Normalize mixed legacy room source payloads without losing dict entries."""
    if raw_entities is None:
        return []
    if isinstance(raw_entities, list):
        return list(raw_entities)
    if isinstance(raw_entities, (tuple, set)):
        return list(raw_entities)
    if isinstance(raw_entities, dict):
        return [raw_entities]
    if isinstance(raw_entities, str):
        clean = raw_entities.strip()
        return [clean] if clean else []
    clean = str(raw_entities).strip()
    return [clean] if clean else []


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped
