"""Options flow: Security step."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import HOUSE_STATES_CANONICAL, OPT_SECURITY
from ._camera_privacy_policy import (
    CAMERA_PRIVACY_ACTIONS,
    CAMERA_PRIVACY_ALARM_STATES,
    CAMERA_PRIVACY_HOUSE_FILTERS,
    CameraPrivacyPolicyRow,
    apply_camera_privacy_policy_rows_to_options,
    parse_camera_privacy_policy_rows_from_options,
)
from ._common import _entity_selector, _is_valid_slug, _object_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _SecurityStepsMixin:
    """Mixin for security step."""

    _SECURITY_PRIORITIES = {"low", "normal", "high"}

    async def async_step_camera_privacy_policies(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        policies = parse_camera_privacy_policy_rows_from_options(self.options)
        policy_options = self._camera_privacy_policy_options(policies)
        if user_input is None:
            return self.async_show_form(
                step_id="camera_privacy_policies",
                data_schema=self._camera_privacy_policy_action_schema(policy_options),
                description_placeholders={
                    "summary": self._camera_privacy_policy_summary(policies),
                },
            )

        action = str(user_input.get("action") or "").strip()
        if action == "back":
            return await self.async_step_init()
        if action == "add":
            self._editing_camera_privacy_reaction_id = None
            return await self.async_step_camera_privacy_policy_form()
        if action not in {"edit", "delete", "toggle_enabled"}:
            return self.async_show_form(
                step_id="camera_privacy_policies",
                data_schema=self._camera_privacy_policy_action_schema(policy_options),
                errors={"action": "invalid_selection"},
                description_placeholders={
                    "summary": self._camera_privacy_policy_summary(policies),
                },
            )

        reaction_id = str(user_input.get("policy") or "").strip()
        if not reaction_id or reaction_id not in policy_options:
            return self.async_show_form(
                step_id="camera_privacy_policies",
                data_schema=self._camera_privacy_policy_action_schema(policy_options),
                errors={"policy": "required"},
                description_placeholders={
                    "summary": self._camera_privacy_policy_summary(policies),
                },
            )
        self._editing_camera_privacy_reaction_id = reaction_id
        if action == "edit":
            return await self.async_step_camera_privacy_policy_form()
        if action == "toggle_enabled":
            return await self._toggle_camera_privacy_policy(reaction_id)
        return await self.async_step_camera_privacy_policy_delete_confirm()

    async def async_step_camera_privacy_policy_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        sources = self._camera_privacy_source_options()
        if not sources:
            return self.async_show_form(
                step_id="camera_privacy_policies",
                data_schema=self._camera_privacy_policy_action_schema({}),
                errors={"base": "no_camera_privacy_sources"},
                description_placeholders={"summary": "0 policies"},
            )
        editing_id = str(getattr(self, "_editing_camera_privacy_reaction_id", "") or "").strip()
        defaults = self._camera_privacy_policy_form_defaults(editing_id)
        if user_input is None:
            return self.async_show_form(
                step_id="camera_privacy_policy_form",
                data_schema=self._camera_privacy_policy_form_schema(sources, defaults),
            )

        row, errors = self._camera_privacy_policy_row_from_input(user_input, sources)
        if errors:
            return self.async_show_form(
                step_id="camera_privacy_policy_form",
                data_schema=self._camera_privacy_policy_form_schema(sources, user_input),
                errors=errors,
            )

        selected = self._parsed_camera_privacy_policy(editing_id)
        rows = self._managed_camera_privacy_rows(exclude_ids={editing_id} if editing_id else set())
        rows.append(row)
        replace_ids = {editing_id} if selected is not None and selected.imported else set()
        self.options = apply_camera_privacy_policy_rows_to_options(
            self.options,
            rows,
            replace_reaction_ids=replace_ids,
        )
        self._editing_camera_privacy_reaction_id = None
        return await self.async_step_camera_privacy_policies()

    async def async_step_camera_privacy_policy_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        reaction_id = str(getattr(self, "_editing_camera_privacy_reaction_id", "") or "").strip()
        if not reaction_id:
            return await self.async_step_camera_privacy_policies()
        if user_input is None:
            return self.async_show_form(
                step_id="camera_privacy_policy_delete_confirm",
                data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            )
        if bool(user_input.get("confirm")):
            selected = self._parsed_camera_privacy_policy(reaction_id)
            rows = self._managed_camera_privacy_rows(exclude_ids={reaction_id})
            replace_ids = {reaction_id} if selected is not None and selected.imported else set()
            self.options = apply_camera_privacy_policy_rows_to_options(
                self.options,
                rows,
                replace_reaction_ids=replace_ids,
            )
        self._editing_camera_privacy_reaction_id = None
        return await self.async_step_camera_privacy_policies()

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

        source_errors = self._validate_camera_evidence_sources(
            user_input.get("camera_evidence_sources")
        )
        if source_errors:
            return self.async_show_form(
                step_id="security",
                data_schema=self._security_schema(user_input),
                errors=source_errors,
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

    def _camera_privacy_policy_action_schema(self, policy_options: dict[str, str]) -> vol.Schema:
        schema_fields: dict[Any, Any] = {
            vol.Required("action", default="add"): vol.In(
                {
                    "add": "Add policy",
                    "edit": "Edit policy",
                    "delete": "Delete policy",
                    "toggle_enabled": "Enable/disable policy",
                    "back": "Back",
                }
            ),
        }
        if policy_options:
            schema_fields[vol.Optional("policy")] = vol.In(policy_options)
        return vol.Schema(schema_fields)

    def _camera_privacy_policy_form_schema(
        self,
        sources: dict[str, str],
        defaults: dict[str, Any],
    ) -> vol.Schema:
        schema = vol.Schema(
            {
                vol.Required(
                    "camera_source_id",
                    default=defaults.get("camera_source_id") or next(iter(sources.keys())),
                ): vol.In(sources),
                vol.Required(
                    "alarm_states",
                    default=defaults.get("alarm_states", []),
                ): cv.multi_select({state: state for state in CAMERA_PRIVACY_ALARM_STATES}),
                vol.Required(
                    "house_filter_mode",
                    default=defaults.get("house_filter_mode", "always"),
                ): vol.In({mode: mode for mode in CAMERA_PRIVACY_HOUSE_FILTERS}),
                vol.Optional(
                    "house_states",
                    default=defaults.get("house_states", []),
                ): cv.multi_select({state: state for state in HOUSE_STATES_CANONICAL}),
                vol.Required(
                    "privacy_action",
                    default=defaults.get("privacy_action", "turn_on"),
                ): vol.In({action: action for action in CAMERA_PRIVACY_ACTIONS}),
                vol.Optional("enabled", default=bool(defaults.get("enabled", True))): bool,
            }
        )
        return self._with_suggested(schema, defaults)

    def _camera_privacy_policy_row_from_input(
        self,
        user_input: dict[str, Any],
        sources: dict[str, str],
    ) -> tuple[CameraPrivacyPolicyRow | None, dict[str, str]]:
        source_id = str(user_input.get("camera_source_id") or "").strip()
        source = self._camera_privacy_source_by_id(source_id)
        if not source_id or source_id not in sources or source is None:
            return None, {"camera_source_id": "required"}
        alarm_states = tuple(self._normalize_multi_value(user_input.get("alarm_states")))
        house_filter_mode = str(user_input.get("house_filter_mode") or "always").strip()
        house_states = tuple(self._normalize_multi_value(user_input.get("house_states")))
        if not alarm_states:
            return None, {"alarm_states": "required"}
        if house_filter_mode in {"only", "except"} and not house_states:
            return None, {"house_states": "required"}
        try:
            return (
                CameraPrivacyPolicyRow(
                    camera_source_id=source_id,
                    camera_display_name=str(source.get("display_name") or source_id),
                    privacy_entity=str(source.get("privacy_entity") or ""),
                    alarm_states=alarm_states,
                    house_filter_mode=house_filter_mode,
                    house_states=house_states,
                    privacy_action=str(user_input.get("privacy_action") or "turn_on"),
                    enabled=bool(user_input.get("enabled", True)),
                ),
                {},
            )
        except ValueError:
            return None, {"base": "invalid"}

    def _camera_privacy_source_options(self) -> dict[str, str]:
        options: dict[str, str] = {}
        for source in (
            dict(self.options.get(OPT_SECURITY, {})).get("camera_evidence_sources", []) or []
        ):
            if not isinstance(source, dict):
                continue
            source_id = str(source.get("id") or "").strip()
            privacy_entity = str(source.get("privacy_entity") or "").strip()
            if source_id and privacy_entity.startswith("switch."):
                options[source_id] = str(source.get("display_name") or source_id)
        return options

    def _camera_privacy_source_by_id(self, source_id: str) -> dict[str, Any] | None:
        for source in (
            dict(self.options.get(OPT_SECURITY, {})).get("camera_evidence_sources", []) or []
        ):
            if isinstance(source, dict) and str(source.get("id") or "").strip() == source_id:
                return dict(source)
        return None

    @staticmethod
    def _camera_privacy_policy_options(policies: list[Any]) -> dict[str, str]:
        options: dict[str, str] = {}
        for parsed in policies:
            suffix = " (imported)" if bool(getattr(parsed, "imported", False)) else ""
            options[str(parsed.reaction_id)] = f"{parsed.label}{suffix}"
        return options

    @staticmethod
    def _camera_privacy_policy_summary(policies: list[Any]) -> str:
        managed = sum(1 for item in policies if not bool(getattr(item, "imported", False)))
        imported = sum(1 for item in policies if bool(getattr(item, "imported", False)))
        return f"{managed} managed | {imported} imported"

    def _camera_privacy_policy_form_defaults(self, reaction_id: str) -> dict[str, Any]:
        parsed = self._parsed_camera_privacy_policy(reaction_id)
        if parsed is None:
            return {"alarm_states": [], "house_filter_mode": "always", "house_states": []}
        row = parsed.row
        return {
            "camera_source_id": row.camera_source_id,
            "alarm_states": list(row.alarm_states),
            "house_filter_mode": row.house_filter_mode,
            "house_states": list(row.house_states),
            "privacy_action": row.privacy_action,
            "enabled": row.enabled,
        }

    def _parsed_camera_privacy_policy(self, reaction_id: str) -> Any | None:
        reaction_id = str(reaction_id or "").strip()
        if not reaction_id:
            return None
        for parsed in parse_camera_privacy_policy_rows_from_options(self.options):
            if parsed.reaction_id == reaction_id:
                return parsed
        return None

    def _managed_camera_privacy_rows(
        self, *, exclude_ids: set[str]
    ) -> list[CameraPrivacyPolicyRow]:
        rows: list[CameraPrivacyPolicyRow] = []
        for parsed in parse_camera_privacy_policy_rows_from_options(self.options):
            if parsed.imported or parsed.reaction_id in exclude_ids:
                continue
            rows.append(parsed.row)
        return rows

    async def _toggle_camera_privacy_policy(self, reaction_id: str) -> "FlowResult":
        selected = self._parsed_camera_privacy_policy(reaction_id)
        if selected is None:
            return await self.async_step_camera_privacy_policies()
        rows = self._managed_camera_privacy_rows(exclude_ids={reaction_id})
        rows.append(replace(selected.row, enabled=not selected.row.enabled))
        replace_ids = {reaction_id} if selected.imported else set()
        self.options = apply_camera_privacy_policy_rows_to_options(
            self.options,
            rows,
            replace_reaction_ids=replace_ids,
        )
        self._editing_camera_privacy_reaction_id = None
        return await self.async_step_camera_privacy_policies()

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
                "vehicle_entity?, contact_entity?, return_home_contributor?, security_priority?, "
                "privacy_entity?, manual_hold_entity?}.\n"
                "Ruoli consigliati: entry, garage.\n"
                "Nota: una camera può essere configurata SOLO con privacy_entity (senza altri campi di evidenza).\n"
                "Esempio (evidenza + privacy): "
                '{"entry_cam": {"display_name": "Front Door Camera", "enabled": true, "role": "entry", '
                '"person_entity": "binary_sensor.front_cam_person", '
                '"contact_entity": "binary_sensor.front_door_contact", '
                '"privacy_entity": "switch.front_cam_privacy", '
                '"manual_hold_entity": "input_boolean.heima_switch_manual_hold_front_cam", '
                '"return_home_contributor": true, "security_priority": "high"}}'
            )
        return (
            "Expected shape for each camera source: "
            "{id, display_name?, enabled, role, motion_entity?, person_entity?, "
            "vehicle_entity?, contact_entity?, return_home_contributor?, security_priority?, "
            "privacy_entity?, manual_hold_entity?}.\n"
            "Recommended roles: entry, garage.\n"
            "Note: a camera can be configured with ONLY privacy_entity (without other evidence fields).\n"
            "Example (evidence + privacy): "
            '{"entry_cam": {"display_name": "Front Door Camera", "enabled": true, "role": "entry", '
            '"person_entity": "binary_sensor.front_cam_person", '
            '"contact_entity": "binary_sensor.front_door_contact", '
            '"privacy_entity": "switch.front_cam_privacy", '
            '"manual_hold_entity": "input_boolean.heima_switch_manual_hold_front_cam", '
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

    def _validate_camera_evidence_sources(self, value: Any) -> dict[str, str]:
        if value in (None, "", [], {}):
            return {}

        sources: list[dict[str, Any]] = []
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    return {"camera_evidence_sources": "invalid"}
                sources.append(dict(item))
        elif isinstance(value, dict):
            for key, raw in value.items():
                if not isinstance(raw, dict):
                    return {"camera_evidence_sources": "invalid"}
                item = dict(raw)
                item.setdefault("id", str(key or "").strip())
                sources.append(item)
        else:
            return {"camera_evidence_sources": "invalid"}

        for item in sources:
            source_id = str(item.get("id") or "").strip()
            if not source_id or not _is_valid_slug(source_id):
                return {"camera_evidence_sources": "invalid_slug"}

            role = str(item.get("role") or "").strip()
            if not role:
                return {"camera_evidence_sources": "required"}

            security_priority = str(item.get("security_priority") or "").strip()
            if security_priority and security_priority not in self._SECURITY_PRIORITIES:
                return {"camera_evidence_sources": "invalid_selection"}

            if not any(
                str(item.get(field) or "").strip()
                for field in (
                    "motion_entity",
                    "person_entity",
                    "vehicle_entity",
                    "contact_entity",
                    "privacy_entity",  # Support camera with privacy-only configuration
                )
            ):
                return {"camera_evidence_sources": "required"}

            # Validate optional fields
            for item_field, expected_prefix in (
                ("privacy_entity", "switch."),
                ("manual_hold_entity", "input_boolean."),
            ):
                entity_value = str(item.get(item_field) or "").strip()
                if entity_value and not entity_value.startswith(expected_prefix):
                    return {"camera_evidence_sources": f"invalid_{item_field}"}

            privacy_action = str(item.get("privacy_action") or "").strip()
            if privacy_action and privacy_action not in {"turn_on", "turn_off"}:
                return {"camera_evidence_sources": "invalid_privacy_action"}

        return {}
