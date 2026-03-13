"""Shared utilities, selectors, parsers, and constants for Heima config flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector
from homeassistant.util import slugify  # noqa: F401 (re-exported for step modules)

from ..const import HOUSE_SIGNAL_NAMES

# ---------------------------------------------------------------------------
# UI option lists
# ---------------------------------------------------------------------------

PRESENCE_METHODS = ["ha_person", "quorum", "manual"]
PEOPLE_GROUP_LOGIC = ["quorum", "weighted_quorum"]
ROOM_LOGIC = ["any_of", "all_of", "weighted_quorum"]
ROOM_OCCUPANCY_MODES = ["derived", "none"]
HEATING_APPLY_MODES = ["delegate_to_scheduler", "set_temperature"]
LIGHTING_APPLY_MODES = ["scene", "delegate"]
HEATING_HOUSE_STATES = ["away", "home", "guest", "vacation", "sleeping", "relax", "working"]
HEATING_BRANCH_TYPES = ["disabled", "scheduler_delegate", "fixed_target", "vacation_curve"]

# ---------------------------------------------------------------------------
# Voluptuous validators
# ---------------------------------------------------------------------------

_NON_NEGATIVE_INT = vol.All(vol.Coerce(int), vol.Range(min=0))

# ---------------------------------------------------------------------------
# HA helpers
# ---------------------------------------------------------------------------


def _default_timezone(hass: HomeAssistant) -> str:
    return str(getattr(hass.config, "time_zone", "UTC") or "UTC")


def _default_language(hass: HomeAssistant) -> str:
    return str(getattr(hass.config, "language", "en") or "en")


# ---------------------------------------------------------------------------
# Selector builders
# ---------------------------------------------------------------------------


def _scene_selector(multiple: bool = False) -> dict[str, Any]:
    return selector({"entity": {"domain": "scene", "multiple": multiple}})


def _entity_selector(domains: list[str], multiple: bool = False) -> dict[str, Any]:
    return selector({"entity": {"domain": domains, "multiple": multiple}})


def _multiline_text_selector() -> dict[str, Any]:
    return selector({"text": {"multiline": True}})


def _object_selector() -> dict[str, Any]:
    return selector({"object": {}})


# ---------------------------------------------------------------------------
# Formatting helpers (in-memory → display string)
# ---------------------------------------------------------------------------


def _format_source_weights(weights: Any) -> str:
    """Render persisted source weights for a textarea field."""
    if not isinstance(weights, dict):
        return ""
    lines: list[str] = []
    for entity_id, value in weights.items():
        try:
            rendered = float(value)
        except (TypeError, ValueError):
            continue
        lines.append(f"{entity_id}={rendered:g}")
    return "\n".join(lines)


def _format_string_list(values: Any) -> str:
    """Render persisted list values for a textarea field."""
    if not isinstance(values, (list, tuple, set)):
        return ""
    return "\n".join(str(value) for value in values if str(value).strip())


def _format_notify_mapping(mapping: Any) -> str:
    """Render persisted alias/group mappings as editable text."""
    if not isinstance(mapping, dict):
        return ""
    lines: list[str] = []
    for key, values in mapping.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        rendered_values = [str(value).strip() for value in (values or []) if str(value).strip()]
        if not rendered_values:
            continue
        lines.append(f"{key_str}={','.join(rendered_values)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parsing helpers (display string → in-memory)
# ---------------------------------------------------------------------------


def _parse_multiline_items(value: Any) -> list[str]:
    """Parse comma/newline separated text into a stable list of ids."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [str(k).strip() for k, enabled in value.items() if enabled and str(k).strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return [str(value).strip()] if str(value).strip() else []
    items: list[str] = []
    for line in value.splitlines():
        for part in line.split(","):
            item = part.strip()
            if item:
                items.append(item)
    return items


def _parse_multiline_mapping(value: Any) -> dict[str, list[str]]:
    """Parse `key=a,b` lines into a normalized mapping."""
    if value is None:
        return {}
    if isinstance(value, dict):
        normalized: dict[str, list[str]] = {}
        for key, items in value.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            normalized_items = _parse_multiline_items(items)
            if normalized_items:
                normalized[key_str] = normalized_items
        return normalized
    if not isinstance(value, str):
        return {}
    mapping: dict[str, list[str]] = {}
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, sep, remainder = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        items_parsed = _parse_multiline_items(remainder)
        if items_parsed:
            mapping[key] = items_parsed
    return mapping


# ---------------------------------------------------------------------------
# House signal helpers
# ---------------------------------------------------------------------------


def _normalize_house_signal_bindings(value: Any) -> dict[str, str]:
    """Normalize configured house-signal entity bindings."""
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for signal_name in HOUSE_SIGNAL_NAMES:
        raw = value.get(signal_name)
        if raw in (None, ""):
            continue
        entity_id = str(raw).strip()
        if entity_id:
            normalized[signal_name] = entity_id
    return normalized


# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------


def _is_valid_slug(value: str) -> bool:
    try:
        cv.slug(value)
        return True
    except vol.Invalid:
        return False
