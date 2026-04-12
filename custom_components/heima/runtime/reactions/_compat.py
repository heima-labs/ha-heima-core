"""Compatibility helpers for reaction config payloads."""

from __future__ import annotations

from typing import Any

from ...const import OPT_REACTIONS

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
_REDACTED_SENTINEL = "**REDACTED**"
_ENTITY_ID_LIST_FIELDS = {
    "primary_signal_entities",
    "trigger_signal_entities",
    "temperature_signal_entities",
    "corroboration_signal_entities",
    "observed_followup_entities",
    "allowed_entities",
}


def resolve_reaction_type(cfg: dict[str, Any]) -> str:
    """Return the canonical reaction_type for a stored config payload."""
    reaction_type = str(cfg.get("reaction_type") or "").strip()
    if reaction_type:
        return reaction_type
    reaction_class = str(cfg.get("reaction_class") or "").strip()
    return LEGACY_REACTION_CLASS_TO_TYPE.get(reaction_class, "")


def normalize_reaction_options_payload(options: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Normalize persisted reaction options and remove obviously corrupted payloads."""
    normalized_options = dict(options or {})
    reactions = dict(normalized_options.get(OPT_REACTIONS, {}) or {})
    configured = dict(reactions.get("configured", {}) or {})
    labels = dict(reactions.get("labels", {}) or {})
    muted = list(reactions.get("muted", []) or [])

    changed = False
    normalized_configured: dict[str, Any] = {}
    removed_ids: set[str] = set()

    for reaction_id, raw_cfg in configured.items():
        if not isinstance(raw_cfg, dict):
            normalized_configured[reaction_id] = raw_cfg
            continue
        cfg, cfg_changed, keep = _normalize_single_reaction_config(raw_cfg)
        changed = changed or cfg_changed
        if not keep:
            removed_ids.add(str(reaction_id))
            changed = True
            continue
        normalized_configured[str(reaction_id)] = cfg

    if removed_ids:
        labels = {rid: label for rid, label in labels.items() if rid not in removed_ids}
        muted = [rid for rid in muted if rid not in removed_ids]
        changed = True

    if changed:
        reactions["configured"] = normalized_configured
        reactions["labels"] = labels
        reactions["muted"] = muted
        normalized_options[OPT_REACTIONS] = reactions

    return normalized_options, changed


def _normalize_single_reaction_config(raw_cfg: dict[str, Any]) -> tuple[dict[str, Any], bool, bool]:
    cfg = dict(raw_cfg)
    changed = False

    reaction_type = resolve_reaction_type(cfg)
    if reaction_type and str(cfg.get("reaction_type") or "").strip() != reaction_type:
        cfg["reaction_type"] = reaction_type
        changed = True
    if "reaction_class" in cfg:
        cfg.pop("reaction_class", None)
        changed = True

    for field in _ENTITY_ID_LIST_FIELDS:
        if field not in cfg or not isinstance(cfg.get(field), list):
            continue
        original = list(cfg.get(field) or [])
        filtered = [
            str(item).strip()
            for item in original
            if str(item).strip() and not _is_redacted(str(item))
        ]
        if filtered != original:
            cfg[field] = filtered
            changed = True

    entity_steps = cfg.get("entity_steps")
    if isinstance(entity_steps, list):
        filtered_steps = [
            dict(raw_step)
            for raw_step in entity_steps
            if isinstance(raw_step, dict)
            and not _is_redacted(str(raw_step.get("entity_id") or ""))
            and str(raw_step.get("entity_id") or "").strip()
        ]
        if filtered_steps != entity_steps:
            cfg["entity_steps"] = filtered_steps
            changed = True

    steps = cfg.get("steps")
    if isinstance(steps, list):
        filtered_action_steps = []
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                continue
            target = str(raw_step.get("target") or "").strip()
            params = dict(raw_step.get("params", {}) or {})
            params_entity_id = str(params.get("entity_id") or "").strip()
            if _is_redacted(target) or _is_redacted(params_entity_id):
                changed = True
                continue
            filtered_action_steps.append(dict(raw_step))
        if filtered_action_steps != steps:
            cfg["steps"] = filtered_action_steps
            changed = True

    keep = not _reaction_requires_prune(cfg)
    return cfg, changed, keep


def _reaction_requires_prune(cfg: dict[str, Any]) -> bool:
    if _contains_redacted_marker(cfg):
        return True

    reaction_type = resolve_reaction_type(cfg)
    if reaction_type in {
        "lighting_scene_schedule",
        "room_darkness_lighting_assist",
        "room_vacancy_lighting_off",
    }:
        entity_steps = cfg.get("entity_steps")
        if not isinstance(entity_steps, list) or not entity_steps:
            return True

    if reaction_type == "room_darkness_lighting_assist":
        primary_entities = cfg.get("primary_signal_entities")
        if not isinstance(primary_entities, list) or not primary_entities:
            return True

    if reaction_type == "room_signal_assist":
        primary_entities = cfg.get("primary_signal_entities")
        trigger_entities = cfg.get("trigger_signal_entities")
        if not (
            isinstance(primary_entities, list)
            and primary_entities
            or isinstance(trigger_entities, list)
            and trigger_entities
        ):
            return True

    return False


def _contains_redacted_marker(value: Any) -> bool:
    if isinstance(value, str):
        return _is_redacted(value)
    if isinstance(value, dict):
        return any(_contains_redacted_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_redacted_marker(item) for item in value)
    return False


def _is_redacted(value: str) -> bool:
    return _REDACTED_SENTINEL in str(value or "")
