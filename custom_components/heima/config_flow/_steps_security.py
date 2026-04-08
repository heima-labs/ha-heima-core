"""Options flow: Security step."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_SECURITY
from ._common import _entity_selector, _object_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _SecurityStepsMixin:
    """Mixin for security step."""

    async def async_step_security(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        current = dict(self.options.get(OPT_SECURITY, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="security",
                data_schema=self._security_schema(current),
                description_placeholders={
                    "camera_sources_help": self._security_camera_evidence_help()
                },
            )

        if user_input.get("enabled") and not user_input.get("security_state_entity"):
            return self.async_show_form(
                step_id="security",
                data_schema=self._security_schema(user_input),
                errors={"security_state_entity": "required"},
                description_placeholders={
                    "camera_sources_help": self._security_camera_evidence_help()
                },
            )

        payload = dict(current)
        payload.update(user_input)
        payload["camera_evidence_sources"] = self._normalize_camera_evidence_sources(
            payload.get("camera_evidence_sources")
        )
        self._update_options({OPT_SECURITY: payload})
        return await self.async_step_init()

    def _security_menu_summary(self) -> str:
        security = dict(self.options.get(OPT_SECURITY, {}))
        coordinator_getter = getattr(self, "_get_coordinator", None)
        coordinator = coordinator_getter() if callable(coordinator_getter) else None
        if coordinator is not None:
            from ..diagnostics import _security_presence_summary_diagnostics

            summary = _security_presence_summary_diagnostics(coordinator)
            configured_total = int(summary.get("configured_total") or 0)
            ready_tonight_total = int(summary.get("ready_tonight_total") or 0)
            blocked_total = int(summary.get("blocked_total") or 0)
            camera_count = len(security.get("camera_evidence_sources", []) or [])
            if configured_total > 0:
                return (
                    f"simulazioni {configured_total}"
                    f" | pronte {ready_tonight_total}"
                    f" | bloccate {blocked_total}"
                    + (f" | camere {camera_count}" if camera_count > 0 else "")
                )
        if security.get("enabled") and security.get("security_state_entity"):
            suffix = ""
            camera_count = len(security.get("camera_evidence_sources", []) or [])
            if camera_count > 0:
                suffix = f" | cameras {camera_count}"
            return f"{security['security_state_entity']}{suffix}"
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
                vol.Optional(
                    "camera_evidence_sources",
                    default=self._camera_evidence_sources_to_editor(
                        defaults.get("camera_evidence_sources", [])
                    ),
                ): _object_selector(),
            }
        )
        return self._with_suggested(schema, defaults)

    def _security_camera_evidence_help(self) -> str:
        language = str(getattr(self, "_flow_language", lambda: "en")() or "en").lower()
        if language.startswith("it"):
            return (
                "Formato atteso per ogni camera: "
                "{id, display_name?, enabled, role, motion_entity?, person_entity?, "
                "vehicle_entity?, contact_entity?, return_home_contributor?, security_priority?}.\n"
                "Ruoli consigliati: entry, garage.\n"
                "Esempio: "
                '{"entry_cam": {"display_name": "Front Door Camera", "enabled": true, "role": "entry", '
                '"person_entity": "binary_sensor.front_cam_person", '
                '"contact_entity": "binary_sensor.front_door_contact", '
                '"return_home_contributor": true, "security_priority": "high"}}'
            )
        return (
            "Expected shape for each camera source: "
            "{id, display_name?, enabled, role, motion_entity?, person_entity?, "
            "vehicle_entity?, contact_entity?, return_home_contributor?, security_priority?}.\n"
            "Recommended roles: entry, garage.\n"
            "Example: "
            '{"entry_cam": {"display_name": "Front Door Camera", "enabled": true, "role": "entry", '
            '"person_entity": "binary_sensor.front_cam_person", '
            '"contact_entity": "binary_sensor.front_door_contact", '
            '"return_home_contributor": true, "security_priority": "high"}}'
        )

    @staticmethod
    def _camera_evidence_sources_to_editor(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {
                str(k): dict(v) for k, v in value.items() if str(k).strip() and isinstance(v, dict)
            }
        if not isinstance(value, list):
            return {}
        editor: dict[str, Any] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("id") or "").strip()
            if not source_id:
                continue
            editor[source_id] = dict(item)
        return editor

    @staticmethod
    def _normalize_camera_evidence_sources(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]
        if not isinstance(value, dict):
            return []
        normalized: list[dict[str, Any]] = []
        for key, raw in value.items():
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            source_id = str(item.get("id") or key or "").strip()
            if not source_id:
                continue
            item["id"] = source_id
            normalized.append(item)
        return normalized
