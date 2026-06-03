"""Shared media-active state semantics."""

from __future__ import annotations

_MEDIA_ACTIVE_STATES = {"on", "playing", "paused", "buffering"}


def media_entity_is_active(entity_id: str, raw_state: str | None) -> bool:
    """Return whether a configured media-like entity should count as active."""
    lowered = str(raw_state or "").strip().lower()
    if lowered in {"", "unknown", "unavailable", "none"}:
        return False
    if str(entity_id).startswith("media_player."):
        return lowered in _MEDIA_ACTIVE_STATES
    return lowered in _MEDIA_ACTIVE_STATES or lowered in {
        "open",
        "occupied",
        "detected",
        "true",
        "1",
    }
