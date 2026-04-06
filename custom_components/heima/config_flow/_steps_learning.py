"""Options flow: Learning step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_LEARNING
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_MAX_SIGNAL_ENTITIES = 10
_LEARNING_PLUGIN_FAMILY_OPTIONS = {
    "presence": "Presence",
    "heating": "Heating",
    "lighting": "Lighting",
    "composite_room_assist": "Room Assist",
    "security_presence_simulation": "Security Presence Simulation",
}


class _LearningStepsMixin:
    """Mixin for learning context configuration step."""

    async def async_step_learning(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        current = dict(self.options.get(OPT_LEARNING, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="learning",
                data_schema=self._learning_schema(current),
            )

        normalized = self._normalize_learning_payload(user_input)
        self._update_options({OPT_LEARNING: normalized})
        return await self.async_step_init()

    def _learning_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        if "enabled_plugin_families" not in defaults:
            defaults["enabled_plugin_families"] = list(_LEARNING_PLUGIN_FAMILY_OPTIONS)
        schema = vol.Schema(
            {
                vol.Optional("outdoor_lux_entity"): _entity_selector(["sensor"]),
                vol.Optional("outdoor_temp_entity"): _entity_selector(["sensor"]),
                vol.Optional("weather_entity"): _entity_selector(["weather"]),
                vol.Optional("context_signal_entities"): _entity_selector(
                    ["binary_sensor", "sensor", "input_boolean", "switch", "media_player"],
                    multiple=True,
                ),
                vol.Optional("enabled_plugin_families"): cv.multi_select(
                    _LEARNING_PLUGIN_FAMILY_OPTIONS
                ),
            }
        )
        return self._with_suggested(schema, defaults)

    def _normalize_learning_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}

        for key in ("outdoor_lux_entity", "outdoor_temp_entity", "weather_entity"):
            val = payload.get(key)
            data[key] = str(val).strip() if val else None

        raw_signals = payload.get("context_signal_entities") or []
        if isinstance(raw_signals, str):
            raw_signals = [raw_signals]
        signals = [str(e).strip() for e in raw_signals if e]
        data["context_signal_entities"] = signals[:_MAX_SIGNAL_ENTITIES]
        raw_families = payload.get("enabled_plugin_families")
        if isinstance(raw_families, dict):
            selected = [key for key, enabled in raw_families.items() if enabled]
        elif isinstance(raw_families, (list, tuple, set)):
            selected = list(raw_families)
        elif raw_families:
            selected = [raw_families]
        else:
            selected = list(_LEARNING_PLUGIN_FAMILY_OPTIONS)
        data["enabled_plugin_families"] = [
            str(item).strip()
            for item in selected
            if str(item).strip() in _LEARNING_PLUGIN_FAMILY_OPTIONS
        ]

        return data
