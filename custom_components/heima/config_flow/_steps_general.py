"""Options flow: General & House Signals step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_ENGINE_ENABLED,
    CONF_LANGUAGE,
    CONF_TIMEZONE,
    DEFAULT_ENGINE_ENABLED,
    OPT_HOUSE_SIGNALS,
    OPT_LIGHTING_APPLY_MODE,
    DEFAULT_LIGHTING_APPLY_MODE,
)
from ._common import (
    LIGHTING_APPLY_MODES,
    _default_language,
    _default_timezone,
    _entity_selector,
    _normalize_house_signal_bindings,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _GeneralStepsMixin:
    """Mixin for general + house signals step."""

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        schema = self._general_schema()
        if user_input is None:
            return self.async_show_form(step_id="general", data_schema=schema)

        errors: dict[str, str] = {}
        timezone_value = user_input.get(CONF_TIMEZONE, _default_timezone(self.hass))
        if not dt_util.get_time_zone(timezone_value):
            errors[CONF_TIMEZONE] = "invalid_time_zone"

        if errors:
            return self.async_show_form(step_id="general", data_schema=schema, errors=errors)

        self._update_options({
            CONF_ENGINE_ENABLED: user_input.get(CONF_ENGINE_ENABLED, DEFAULT_ENGINE_ENABLED),
            CONF_TIMEZONE: timezone_value,
            CONF_LANGUAGE: user_input.get(CONF_LANGUAGE, _default_language(self.hass)),
            OPT_LIGHTING_APPLY_MODE: user_input.get(OPT_LIGHTING_APPLY_MODE, DEFAULT_LIGHTING_APPLY_MODE),
            OPT_HOUSE_SIGNALS: self._normalize_general_house_signals(user_input),
        })
        return await self.async_step_init()

    def _general_schema(self) -> vol.Schema:
        schema_map: dict[Any, Any] = {
            vol.Optional(
                CONF_ENGINE_ENABLED,
                default=self.options.get(CONF_ENGINE_ENABLED, DEFAULT_ENGINE_ENABLED),
            ): bool,
            vol.Optional(
                CONF_TIMEZONE,
                default=self.options.get(CONF_TIMEZONE, _default_timezone(self.hass)),
            ): cv.string,
            vol.Optional(
                CONF_LANGUAGE,
                default=self.options.get(CONF_LANGUAGE, _default_language(self.hass)),
            ): cv.string,
            vol.Optional(
                OPT_LIGHTING_APPLY_MODE,
                default=self.options.get(OPT_LIGHTING_APPLY_MODE, DEFAULT_LIGHTING_APPLY_MODE),
            ): vol.In(LIGHTING_APPLY_MODES),
        }
        house_signals = self._house_signal_bindings()
        for signal_name, label_key in (
            ("vacation_mode", "vacation_mode_entity"),
            ("guest_mode", "guest_mode_entity"),
            ("sleep_window", "sleep_window_entity"),
            ("relax_mode", "relax_mode_entity"),
            ("work_window", "work_window_entity"),
        ):
            schema_map[
                vol.Optional(label_key, default=house_signals.get(signal_name))
            ] = _entity_selector(["input_boolean", "binary_sensor", "sensor"])
        return vol.Schema(schema_map)

    def _house_signal_bindings(self) -> dict[str, str]:
        return _normalize_house_signal_bindings(self.options.get(OPT_HOUSE_SIGNALS, {}))

    def _normalize_general_house_signals(self, user_input: dict[str, Any]) -> dict[str, str]:
        raw = {
            "vacation_mode": user_input.get("vacation_mode_entity"),
            "guest_mode": user_input.get("guest_mode_entity"),
            "sleep_window": user_input.get("sleep_window_entity"),
            "relax_mode": user_input.get("relax_mode_entity"),
            "work_window": user_input.get("work_window_entity"),
        }
        return _normalize_house_signal_bindings(raw)
