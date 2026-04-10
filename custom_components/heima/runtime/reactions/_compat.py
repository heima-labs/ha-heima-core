"""Compatibility helpers for reaction config payloads."""

from __future__ import annotations

from typing import Any

LEGACY_REACTION_CLASS_TO_TYPE: dict[str, str] = {
    "PresencePatternReaction": "presence_preheat",
    "LightingScheduleReaction": "lighting_scene_schedule",
    "HeatingPreferenceReaction": "heating_preference",
    "HeatingEcoReaction": "heating_eco",
    "RoomSignalAssistReaction": "room_signal_assist",
    "RoomLightingAssistReaction": "room_darkness_lighting_assist",
    "RoomLightingVacancyOffReaction": "room_vacancy_lighting_off",
    "VacationPresenceSimulationReaction": "vacation_presence_simulation",
}


def resolve_reaction_type(cfg: dict[str, Any]) -> str:
    """Return the canonical reaction_type for a stored config payload."""
    reaction_type = str(cfg.get("reaction_type") or "").strip()
    if reaction_type:
        return reaction_type
    reaction_class = str(cfg.get("reaction_class") or "").strip()
    return LEGACY_REACTION_CLASS_TO_TYPE.get(reaction_class, "")
