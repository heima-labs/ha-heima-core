"""Shared reaction config-flow form schemas and normalizers."""

# mypy: ignore-errors

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..room_sources import (
    room_signal_bucket_labels,
    room_signal_entity_id,
    room_signal_has_burst,
    room_signal_names,
)
from ._common import (
    HEATING_HOUSE_STATES,
    _entity_selector,
    _number_box_selector,
)
from ._reaction_contextual_lighting import _ContextualLightingPolicyFormMixin
from ._reaction_helpers import parse_hhmm_to_min as _parse_hhmm_to_min

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_REDACTED_SENTINEL = "**REDACTED**"


class _ReactionFormHelpersMixin(_ContextualLightingPolicyFormMixin):
    """Mixin for shared reaction form schemas, renderers, and normalizers."""

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _admin_authored_security_presence_simulation_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._vacation_presence_simulation_editor_schema(
            defaults,
            include_delete=False,
        )

    def _admin_authored_lighting_action_options(self) -> dict[str, str]:
        language = self._flow_language()
        if language.startswith("it"):
            return {"on": "Accendi", "off": "Spegni"}
        return {"on": "Turn on", "off": "Turn off"}

    def _signal_threshold_mode_options(self) -> dict[str, str]:
        language = self._flow_language()
        if language.startswith("it"):
            return {
                "rise": "Aumento rapido",
                "drop": "Diminuzione rapida",
                "above": "Supera soglia",
                "below": "Scende sotto soglia",
                "switch_on": "Passa a on",
                "switch_off": "Passa a off",
                "state_change": "Cambio stato",
            }
        return {
            "rise": "Rapid rise",
            "drop": "Rapid drop",
            "above": "Crosses above threshold",
            "below": "Drops below threshold",
            "switch_on": "Switches on",
            "switch_off": "Switches off",
            "state_change": "State change",
        }

    def _admin_authored_room_signal_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._room_signal_assist_editor_schema(
            defaults,
            include_room_id=True,
            include_enabled=False,
            include_delete=False,
        )

    def _admin_authored_room_darkness_lighting_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._room_darkness_lighting_editor_schema(
            defaults,
            include_room_id=True,
            include_enabled=False,
            include_delete=False,
        )

    def _admin_authored_room_contextual_lighting_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        bucket_match_options = self._bucket_match_mode_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
                    vol.Required("primary_signal_name", default="room_lux"): str,
                    vol.Required("primary_bucket", default="ok"): str,
                    vol.Required("primary_bucket_match_mode", default="lte"): vol.In(
                        bucket_match_options
                    ),
                    vol.Required("preset", default="all_day_adaptive"): vol.In(
                        self._contextual_lighting_preset_options()
                    ),
                    vol.Required("light_entities"): _entity_selector(["light"], multiple=True),
                }
            ),
            defaults,
        )

    def _admin_authored_room_contextual_lighting_assist_json_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._contextual_lighting_policy_editor_schema(
            defaults,
            include_enabled=False,
            include_delete=False,
        )

    def _reactions_edit_room_signal_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._room_signal_assist_editor_schema(
            defaults,
            include_room_id=False,
            include_enabled=True,
            include_delete=True,
        )

    def _room_signal_assist_editor_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> vol.Schema:
        defaults = defaults or {}
        bucket_match_options = self._bucket_match_mode_options()
        trigger_mode_options = self._trigger_mode_options()
        schema_fields: dict[Any, Any] = {}
        if include_room_id:
            room_options = {room_id: room_id for room_id in self._room_ids()}
            schema_fields[vol.Required("room_id")] = vol.In(room_options)
        if include_enabled:
            schema_fields[vol.Optional("enabled", default=True)] = bool
        schema_fields.update(
            {
                vol.Required("primary_signal_name", default=""): str,
                vol.Required("primary_trigger_mode", default="bucket"): vol.In(
                    trigger_mode_options
                ),
                vol.Optional("primary_bucket", default=""): str,
                vol.Required("primary_bucket_match_mode", default="eq"): vol.In(
                    bucket_match_options
                ),
                vol.Optional("corroboration_signal_name", default=""): str,
                vol.Optional("corroboration_bucket", default=""): str,
                vol.Optional("corroboration_bucket_match_mode", default="eq"): vol.In(
                    bucket_match_options
                ),
                vol.Required("action_entities"): _entity_selector(
                    ["scene", "script"], multiple=True
                ),
            }
        )
        if include_delete:
            schema_fields[vol.Optional("delete_reaction", default=False)] = bool
        return self._with_suggested(vol.Schema(schema_fields), defaults)

    def _reactions_edit_room_contextual_lighting_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._contextual_lighting_policy_editor_schema(
            defaults,
            include_enabled=True,
            include_delete=True,
        )

    def _format_room_signals_placeholder(self, rooms: list[dict[str, Any]], room_id: str) -> str:
        """Return a human-readable signal/bucket map for description_placeholders."""
        signals = room_signal_names(rooms, room_id)
        if not signals:
            return "—"
        lines = []
        for signal_name in signals:
            labels = room_signal_bucket_labels(rooms, room_id, signal_name)
            lines.append(f"{signal_name}: {', '.join(labels) if labels else '—'}")
        return "\n".join(lines)

    def _show_room_darkness_lighting_editor(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        template_title: str = "",
        template_description: str = "",
        reaction_description: str = "",
        room_id: str = "",
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> "FlowResult":
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._room_darkness_lighting_editor_schema(
                defaults,
                include_room_id=include_room_id,
                include_enabled=include_enabled,
                include_delete=include_delete,
            ),
            errors=errors,
            description_placeholders={
                "template_title": template_title,
                "template_description": template_description,
                "reaction_description": reaction_description,
                "room_id": room_id,
                "available_signals": self._format_room_signals_placeholder(self._rooms(), room_id),
            },
        )

    def _show_room_signal_assist_editor(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        template_title: str = "",
        template_description: str = "",
        reaction_description: str = "",
        room_id: str = "",
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> "FlowResult":
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._room_signal_assist_editor_schema(
                defaults,
                include_room_id=include_room_id,
                include_enabled=include_enabled,
                include_delete=include_delete,
            ),
            errors=errors,
            description_placeholders={
                "template_title": template_title,
                "template_description": template_description,
                "reaction_description": reaction_description,
                "room_id": room_id,
                "available_signals": self._format_room_signals_placeholder(self._rooms(), room_id),
            },
        )

    def _show_admin_authored_room_vacancy_lighting_off_form(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        template_title: str = "",
        template_description: str = "",
    ) -> "FlowResult":
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._admin_authored_room_vacancy_lighting_off_schema(defaults),
            errors=errors,
            description_placeholders={
                "template_title": template_title,
                "template_description": template_description,
            },
        )

    def _show_room_vacancy_lighting_off_editor(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        reaction_description: str = "",
        room_id: str = "",
        include_enabled: bool,
        include_delete: bool,
    ) -> "FlowResult":
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._room_vacancy_lighting_off_editor_schema(
                defaults,
                include_room_id=False,
                include_enabled=include_enabled,
                include_delete=include_delete,
            ),
            errors=errors,
            description_placeholders={
                "reaction_description": reaction_description,
                "room_id": room_id,
            },
        )

    def _show_vacation_presence_simulation_editor(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        reaction_description: str = "",
        include_delete: bool,
    ) -> "FlowResult":
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._vacation_presence_simulation_editor_schema(
                defaults,
                include_delete=include_delete,
            ),
            errors=errors,
            description_placeholders={"reaction_description": reaction_description},
        )

    def _normalize_room_darkness_lighting_editor_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
        room_id: str | None,
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        rooms = self._rooms()
        errors: dict[str, str] = {}
        resolved_room_id = (
            str(user_input.get("room_id") or "").strip()
            if include_room_id
            else str(room_id or defaults.get("room_id") or "").strip()
        )
        primary_signal_name = str(
            user_input.get("primary_signal_name")
            or defaults.get("primary_signal_name")
            or "room_lux"
        ).strip()
        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode")
            or defaults.get("primary_bucket_match_mode")
            or "eq"
        ).strip()
        light_entities = [
            entity_id
            for entity_id in self._normalize_multi_value(user_input.get("light_entities"))
            if _REDACTED_SENTINEL not in entity_id
        ]
        action = str(user_input.get("action") or defaults.get("action") or "on").strip() or "on"

        if include_room_id and not resolved_room_id:
            errors["room_id"] = "required"
        if not light_entities:
            errors["light_entities"] = "required"

        valid_signals = room_signal_names(rooms, resolved_room_id) if resolved_room_id else []
        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif valid_signals and primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"

        if not errors.get("primary_signal_name") and resolved_room_id:
            valid_buckets = room_signal_bucket_labels(rooms, resolved_room_id, primary_signal_name)
            if not primary_bucket:
                errors["primary_bucket"] = "required"
                primary_bucket = str(defaults.get("primary_bucket") or "dim")
            elif valid_buckets and primary_bucket not in valid_buckets:
                errors["primary_bucket"] = "invalid_bucket"
        elif not primary_bucket:
            primary_bucket = str(defaults.get("primary_bucket") or "dim")

        if primary_bucket_match_mode not in self._bucket_match_mode_options():
            errors["primary_bucket_match_mode"] = "invalid_option"
            primary_bucket_match_mode = str(defaults.get("primary_bucket_match_mode") or "eq")

        brightness: int | None = None
        color_temp_kelvin: int | None = None
        if action == "on":
            try:
                brightness = int(user_input.get("brightness") or 0)
                if brightness < 1 or brightness > 255:
                    raise ValueError
            except (TypeError, ValueError):
                errors["brightness"] = "invalid_number"
            try:
                color_temp_kelvin = int(user_input.get("color_temp_kelvin") or 0)
                if color_temp_kelvin < 1500 or color_temp_kelvin > 9000:
                    raise ValueError
            except (TypeError, ValueError):
                errors["color_temp_kelvin"] = "invalid_number"

        current_input: dict[str, Any] = {
            "primary_signal_name": primary_signal_name
            or str(defaults.get("primary_signal_name") or "room_lux"),
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "light_entities": light_entities,
            "action": action,
            "brightness": user_input.get("brightness", defaults.get("brightness", 190)),
            "color_temp_kelvin": user_input.get(
                "color_temp_kelvin", defaults.get("color_temp_kelvin", 2850)
            ),
        }
        if include_room_id:
            current_input["room_id"] = resolved_room_id or str(defaults.get("room_id") or "")
        if include_enabled:
            current_input["enabled"] = bool(
                user_input.get("enabled", defaults.get("enabled", True))
            )
        if include_delete:
            current_input["delete_reaction"] = False

        primary_entity_id = room_signal_entity_id(rooms, resolved_room_id, primary_signal_name)
        resolved = {
            "room_id": resolved_room_id,
            "primary_signal_name": primary_signal_name or "room_lux",
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "primary_signal_entities": [primary_entity_id] if primary_entity_id else [],
            "light_entities": light_entities,
            "action": action,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "enabled": bool(current_input.get("enabled", True)),
        }
        return current_input, resolved, errors

    def _normalize_room_signal_assist_editor_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
        room_id: str | None,
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        rooms = self._rooms()
        errors: dict[str, str] = {}
        resolved_room_id = (
            str(user_input.get("room_id") or "").strip()
            if include_room_id
            else str(room_id or defaults.get("room_id") or "").strip()
        )
        primary_signal_name = str(
            user_input.get("primary_signal_name") or defaults.get("primary_signal_name") or ""
        ).strip()
        primary_trigger_mode = str(
            user_input.get("primary_trigger_mode")
            or defaults.get("primary_trigger_mode")
            or "bucket"
        ).strip()
        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode")
            or defaults.get("primary_bucket_match_mode")
            or "eq"
        ).strip()
        corroboration_signal_name = str(user_input.get("corroboration_signal_name") or "").strip()
        corroboration_bucket = str(user_input.get("corroboration_bucket") or "").strip()
        corroboration_bucket_match_mode = str(
            user_input.get("corroboration_bucket_match_mode")
            or defaults.get("corroboration_bucket_match_mode")
            or "eq"
        ).strip()
        action_entities = self._normalize_multi_value(user_input.get("action_entities"))

        if include_room_id and not resolved_room_id:
            errors["room_id"] = "required"
        if not action_entities:
            errors["action_entities"] = "required"

        valid_signals = room_signal_names(rooms, resolved_room_id) if resolved_room_id else []
        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif valid_signals and primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"

        if primary_trigger_mode not in self._trigger_mode_options():
            errors["primary_trigger_mode"] = "invalid_option"
        elif not errors.get("primary_signal_name"):
            if primary_trigger_mode == "burst":
                if not room_signal_has_burst(rooms, resolved_room_id, primary_signal_name):
                    errors["primary_trigger_mode"] = "no_burst_config"
            else:
                valid_buckets = room_signal_bucket_labels(
                    rooms, resolved_room_id, primary_signal_name
                )
                if not primary_bucket:
                    errors["primary_bucket"] = "required"
                elif primary_bucket not in valid_buckets:
                    errors["primary_bucket"] = "invalid_bucket"
                if primary_bucket_match_mode not in self._bucket_match_mode_options():
                    errors["primary_bucket_match_mode"] = "invalid_option"

        if corroboration_signal_name:
            if corroboration_signal_name not in valid_signals:
                errors["corroboration_signal_name"] = "invalid_signal_name"
            elif not errors.get("corroboration_signal_name") and corroboration_bucket:
                valid_corr_buckets = room_signal_bucket_labels(
                    rooms, resolved_room_id, corroboration_signal_name
                )
                if corroboration_bucket not in valid_corr_buckets:
                    errors["corroboration_bucket"] = "invalid_bucket"
        if corroboration_bucket_match_mode not in self._bucket_match_mode_options():
            errors["corroboration_bucket_match_mode"] = "invalid_option"

        current_input: dict[str, Any] = {
            "primary_signal_name": primary_signal_name
            or str(defaults.get("primary_signal_name") or ""),
            "primary_trigger_mode": primary_trigger_mode,
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "corroboration_signal_name": corroboration_signal_name,
            "corroboration_bucket": corroboration_bucket,
            "corroboration_bucket_match_mode": corroboration_bucket_match_mode,
            "action_entities": action_entities,
        }
        if include_room_id:
            current_input["room_id"] = resolved_room_id or str(defaults.get("room_id") or "")
        if include_enabled:
            current_input["enabled"] = bool(
                user_input.get("enabled", defaults.get("enabled", True))
            )
        if include_delete:
            current_input["delete_reaction"] = False

        primary_entity_id = room_signal_entity_id(rooms, resolved_room_id, primary_signal_name)
        primary_entities = [primary_entity_id] if primary_entity_id else []
        corroboration_entities: list[str] = []
        if corroboration_signal_name:
            corr_entity_id = room_signal_entity_id(
                rooms, resolved_room_id, corroboration_signal_name
            )
            if corr_entity_id:
                corroboration_entities = [corr_entity_id]

        resolved = {
            "room_id": resolved_room_id,
            "primary_signal_name": primary_signal_name,
            "primary_trigger_mode": primary_trigger_mode,
            "primary_bucket": primary_bucket if primary_trigger_mode == "bucket" else "",
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "primary_signal_entities": primary_entities,
            "corroboration_signal_name": corroboration_signal_name or "corroboration",
            "corroboration_bucket": corroboration_bucket,
            "corroboration_bucket_match_mode": corroboration_bucket_match_mode,
            "corroboration_signal_entities": corroboration_entities,
            "action_entities": action_entities,
            "enabled": bool(current_input.get("enabled", True)),
        }
        return current_input, resolved, errors

    def _normalize_admin_authored_room_vacancy_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        errors: dict[str, str] = {}
        room_id = str(user_input.get("room_id") or defaults.get("room_id") or "").strip()
        light_entities = self._normalize_multi_value(user_input.get("light_entities"))

        if not room_id:
            errors["room_id"] = "required"
        if not light_entities:
            errors["light_entities"] = "required"

        try:
            vacancy_delay_min = int(user_input.get("vacancy_delay_min") or 0)
            if vacancy_delay_min < 1 or vacancy_delay_min > 180:
                raise ValueError
        except (TypeError, ValueError):
            errors["vacancy_delay_min"] = "invalid_number"
            vacancy_delay_min = int(defaults["vacancy_delay_min"])

        current_input = {
            "room_id": room_id or defaults["room_id"],
            "light_entities": light_entities,
            "vacancy_delay_min": vacancy_delay_min,
        }
        resolved = {
            "room_id": room_id,
            "light_entities": light_entities,
            "vacancy_delay_min": vacancy_delay_min,
        }
        return current_input, resolved, errors

    def _normalize_room_vacancy_lighting_off_editor_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
        room_id: str,
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        resolved_room_id = (
            str(user_input.get("room_id") or "").strip() if include_room_id else room_id
        )
        current_input, resolved, errors = self._normalize_admin_authored_room_vacancy_submission(
            user_input=user_input,
            defaults={"room_id": resolved_room_id or room_id, **defaults},
        )
        if not include_room_id:
            current_input.pop("room_id", None)
        if include_enabled:
            current_input["enabled"] = bool(
                user_input.get("enabled", defaults.get("enabled", True))
            )
        if include_delete:
            current_input["delete_reaction"] = False
        resolved["room_id"] = resolved_room_id or room_id
        resolved["enabled"] = bool(current_input.get("enabled", True))
        return current_input, resolved, errors

    def _normalize_security_presence_simulation_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
        include_delete: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        min_jitter = self._coerce_optional_int(user_input.get("min_jitter_override_min"))
        max_jitter = self._coerce_optional_int(user_input.get("max_jitter_override_min"))
        max_events = self._coerce_optional_int(user_input.get("max_events_per_evening_override"))
        latest_end = str(user_input.get("latest_end_time_override") or "").strip()
        errors: dict[str, str] = {}
        if latest_end and _parse_hhmm_to_min(latest_end) is None:
            errors["latest_end_time_override"] = "invalid_hhmm"
        if min_jitter is not None and min_jitter < 0:
            errors["min_jitter_override_min"] = "invalid_number"
        if max_jitter is not None and max_jitter < 0:
            errors["max_jitter_override_min"] = "invalid_number"
        if min_jitter is not None and max_jitter is not None and min_jitter > max_jitter:
            errors["max_jitter_override_min"] = "invalid_number"
        if max_events is not None and max_events <= 0:
            errors["max_events_per_evening_override"] = "invalid_number"

        current_input = {
            "enabled": bool(user_input.get("enabled", defaults.get("enabled", True))),
            "allowed_rooms": self._normalize_multi_value(
                user_input.get("allowed_rooms", defaults.get("allowed_rooms", []))
            ),
            "allowed_entities": self._normalize_multi_value(
                user_input.get("allowed_entities", defaults.get("allowed_entities", []))
            ),
            "requires_dark_outside": bool(
                user_input.get("requires_dark_outside", defaults.get("requires_dark_outside", True))
            ),
            "simulation_aggressiveness": str(
                user_input.get(
                    "simulation_aggressiveness",
                    defaults.get("simulation_aggressiveness", "medium"),
                )
                or "medium"
            ),
            "min_jitter_override_min": min_jitter,
            "max_jitter_override_min": max_jitter,
            "max_events_per_evening_override": max_events,
            "latest_end_time_override": latest_end,
            "skip_if_presence_detected": bool(
                user_input.get(
                    "skip_if_presence_detected",
                    defaults.get("skip_if_presence_detected", True),
                )
            ),
        }
        if include_delete:
            current_input["delete_reaction"] = False

        resolved = dict(current_input)
        return current_input, resolved, errors

    def _normalize_scheduled_routine_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
        include_enabled: bool,
        include_delete: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        errors: dict[str, str] = {}
        weekday = str(user_input.get("weekday") or defaults.get("weekday") or "0").strip()
        scheduled_time = str(
            user_input.get("scheduled_time") or defaults.get("scheduled_time") or "20:00"
        ).strip()
        routine_kind = str(
            user_input.get("routine_kind") or defaults.get("routine_kind") or "scene"
        ).strip()
        target_entities = self._normalize_multi_value(user_input.get("target_entities"))
        entity_action = str(
            user_input.get("entity_action") or defaults.get("entity_action") or "turn_on"
        ).strip()
        house_state_in = self._normalize_multi_value(user_input.get("house_state_in"))
        skip_if_anyone_home = bool(
            user_input.get("skip_if_anyone_home", defaults.get("skip_if_anyone_home", False))
        )

        if weekday not in self._weekday_options():
            errors["weekday"] = "invalid_option"
        scheduled_min = _parse_hhmm_to_min(scheduled_time)
        if scheduled_min is None:
            errors["scheduled_time"] = "invalid_hhmm"
        if routine_kind not in self._scheduled_routine_kind_options():
            errors["routine_kind"] = "invalid_option"
        if entity_action not in self._scheduled_routine_entity_action_options():
            errors["entity_action"] = "invalid_option"
        if not target_entities:
            errors["target_entities"] = "required"

        allowed_domains = {
            "scene": {"scene"},
            "script": {"script"},
            "entity_action": {"light", "switch", "input_boolean"},
        }.get(routine_kind, set())
        if target_entities and any(
            "." not in entity_id or entity_id.split(".", 1)[0] not in allowed_domains
            for entity_id in target_entities
        ):
            errors["target_entities"] = "invalid_target_domain"

        current_input: dict[str, Any] = {
            "weekday": weekday,
            "scheduled_time": scheduled_time,
            "routine_kind": routine_kind,
            "target_entities": target_entities,
            "entity_action": entity_action,
            "house_state_in": house_state_in,
            "skip_if_anyone_home": skip_if_anyone_home,
        }
        if include_enabled:
            current_input["enabled"] = bool(
                user_input.get("enabled", defaults.get("enabled", True))
            )
        if include_delete:
            current_input["delete_reaction"] = False

        resolved = {
            "weekday": int(weekday) if weekday in self._weekday_options() else 0,
            "scheduled_min": scheduled_min,
            "routine_kind": routine_kind,
            "target_entities": target_entities,
            "entity_action": entity_action,
            "house_state_in": house_state_in,
            "skip_if_anyone_home": skip_if_anyone_home,
            "enabled": bool(current_input.get("enabled", True)),
        }
        return current_input, resolved, errors

    def _admin_authored_room_vacancy_lighting_off_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._room_vacancy_lighting_off_editor_schema(
            defaults,
            include_room_id=True,
            include_enabled=False,
            include_delete=False,
        )

    def _admin_authored_scheduled_routine_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._scheduled_routine_editor_schema(
            defaults,
            include_enabled=False,
            include_delete=False,
        )

    def _scheduled_routine_editor_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_enabled: bool,
        include_delete: bool,
    ) -> vol.Schema:
        defaults = defaults or {}
        schema_dict: dict[Any, Any] = {}
        if include_enabled:
            schema_dict[vol.Optional("enabled", default=bool(defaults.get("enabled", True)))] = bool
        schema_dict.update(
            {
                vol.Required("weekday", default="0"): vol.In(self._weekday_options()),
                vol.Required("scheduled_time", default="20:00"): str,
                vol.Required("routine_kind", default="scene"): vol.In(
                    self._scheduled_routine_kind_options()
                ),
                vol.Optional("target_entities"): _entity_selector(
                    ["scene", "script", "light", "switch", "input_boolean"],
                    multiple=True,
                ),
                vol.Optional("entity_action", default="turn_on"): vol.In(
                    self._scheduled_routine_entity_action_options()
                ),
                vol.Optional("house_state_in", default=defaults.get("house_state_in", [])): (
                    cv.multi_select({state: state for state in HEATING_HOUSE_STATES})
                ),
                vol.Optional(
                    "skip_if_anyone_home",
                    default=bool(defaults.get("skip_if_anyone_home", False)),
                ): bool,
            }
        )
        if include_delete:
            schema_dict[vol.Optional("delete_reaction", default=False)] = bool
        return self._with_suggested(vol.Schema(schema_dict), defaults)

    def _room_vacancy_lighting_off_editor_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        schema_dict: dict[Any, Any] = {}
        if include_room_id:
            schema_dict[vol.Required("room_id")] = vol.In(room_options)
        if include_enabled:
            schema_dict[vol.Optional("enabled", default=bool(defaults.get("enabled", True)))] = bool
        schema_dict[vol.Required("light_entities")] = _entity_selector(["light"], multiple=True)
        schema_dict[vol.Required("vacancy_delay_min", default=5)] = _number_box_selector(
            min_value=1, max_value=180, step=1
        )
        if include_delete:
            schema_dict[vol.Optional("delete_reaction", default=False)] = bool
        return self._with_suggested(vol.Schema(schema_dict), defaults)

    def _vacation_presence_simulation_editor_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_delete: bool,
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        aggressiveness = (
            {"low": "Bassa", "medium": "Media", "high": "Alta"}
            if self._flow_language().startswith("it")
            else {"low": "Low", "medium": "Medium", "high": "High"}
        )
        schema_dict: dict[Any, Any] = {
            vol.Required("enabled", default=bool(defaults.get("enabled", True))): bool,
            vol.Optional(
                "allowed_rooms",
                default=defaults.get("allowed_rooms", []),
            ): cv.multi_select(room_options),
            vol.Optional("allowed_entities"): _entity_selector(["light"], multiple=True),
            vol.Required(
                "requires_dark_outside",
                default=bool(defaults.get("requires_dark_outside", True)),
            ): bool,
            vol.Required(
                "simulation_aggressiveness",
                default=str(defaults.get("simulation_aggressiveness", "medium") or "medium"),
            ): vol.In(aggressiveness),
            vol.Optional(
                "min_jitter_override_min", default=defaults.get("min_jitter_override_min")
            ): vol.Any(None, _number_box_selector(min_value=0, step=1)),
            vol.Optional(
                "max_jitter_override_min", default=defaults.get("max_jitter_override_min")
            ): vol.Any(None, _number_box_selector(min_value=0, step=1)),
            vol.Optional(
                "max_events_per_evening_override",
                default=defaults.get("max_events_per_evening_override"),
            ): vol.Any(None, _number_box_selector(min_value=1, step=1)),
            vol.Optional(
                "latest_end_time_override",
                default=str(defaults.get("latest_end_time_override", "") or ""),
            ): str,
            vol.Required(
                "skip_if_presence_detected",
                default=bool(defaults.get("skip_if_presence_detected", True)),
            ): bool,
        }
        if include_delete:
            schema_dict[vol.Optional("delete_reaction", default=False)] = bool
        return self._with_suggested(vol.Schema(schema_dict), defaults)

    def _show_scheduled_routine_editor(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        template_title: str = "",
        template_description: str = "",
        reaction_description: str = "",
        include_enabled: bool,
        include_delete: bool,
    ) -> "FlowResult":
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._scheduled_routine_editor_schema(
                defaults,
                include_enabled=include_enabled,
                include_delete=include_delete,
            ),
            errors=errors,
            description_placeholders={
                "template_title": template_title,
                "template_description": template_description,
                "reaction_description": reaction_description,
            },
        )

    def _reactions_edit_room_lighting_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        return self._room_darkness_lighting_editor_schema(
            defaults,
            include_room_id=False,
            include_enabled=True,
            include_delete=True,
        )

    def _room_darkness_lighting_editor_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_room_id: bool,
        include_enabled: bool,
        include_delete: bool,
    ) -> vol.Schema:
        defaults = defaults or {}
        action_options = self._admin_authored_lighting_action_options()
        bucket_match_options = self._bucket_match_mode_options()
        schema_fields: dict[Any, Any] = {}
        if include_room_id:
            room_options = {room_id: room_id for room_id in self._room_ids()}
            schema_fields[vol.Required("room_id")] = vol.In(room_options)
        if include_enabled:
            schema_fields[vol.Optional("enabled", default=True)] = bool
        schema_fields.update(
            {
                vol.Required("primary_signal_name", default="room_lux"): str,
                vol.Required("primary_bucket", default="dim"): str,
                vol.Required("primary_bucket_match_mode", default="eq"): vol.In(
                    bucket_match_options
                ),
                vol.Required("light_entities"): _entity_selector(["light"], multiple=True),
                vol.Required("action", default="on"): vol.In(action_options),
                vol.Optional("brightness", default=190): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=255)
                ),
                vol.Optional("color_temp_kelvin", default=2850): vol.All(
                    vol.Coerce(int), vol.Range(min=1500, max=9000)
                ),
            }
        )
        if include_delete:
            schema_fields[vol.Optional("delete_reaction", default=False)] = bool
        return self._with_suggested(vol.Schema(schema_fields), defaults)

    def _weekday_options(self) -> dict[str, str]:
        language = self._flow_language()
        return {str(index): self._weekday_label(index, language) for index in range(7)}

    def _scheduled_routine_kind_options(self) -> dict[str, str]:
        language = self._flow_language()
        if language.startswith("it"):
            return {
                "scene": "Scena",
                "script": "Script",
                "entity_action": "Azione entità",
            }
        return {
            "scene": "Scene",
            "script": "Script",
            "entity_action": "Entity action",
        }

    def _scheduled_routine_entity_action_options(self) -> dict[str, str]:
        language = self._flow_language()
        if language.startswith("it"):
            return {"turn_on": "Accendi", "turn_off": "Spegni"}
        return {"turn_on": "Turn on", "turn_off": "Turn off"}

    @staticmethod
    def _bucket_match_mode_options() -> dict[str, str]:
        return {
            "eq": "Exact bucket",
            "lte": "Bucket or lower",
            "gte": "Bucket or higher",
        }

    @staticmethod
    def _trigger_mode_options() -> dict[str, str]:
        return {
            "bucket": "Bucket (steady-state)",
            "burst": "Burst (rapid change)",
        }
