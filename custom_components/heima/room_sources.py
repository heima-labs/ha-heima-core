"""Helpers for room source configuration and learning signal selection."""

from __future__ import annotations

from typing import Any


def normalize_room_sources(
    raw_sources: Any,
    *,
    learning_enabled_entities: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Normalize legacy or structured room sources to a stable dict shape."""
    learning_enabled = {
        str(entity_id).strip()
        for entity_id in (learning_enabled_entities or [])
        if str(entity_id).strip()
    }
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    if raw_sources is None:
        return normalized

    if not isinstance(raw_sources, list):
        raw_sources = [raw_sources]

    for item in raw_sources:
        entity_id = ""
        item_learning_enabled: bool | None = None
        if isinstance(item, dict):
            entity_id = str(item.get("entity_id", "")).strip()
            if "learning_enabled" in item:
                item_learning_enabled = bool(item.get("learning_enabled"))
        else:
            entity_id = str(item).strip()

        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        normalized.append(
            {
                "entity_id": entity_id,
                "learning_enabled": (
                    entity_id in learning_enabled
                    if learning_enabled_entities is not None
                    else bool(item_learning_enabled)
                ),
            }
        )
    return normalized


def room_source_entity_ids(room_or_sources: Any) -> list[str]:
    """Return all entity ids configured as sources for a room."""
    return [
        str(source.get("entity_id", "")).strip()
        for source in normalize_room_sources(_extract_sources(room_or_sources))
        if str(source.get("entity_id", "")).strip()
    ]


def room_learning_source_entity_ids(room_or_sources: Any) -> list[str]:
    """Return room source entity ids explicitly enabled for learning."""
    return [
        str(source.get("entity_id", "")).strip()
        for source in normalize_room_sources(_extract_sources(room_or_sources))
        if source.get("learning_enabled") and str(source.get("entity_id", "")).strip()
    ]


def _extract_sources(room_or_sources: Any) -> Any:
    if isinstance(room_or_sources, dict):
        return room_or_sources.get("sources", [])
    return room_or_sources
