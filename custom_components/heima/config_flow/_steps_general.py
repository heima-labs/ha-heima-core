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
    DEFAULT_HOUSE_STATE_CONFIG,
    OPT_HOUSE_SIGNALS,
    OPT_HOUSE_STATE_CONFIG,
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
            OPT_HOUSE_STATE_CONFIG: self._normalize_house_state_config(user_input),
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
        house_state_cfg = self._house_state_config()
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
        schema_map[
            vol.Optional(
                "media_active_entities",
                default=list(house_state_cfg.get("media_active_entities", [])),
            )
        ] = _entity_selector(["media_player", "binary_sensor", "sensor"], multiple=True)
        schema_map[
            vol.Optional(
                "sleep_charging_entities",
                default=list(house_state_cfg.get("sleep_charging_entities", [])),
            )
        ] = _entity_selector(["input_boolean", "binary_sensor", "sensor"], multiple=True)
        schema_map[
            vol.Optional("workday_entity", default=house_state_cfg.get("workday_entity"))
        ] = _entity_selector(["input_boolean", "binary_sensor", "sensor"])
        schema_map[
            vol.Optional("sleep_enter_min", default=house_state_cfg.get("sleep_enter_min", 10))
        ] = vol.All(vol.Coerce(int), vol.Range(min=0))
        schema_map[
            vol.Optional("sleep_exit_min", default=house_state_cfg.get("sleep_exit_min", 2))
        ] = vol.All(vol.Coerce(int), vol.Range(min=0))
        schema_map[
            vol.Optional("work_enter_min", default=house_state_cfg.get("work_enter_min", 5))
        ] = vol.All(vol.Coerce(int), vol.Range(min=0))
        schema_map[
            vol.Optional("relax_enter_min", default=house_state_cfg.get("relax_enter_min", 2))
        ] = vol.All(vol.Coerce(int), vol.Range(min=0))
        schema_map[
            vol.Optional("relax_exit_min", default=house_state_cfg.get("relax_exit_min", 10))
        ] = vol.All(vol.Coerce(int), vol.Range(min=0))
        schema_map[
            vol.Optional(
                "sleep_requires_media_off",
                default=house_state_cfg.get("sleep_requires_media_off", True),
            )
        ] = bool
        schema_map[
            vol.Optional(
                "sleep_charging_min_count",
                default=house_state_cfg.get("sleep_charging_min_count"),
            )
        ] = vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=0)))
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

    def _house_state_config(self) -> dict[str, Any]:
        current = self.options.get(OPT_HOUSE_STATE_CONFIG, {})
        merged = dict(DEFAULT_HOUSE_STATE_CONFIG)
        if isinstance(current, dict):
            merged.update(current)
        return merged

    def _normalize_house_state_config(self, user_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "media_active_entities": [
                str(entity_id).strip()
                for entity_id in list(user_input.get("media_active_entities", []) or [])
                if str(entity_id).strip()
            ],
            "sleep_charging_entities": [
                str(entity_id).strip()
                for entity_id in list(user_input.get("sleep_charging_entities", []) or [])
                if str(entity_id).strip()
            ],
            "workday_entity": str(user_input.get("workday_entity", "") or "").strip(),
            "sleep_enter_min": int(user_input.get("sleep_enter_min", 10)),
            "sleep_exit_min": int(user_input.get("sleep_exit_min", 2)),
            "work_enter_min": int(user_input.get("work_enter_min", 5)),
            "relax_enter_min": int(user_input.get("relax_enter_min", 2)),
            "relax_exit_min": int(user_input.get("relax_exit_min", 10)),
            "sleep_requires_media_off": bool(user_input.get("sleep_requires_media_off", True)),
            "sleep_charging_min_count": (
                int(user_input["sleep_charging_min_count"])
                if user_input.get("sleep_charging_min_count") not in (None, "")
                else None
            ),
        }
