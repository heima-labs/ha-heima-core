"""Options flow: Heating steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_HEATING
from ._common import (
    HEATING_APPLY_MODES,
    HEATING_BRANCH_TYPES,
    HEATING_HOUSE_STATES,
    _entity_selector,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _HeatingStepsMixin:
    """Mixin for heating steps."""

    async def async_step_heating(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        current = self._heating_config()
        if user_input is None:
            return self.async_show_form(
                step_id="heating", data_schema=self._heating_general_schema(current)
            )

        payload = self._normalize_heating_payload(user_input)
        errors = self._validate_heating_general(payload)
        if errors:
            return self.async_show_form(
                step_id="heating",
                data_schema=self._heating_general_schema(payload),
                errors=errors,
            )

        existing = self._normalize_heating_payload(self._heating_config())
        payload["override_branches"] = existing.get("override_branches", {})
        self._update_options({OPT_HEATING: payload})
        return await self.async_step_heating_branches_menu()

    async def async_step_heating_branches_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return self.async_show_menu(
            step_id="heating_branches_menu",
            menu_options=[
                "heating_branches_edit",
                "heating_branches_save",
            ],
            description_placeholders={"summary": self._heating_menu_summary()},
        )

    async def async_step_heating_branches_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        if user_input is None:
            schema = vol.Schema({vol.Required("house_state"): vol.In(HEATING_HOUSE_STATES)})
            return self.async_show_form(step_id="heating_branches_edit", data_schema=schema)

        house_state = str(user_input.get("house_state", "")).strip()
        if house_state not in HEATING_HOUSE_STATES:
            return await self.async_step_heating_branches_menu()
        self._editing_heating_house_state = house_state
        return await self.async_step_heating_branch_select()

    async def async_step_heating_branch_select(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Step 1: select branch type only."""
        house_state = self._editing_heating_house_state
        if not house_state:
            return await self.async_step_heating_branches_menu()

        current_branch = self._heating_override_branches().get(house_state, {})
        current_type = str(current_branch.get("branch", "disabled"))

        if user_input is None:
            schema = self._with_suggested(
                vol.Schema({vol.Required("branch"): vol.In(HEATING_BRANCH_TYPES)}),
                {"branch": current_type},
            )
            return self.async_show_form(step_id="heating_branch_select", data_schema=schema)

        branch = str(user_input.get("branch", "disabled")).strip()
        if branch not in HEATING_BRANCH_TYPES:
            branch = "disabled"
        self._editing_heating_branch = branch
        return await self.async_step_heating_branch_edit_form()

    async def async_step_heating_branch_edit_form(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Step 2: parameters for the selected branch type."""
        house_state = self._editing_heating_house_state
        branch = self._editing_heating_branch
        if not house_state or not branch:
            return await self.async_step_heating_branches_menu()

        # Skip parameter form for branch types with no parameters
        if branch == "disabled":
            heating = self._normalize_heating_payload(self._heating_config())
            branches = dict(heating.get("override_branches", {}))
            branches[house_state] = {"branch": "disabled"}
            heating["override_branches"] = branches
            self._update_options({OPT_HEATING: heating})
            return await self.async_step_heating_branches_menu()

        current_branch = self._heating_override_branches().get(house_state, {})
        defaults = dict(current_branch)
        defaults["branch"] = branch

        if user_input is None:
            return self.async_show_form(
                step_id="heating_branch_edit_form",
                data_schema=self._heating_branch_schema(defaults),
            )

        payload = self._normalize_heating_branch_payload({**user_input, "branch": branch})
        errors = self._validate_heating_branch(payload)
        if errors:
            return self.async_show_form(
                step_id="heating_branch_edit_form",
                data_schema=self._heating_branch_schema({**user_input, "branch": branch}),
                errors=errors,
            )

        heating = self._normalize_heating_payload(self._heating_config())
        branches = dict(heating.get("override_branches", {}))
        branches[house_state] = payload
        heating["override_branches"] = branches
        self._update_options({OPT_HEATING: heating})
        return await self.async_step_heating_branches_menu()

    async def async_step_heating_branches_save(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return await self.async_step_init()

    # ---- Schema ----

    def _heating_general_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        defaults = self._normalize_heating_payload(defaults)
        schema = vol.Schema(
            {
                vol.Required("climate_entity"): _entity_selector(["climate"]),
                vol.Required(
                    "apply_mode", default=defaults.get("apply_mode", "delegate_to_scheduler")
                ): vol.In(HEATING_APPLY_MODES),
                vol.Required(
                    "temperature_step", default=defaults.get("temperature_step", 0.5)
                ): vol.Coerce(float),
                vol.Optional(
                    "manual_override_guard", default=defaults.get("manual_override_guard", True)
                ): bool,
                vol.Optional("outdoor_temperature_entity"): _entity_selector(["sensor"]),
                vol.Optional("vacation_hours_from_start_entity"): _entity_selector(["sensor"]),
                vol.Optional("vacation_hours_to_end_entity"): _entity_selector(["sensor"]),
                vol.Optional("vacation_total_hours_entity"): _entity_selector(["sensor"]),
                vol.Optional("vacation_is_long_entity"): _entity_selector(["binary_sensor"]),
                vol.Optional("context_entities"): _entity_selector(
                    ["sensor", "weather", "binary_sensor", "input_number", "number"], multiple=True
                ),
            }
        )
        return self._with_suggested(schema, defaults)

    def _heating_branch_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        branch = str(defaults.get("branch", "disabled") or "disabled").strip()
        if branch not in HEATING_BRANCH_TYPES:
            branch = "disabled"
        schema_map: dict[Any, Any] = {}
        if branch == "fixed_target":
            schema_map[vol.Optional("target_temperature")] = vol.Coerce(float)
        elif branch == "vacation_curve":
            for key in (
                "vacation_ramp_down_h",
                "vacation_ramp_up_h",
                "vacation_min_temp",
                "vacation_comfort_temp",
                "vacation_min_total_hours_for_ramp",
            ):
                schema_map[vol.Optional(key)] = vol.Coerce(float)
        return self._with_suggested(vol.Schema(schema_map), defaults)

    # ---- Validators ----

    def _validate_heating_general(self, payload: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not payload.get("climate_entity"):
            errors["climate_entity"] = "required"
        try:
            if float(payload.get("temperature_step", 0)) <= 0:
                errors["temperature_step"] = "invalid_number"
        except (TypeError, ValueError):
            errors["temperature_step"] = "invalid_number"
        return errors

    def _validate_heating_branch(self, payload: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        branch = str(payload.get("branch", "disabled"))
        if branch == "fixed_target":
            try:
                if float(payload.get("target_temperature", 0)) <= 0:
                    errors["target_temperature"] = "invalid_number"
            except (TypeError, ValueError):
                errors["target_temperature"] = "invalid_number"
            return errors
        if branch == "vacation_curve":
            for key in (
                "vacation_ramp_down_h",
                "vacation_ramp_up_h",
                "vacation_min_total_hours_for_ramp",
            ):
                try:
                    if float(payload.get(key, -1)) < 0:
                        errors[key] = "invalid_number"
                except (TypeError, ValueError):
                    errors[key] = "invalid_number"
            for key in ("vacation_min_temp", "vacation_comfort_temp"):
                try:
                    if float(payload.get(key, 0)) <= 0:
                        errors[key] = "invalid_number"
                except (TypeError, ValueError):
                    errors[key] = "invalid_number"

            heating = self._normalize_heating_payload(self._heating_config())
            for key in (
                "outdoor_temperature_entity",
                "vacation_hours_from_start_entity",
                "vacation_hours_to_end_entity",
                "vacation_total_hours_entity",
                "vacation_is_long_entity",
            ):
                if not heating.get(key):
                    errors["branch"] = "missing_vacation_bindings"
                    break
        return errors

    # ---- Normalization ----

    def _normalize_heating_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        if data.get("climate_entity"):
            data["climate_entity"] = str(data["climate_entity"])
        else:
            data.pop("climate_entity", None)

        apply_mode = str(
            data.get("apply_mode", data.get("apply_mode_auto", "delegate_to_scheduler"))
            or "delegate_to_scheduler"
        ).strip()
        if apply_mode not in HEATING_APPLY_MODES:
            apply_mode = "delegate_to_scheduler"
        data["apply_mode"] = apply_mode
        data.pop("apply_mode_auto", None)

        try:
            data["temperature_step"] = float(data.get("temperature_step", 0.5))
        except (TypeError, ValueError):
            data["temperature_step"] = 0.5

        data["manual_override_guard"] = bool(data.get("manual_override_guard", True))

        for key in (
            "outdoor_temperature_entity",
            "vacation_hours_from_start_entity",
            "vacation_hours_to_end_entity",
            "vacation_total_hours_entity",
            "vacation_is_long_entity",
        ):
            if data.get(key):
                data[key] = str(data[key])
            else:
                data.pop(key, None)

        raw_ctx = data.get("context_entities")
        if isinstance(raw_ctx, list):
            data["context_entities"] = [str(e) for e in raw_ctx if e]
        elif raw_ctx:
            data["context_entities"] = [str(raw_ctx)]
        else:
            data.pop("context_entities", None)

        branches = data.get("override_branches", {})
        if isinstance(branches, dict):
            normalized_branches: dict[str, dict[str, Any]] = {}
            for house_state, branch_cfg in branches.items():
                state_key = str(house_state).strip()
                if state_key not in HEATING_HOUSE_STATES or not isinstance(branch_cfg, dict):
                    continue
                normalized_branches[state_key] = self._normalize_heating_branch_payload(branch_cfg)
            data["override_branches"] = normalized_branches
        else:
            data["override_branches"] = {}
        return data

    def _normalize_heating_branch_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        branch = str(payload.get("branch", "disabled") or "disabled").strip()
        if branch not in HEATING_BRANCH_TYPES:
            branch = "disabled"
        normalized: dict[str, Any] = {"branch": branch}
        if branch == "fixed_target":
            if payload.get("target_temperature") not in (None, ""):
                normalized["target_temperature"] = float(payload["target_temperature"])
            return normalized
        if branch == "vacation_curve":
            for key in (
                "vacation_ramp_down_h",
                "vacation_ramp_up_h",
                "vacation_min_temp",
                "vacation_comfort_temp",
                "vacation_min_total_hours_for_ramp",
            ):
                if payload.get(key) not in (None, ""):
                    normalized[key] = float(payload[key])
            return normalized
        return normalized
