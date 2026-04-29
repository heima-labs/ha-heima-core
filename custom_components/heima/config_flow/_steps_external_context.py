"""Options flow: External Context step."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from ..const import OPT_EXTERNAL_CONTEXT
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

# Canonical slots with entity domain restrictions
_SLOT_DOMAINS: dict[str, list[str]] = {
    "outdoor_temp": ["sensor"],
    "outdoor_humidity": ["sensor"],
    "outdoor_lux": ["sensor"],
    "wind_speed": ["sensor"],
    "rain_last_1h": ["sensor"],
    "rain_forecast_next_6h": ["sensor"],
    "weather_condition": ["sensor"],
    "weather_alert_level": ["sensor"],
    "weather_alert_phenomena": ["sensor"],
}


class _ExternalContextStepsMixin:
    """Mixin for external context slot mapping step."""

    async def async_step_external_context(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        current = dict(self.options.get(OPT_EXTERNAL_CONTEXT, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="external_context",
                data_schema=self._external_context_schema(current),
            )

        normalized = self._normalize_external_context_payload(user_input)
        self._update_options({OPT_EXTERNAL_CONTEXT: normalized})
        return await self.async_step_init()

    def _external_context_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema = vol.Schema(
            {
                vol.Optional(slot): _entity_selector(domains)
                for slot, domains in _SLOT_DOMAINS.items()
            }
        )
        return self._with_suggested(schema, defaults)

    def _normalize_external_context_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for slot in _SLOT_DOMAINS:
            val = payload.get(slot)
            result[slot] = str(val).strip() if val else None
        return result
