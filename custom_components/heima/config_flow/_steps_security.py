"""Options flow: Security step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_SECURITY
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _SecurityStepsMixin:
    """Mixin for security step."""

    async def async_step_security(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        current = dict(self.options.get(OPT_SECURITY, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="security", data_schema=self._security_schema(current)
            )

        if user_input.get("enabled") and not user_input.get("security_state_entity"):
            return self.async_show_form(
                step_id="security",
                data_schema=self._security_schema(user_input),
                errors={"security_state_entity": "required"},
            )

        self._update_options({OPT_SECURITY: user_input})
        return await self.async_step_init()

    def _security_menu_summary(self) -> str:
        security = dict(self.options.get(OPT_SECURITY, {}))
        coordinator_getter = getattr(self, "_get_coordinator", None)
        coordinator = coordinator_getter() if callable(coordinator_getter) else None
        if coordinator is not None:
            from ..diagnostics import _security_presence_summary_diagnostics

            summary = _security_presence_summary_diagnostics(coordinator)
            configured_total = int(summary.get("configured_total") or 0)
            active_tonight_total = int(summary.get("active_tonight_total") or 0)
            blocked_total = int(summary.get("blocked_total") or 0)
            if configured_total > 0:
                return (
                    f"simulazioni {configured_total}"
                    f" | attive {active_tonight_total}"
                    f" | bloccate {blocked_total}"
                )
        if security.get("enabled") and security.get("security_state_entity"):
            return str(security["security_state_entity"])
        return "—"

    def _security_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        schema = vol.Schema(
            {
                vol.Optional("enabled", default=defaults.get("enabled", False)): bool,
                vol.Optional("security_state_entity"): _entity_selector(
                    ["alarm_control_panel", "sensor", "binary_sensor"]
                ),
                vol.Optional(
                    "armed_away_value", default=defaults.get("armed_away_value", "armed_away")
                ): cv.string,
                vol.Optional(
                    "armed_home_value", default=defaults.get("armed_home_value", "armed_home")
                ): cv.string,
            }
        )
        return self._with_suggested(schema, defaults)
