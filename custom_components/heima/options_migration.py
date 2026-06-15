"""Config entry options migrations."""

from __future__ import annotations

from typing import Any

from .const import OPT_EXTERNAL_CONTEXT, OPT_LEARNING

_LEGACY_LEARNING_EXTERNAL_CONTEXT_MAP = {
    "outdoor_lux_entity": ("outdoor_lux",),
    "outdoor_temp_entity": ("outdoor_temp",),
    "weather_entity": ("weather_condition", "outdoor_temp"),
}


def migrate_learning_external_context_options(
    options: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Move legacy learning outdoor/weather entity config into external_context.

    Outdoor and weather entities are runtime context sources, not learning policy.
    Existing values are preserved by copying them to the canonical external_context
    slots only when the target slot is empty, then removing the legacy keys.
    """
    learning = options.get(OPT_LEARNING)
    if not isinstance(learning, dict):
        return options, False

    migrated = dict(options)
    migrated_learning = dict(learning)
    external_context = dict(migrated.get(OPT_EXTERNAL_CONTEXT) or {})
    changed = False

    for legacy_key, target_slots in _LEGACY_LEARNING_EXTERNAL_CONTEXT_MAP.items():
        value = str(migrated_learning.get(legacy_key) or "").strip()
        if value:
            for slot in target_slots:
                if not str(external_context.get(slot) or "").strip():
                    external_context[slot] = value
                    changed = True
        if legacy_key in migrated_learning:
            migrated_learning.pop(legacy_key, None)
            changed = True

    if not changed:
        return options, False

    migrated[OPT_LEARNING] = migrated_learning
    migrated[OPT_EXTERNAL_CONTEXT] = external_context
    return migrated, True
