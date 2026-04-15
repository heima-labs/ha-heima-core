"""Options flow: Reactions step (persisted mute management + proposal review)."""

# mypy: ignore-errors

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN, OPT_REACTIONS
from ..room_sources import (
    room_signal_bucket_labels,
    room_signal_entity_id,
    room_signal_has_burst,
    room_signal_names,
)
from ..runtime.analyzers import create_builtin_learning_plugin_registry
from ..runtime.analyzers.base import ReactionProposal
from ..runtime.reactions import create_builtin_reaction_plugin_registry, resolve_reaction_type
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)
_REDACTED_SENTINEL = "**REDACTED**"


class _ReactionsStepsMixin:
    """Mixin for reactions step."""

    @staticmethod
    def _reaction_type_from_cfg(cfg: dict[str, Any]) -> str:
        return resolve_reaction_type(cfg)

    @staticmethod
    def _has_redacted_payload(value: Any) -> bool:
        if isinstance(value, str):
            return _REDACTED_SENTINEL in value
        if isinstance(value, dict):
            return any(_ReactionsStepsMixin._has_redacted_payload(item) for item in value.values())
        if isinstance(value, list):
            return any(_ReactionsStepsMixin._has_redacted_payload(item) for item in value)
        return False

    def _admin_authored_identity_conflicts(self, proposal: ReactionProposal) -> bool:
        """Return True if a configured reaction already covers this identity key."""
        identity_key = str(proposal.identity_key or "").strip()
        if not identity_key:
            return False
        configured = dict(self._reactions_options().get("configured", {}))
        for raw in configured.values():
            reaction_cfg = _safe_mapping(raw)
            if str(reaction_cfg.get("source_proposal_identity_key") or "").strip() == identity_key:
                return True
        return False

    async def _store_admin_authored_reaction_directly(
        self, proposal: ReactionProposal
    ) -> "FlowResult":
        """Persist an admin-authored reaction directly to configured, bypassing proposals review."""
        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels: dict[str, str] = dict(reactions_cfg.get("labels", {}))
        reaction_id = proposal.proposal_id
        configured[reaction_id] = self._configured_reaction_from_proposal(proposal)
        labels[reaction_id] = proposal.description
        reactions_cfg["configured"] = configured
        reactions_cfg["labels"] = labels
        self._store_reactions_options(reactions_cfg)
        return await self.async_step_init()

    async def async_step_admin_authored_create(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Start an admin-authored automation request from plugin-declared templates."""
        template_options = self._admin_authored_template_options()
        if not template_options:
            return await self.async_step_init()

        if user_input is None:
            schema = vol.Schema({vol.Required("template_id"): vol.In(template_options)})
            return self.async_show_form(
                step_id="admin_authored_create",
                data_schema=schema,
                description_placeholders={
                    "availability_notes": self._admin_authored_template_availability_notes()
                },
            )

        template_id = str(user_input.get("template_id") or "").strip()
        available, reason = self._admin_authored_template_availability(template_id)
        if not available:
            schema = vol.Schema({vol.Required("template_id"): vol.In(template_options)})
            return self.async_show_form(
                step_id="admin_authored_create",
                data_schema=schema,
                errors={"base": "template_unavailable"},
                description_placeholders={
                    "availability_notes": reason
                    or self._admin_authored_template_availability_notes()
                },
            )
        template = self._admin_authored_template(template_id)
        flow_step_id = str(getattr(template, "flow_step_id", "") or "").strip()
        if template is not None and flow_step_id:
            step = getattr(self, f"async_step_{flow_step_id}", None)
            if callable(step):
                self._selected_admin_authored_template_id = template_id
                return await step()
        return await self.async_step_init()

    async def async_step_admin_authored_lighting_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored lighting schedule proposal."""
        template = self._admin_authored_template("lighting.scene_schedule.basic")
        room_ids = self._room_ids()
        if template is None or not room_ids:
            return await self.async_step_init()

        defaults = {
            "room_id": room_ids[0],
            "weekday": "0",
            "scheduled_time": "20:00",
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_lighting_schedule",
                data_schema=self._admin_authored_lighting_schedule_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        room_id = str(user_input.get("room_id") or "").strip()
        action = str(user_input.get("action") or "on").strip()
        entity_ids = self._normalize_multi_value(user_input.get("light_entities"))
        weekday_raw = user_input.get("weekday")
        scheduled_time = str(user_input.get("scheduled_time") or "").strip()

        if not room_id:
            errors["room_id"] = "required"
        if not entity_ids:
            errors["light_entities"] = "required"

        weekday: int | None = None
        try:
            weekday = int(weekday_raw)
            if weekday < 0 or weekday > 6:
                raise ValueError
        except (TypeError, ValueError):
            errors["weekday"] = "invalid_number"

        scheduled_min = _parse_hhmm_to_min(scheduled_time)
        if scheduled_min is None:
            errors["scheduled_time"] = "invalid_hhmm"

        brightness = None
        color_temp_kelvin = None
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

        if errors:
            return self.async_show_form(
                step_id="admin_authored_lighting_schedule",
                data_schema=self._admin_authored_lighting_schedule_schema(
                    {
                        "room_id": room_id or defaults["room_id"],
                        "weekday": str(weekday_raw or defaults["weekday"]),
                        "scheduled_time": scheduled_time or defaults["scheduled_time"],
                        "light_entities": entity_ids,
                        "action": action or defaults["action"],
                        "brightness": user_input.get("brightness", defaults["brightness"]),
                        "color_temp_kelvin": user_input.get(
                            "color_temp_kelvin", defaults["color_temp_kelvin"]
                        ),
                    }
                ),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        assert weekday is not None
        assert scheduled_min is not None

        proposal = self._build_admin_authored_lighting_schedule_proposal(
            room_id=room_id,
            weekday=weekday,
            scheduled_min=scheduled_min,
            entity_ids=entity_ids,
            action=action,
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self.async_show_form(
                step_id="admin_authored_lighting_schedule",
                data_schema=self._admin_authored_lighting_schedule_schema(
                    {
                        "room_id": room_id,
                        "weekday": str(weekday),
                        "scheduled_time": scheduled_time,
                        "light_entities": entity_ids,
                        "action": action,
                        "brightness": brightness or defaults["brightness"],
                        "color_temp_kelvin": color_temp_kelvin or defaults["color_temp_kelvin"],
                    }
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self.async_show_form(
                step_id="admin_authored_lighting_schedule",
                data_schema=self._admin_authored_lighting_schedule_schema(
                    {
                        "room_id": room_id,
                        "weekday": str(weekday),
                        "scheduled_time": scheduled_time,
                        "light_entities": entity_ids,
                        "action": action,
                        "brightness": brightness or defaults["brightness"],
                        "color_temp_kelvin": color_temp_kelvin or defaults["color_temp_kelvin"],
                    }
                ),
                errors={"base": "redacted_payload"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    async def async_step_admin_authored_security_presence_simulation(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored vacation presence simulation policy."""
        template = self._admin_authored_template("security.vacation_presence_simulation.basic")
        if template is None:
            return await self.async_step_init()
        available, reason = self._admin_authored_template_availability(template.template_id)
        if not available:
            schema = vol.Schema(
                {vol.Required("template_id"): vol.In(self._admin_authored_template_options())}
            )
            return self.async_show_form(
                step_id="admin_authored_create",
                data_schema=schema,
                errors={"base": "template_unavailable"},
                description_placeholders={"availability_notes": reason or ""},
            )

        defaults = {
            "enabled": True,
            "allowed_rooms": [],
            "allowed_entities": [],
            "requires_dark_outside": True,
            "simulation_aggressiveness": "medium",
            "min_jitter_override_min": None,
            "max_jitter_override_min": None,
            "max_events_per_evening_override": None,
            "latest_end_time_override": "",
            "skip_if_presence_detected": True,
        }
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._admin_authored_security_presence_simulation_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        min_jitter = self._coerce_optional_int(user_input.get("min_jitter_override_min"))
        max_jitter = self._coerce_optional_int(user_input.get("max_jitter_override_min"))
        max_events = self._coerce_optional_int(user_input.get("max_events_per_evening_override"))
        latest_end = str(user_input.get("latest_end_time_override") or "").strip()
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

        if errors:
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._admin_authored_security_presence_simulation_schema(user_input),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal = self._build_admin_authored_security_presence_simulation_proposal(
            enabled=bool(user_input.get("enabled", True)),
            allowed_rooms=self._normalize_multi_value(user_input.get("allowed_rooms")),
            allowed_entities=self._normalize_multi_value(user_input.get("allowed_entities")),
            requires_dark_outside=bool(user_input.get("requires_dark_outside", True)),
            simulation_aggressiveness=str(user_input.get("simulation_aggressiveness") or "medium"),
            min_jitter_override_min=min_jitter,
            max_jitter_override_min=max_jitter,
            max_events_per_evening_override=max_events,
            latest_end_time_override=latest_end or None,
            skip_if_presence_detected=bool(user_input.get("skip_if_presence_detected", True)),
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._admin_authored_security_presence_simulation_schema(user_input),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._admin_authored_security_presence_simulation_schema(user_input),
                errors={"base": "redacted_payload"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    async def async_step_admin_authored_room_signal_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored room signal assist proposal."""
        template = self._admin_authored_template("room.signal_assist.basic")
        room_ids = self._room_ids()
        if template is None or not room_ids:
            return await self.async_step_init()

        rooms = self._rooms()
        defaults = {
            "room_id": room_ids[0],
            "primary_signal_name": "room_humidity",
            "primary_trigger_mode": "bucket",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": [],
        }
        errors: dict[str, str] = {}

        def _placeholders(selected_room_id: str) -> dict[str, str]:
            return {
                "template_title": template.title,
                "template_description": template.description,
                "available_signals": self._format_room_signals_placeholder(
                    rooms, selected_room_id
                ),
            }

        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(defaults),
                description_placeholders=_placeholders(defaults["room_id"]),
            )

        room_id = str(user_input.get("room_id") or "").strip()
        primary_signal_name = str(user_input.get("primary_signal_name") or "").strip()
        primary_trigger_mode = str(
            user_input.get("primary_trigger_mode") or defaults["primary_trigger_mode"]
        ).strip()
        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode") or defaults["primary_bucket_match_mode"]
        ).strip()
        corroboration_signal_name = str(user_input.get("corroboration_signal_name") or "").strip()
        corroboration_bucket = str(user_input.get("corroboration_bucket") or "").strip()
        corroboration_bucket_match_mode = str(
            user_input.get("corroboration_bucket_match_mode")
            or defaults["corroboration_bucket_match_mode"]
        ).strip()
        action_entities = self._normalize_multi_value(user_input.get("action_entities"))

        if not room_id:
            errors["room_id"] = "required"
        if not action_entities:
            errors["action_entities"] = "required"

        valid_signals = room_signal_names(rooms, room_id) if room_id else []

        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"

        if primary_trigger_mode not in self._trigger_mode_options():
            errors["primary_trigger_mode"] = "invalid_option"
        elif not errors.get("primary_signal_name"):
            if primary_trigger_mode == "burst":
                if not room_signal_has_burst(rooms, room_id, primary_signal_name):
                    errors["primary_trigger_mode"] = "no_burst_config"
            else:
                valid_buckets = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
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
                    rooms, room_id, corroboration_signal_name
                )
                if corroboration_bucket not in valid_corr_buckets:
                    errors["corroboration_bucket"] = "invalid_bucket"
        if corroboration_bucket_match_mode not in self._bucket_match_mode_options():
            errors["corroboration_bucket_match_mode"] = "invalid_option"

        current_input = {
            "room_id": room_id or defaults["room_id"],
            "primary_signal_name": primary_signal_name or defaults["primary_signal_name"],
            "primary_trigger_mode": primary_trigger_mode,
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "corroboration_signal_name": corroboration_signal_name,
            "corroboration_bucket": corroboration_bucket,
            "corroboration_bucket_match_mode": corroboration_bucket_match_mode,
            "action_entities": action_entities,
        }

        if errors:
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(current_input),
                errors=errors,
                description_placeholders=_placeholders(room_id or defaults["room_id"]),
            )

        primary_entity_id = room_signal_entity_id(rooms, room_id, primary_signal_name)
        primary_entities = [primary_entity_id] if primary_entity_id else []

        corroboration_entities: list[str] = []
        if corroboration_signal_name:
            corr_entity_id = room_signal_entity_id(rooms, room_id, corroboration_signal_name)
            if corr_entity_id:
                corroboration_entities = [corr_entity_id]

        proposal = self._build_admin_authored_room_signal_assist_proposal(
            room_id=room_id,
            primary_signal_entities=primary_entities,
            primary_signal_name=primary_signal_name,
            primary_trigger_mode=primary_trigger_mode,
            primary_bucket=primary_bucket,
            primary_bucket_match_mode=primary_bucket_match_mode,
            corroboration_signal_entities=corroboration_entities,
            corroboration_signal_name=corroboration_signal_name or "corroboration",
            corroboration_bucket=corroboration_bucket,
            corroboration_bucket_match_mode=corroboration_bucket_match_mode,
            action_entities=action_entities,
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(current_input),
                errors={"base": "duplicate"},
                description_placeholders=_placeholders(room_id),
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(current_input),
                errors={"base": "redacted_payload"},
                description_placeholders=_placeholders(room_id),
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    async def async_step_admin_authored_room_darkness_lighting_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored room darkness lighting assist proposal."""
        template = self._admin_authored_template("room.darkness_lighting_assist.basic")
        room_ids = self._room_ids()
        rooms = self._rooms()
        if template is None or not room_ids:
            return await self.async_step_init()

        default_room_id = room_ids[0]
        defaults = {
            "room_id": default_room_id,
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "primary_bucket_match_mode": "eq",
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
        errors: dict[str, str] = {}

        if user_input is None:
            signals_placeholder = self._format_room_signals_placeholder(rooms, default_room_id)
            return self.async_show_form(
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                    "available_signals": signals_placeholder,
                },
            )

        room_id = str(user_input.get("room_id") or "").strip()
        primary_signal_name = str(user_input.get("primary_signal_name") or "room_lux").strip()
        action = str(user_input.get("action") or "on").strip()
        entity_ids = self._normalize_multi_value(user_input.get("light_entities"))
        signals_placeholder = self._format_room_signals_placeholder(rooms, room_id)

        if not room_id:
            errors["room_id"] = "required"
        if not entity_ids:
            errors["light_entities"] = "required"

        valid_signals = room_signal_names(rooms, room_id) if room_id else []
        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif valid_signals and primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"

        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode") or defaults["primary_bucket_match_mode"]
        ).strip()
        if not errors.get("primary_signal_name") and room_id:
            valid_buckets = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
            if not primary_bucket:
                errors["primary_bucket"] = "required"
                primary_bucket = defaults["primary_bucket"]
            elif valid_buckets and primary_bucket not in valid_buckets:
                errors["primary_bucket"] = "invalid_bucket"
        elif not primary_bucket:
            primary_bucket = defaults["primary_bucket"]
        if primary_bucket_match_mode not in self._bucket_match_mode_options():
            errors["primary_bucket_match_mode"] = "invalid_option"
            primary_bucket_match_mode = defaults["primary_bucket_match_mode"]

        brightness = None
        color_temp_kelvin = None
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

        current_input = {
            "room_id": room_id or defaults["room_id"],
            "primary_signal_name": primary_signal_name or defaults["primary_signal_name"],
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "light_entities": entity_ids,
            "action": action or defaults["action"],
            "brightness": user_input.get("brightness", defaults["brightness"]),
            "color_temp_kelvin": user_input.get("color_temp_kelvin", defaults["color_temp_kelvin"]),
        }

        if errors:
            return self.async_show_form(
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(
                    current_input
                ),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                    "available_signals": signals_placeholder,
                },
            )

        primary_entity_id = room_signal_entity_id(rooms, room_id, primary_signal_name)
        primary_signal_entities = [primary_entity_id] if primary_entity_id else []

        proposal = self._build_admin_authored_room_darkness_lighting_assist_proposal(
            room_id=room_id,
            primary_signal_entities=primary_signal_entities,
            primary_signal_name=primary_signal_name or "room_lux",
            primary_bucket=primary_bucket,
            primary_bucket_match_mode=primary_bucket_match_mode,
            entity_ids=entity_ids,
            action=action,
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self.async_show_form(
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(
                    current_input
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                    "available_signals": signals_placeholder,
                },
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self.async_show_form(
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(
                    current_input
                ),
                errors={"base": "redacted_payload"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                    "available_signals": signals_placeholder,
                },
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    async def async_step_admin_authored_room_vacancy_lighting_off(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored vacancy lights-off proposal."""
        template = self._admin_authored_template("room.vacancy_lighting_off.basic")
        room_ids = self._room_ids()
        if template is None or not room_ids:
            return await self.async_step_init()

        defaults = {
            "room_id": room_ids[0],
            "light_entities": [],
            "vacancy_delay_min": 5,
        }
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                data_schema=self._admin_authored_room_vacancy_lighting_off_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        room_id = str(user_input.get("room_id") or "").strip()
        entity_ids = self._normalize_multi_value(user_input.get("light_entities"))

        if not room_id:
            errors["room_id"] = "required"
        if not entity_ids:
            errors["light_entities"] = "required"

        try:
            vacancy_delay_min = int(user_input.get("vacancy_delay_min") or 0)
            if vacancy_delay_min < 1 or vacancy_delay_min > 180:
                raise ValueError
        except (TypeError, ValueError):
            errors["vacancy_delay_min"] = "invalid_number"
            vacancy_delay_min = int(defaults["vacancy_delay_min"])

        if errors:
            return self.async_show_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                data_schema=self._admin_authored_room_vacancy_lighting_off_schema(
                    {
                        "room_id": room_id or defaults["room_id"],
                        "light_entities": entity_ids,
                        "vacancy_delay_min": vacancy_delay_min,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal = self._build_admin_authored_room_vacancy_lighting_off_proposal(
            room_id=room_id,
            entity_ids=entity_ids,
            vacancy_delay_min=vacancy_delay_min,
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self.async_show_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                data_schema=self._admin_authored_room_vacancy_lighting_off_schema(
                    {
                        "room_id": room_id,
                        "light_entities": entity_ids,
                        "vacancy_delay_min": vacancy_delay_min,
                    }
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self.async_show_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                data_schema=self._admin_authored_room_vacancy_lighting_off_schema(
                    {
                        "room_id": room_id,
                        "light_entities": entity_ids,
                        "vacancy_delay_min": vacancy_delay_min,
                    }
                ),
                errors={"base": "redacted_payload"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    def _store_reactions_options(self, updates: dict[str, Any]) -> None:
        """Persist reaction options without dropping sibling reaction state."""
        reactions_cfg = dict(self._reactions_options())
        reactions_cfg.update(updates)
        self._update_options({OPT_REACTIONS: reactions_cfg})

    async def async_step_reactions(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Show registered reactions and allow toggling persisted mute state."""
        reaction_labels = self._get_registered_reaction_labels()
        current_muted = list(self._reactions_options().get("muted", []))

        if not reaction_labels:
            # No reactions registered — skip silently back to menu
            return await self.async_step_init()

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("muted_reactions"): cv.multi_select(reaction_labels),
                }
            )
            return self.async_show_form(
                step_id="reactions",
                data_schema=self.add_suggested_values_to_schema(
                    schema, {"muted_reactions": current_muted}
                ),
            )

        muted = self._normalize_multi_value(user_input.get("muted_reactions"))
        # Only persist IDs that are actually registered
        muted = [rid for rid in muted if rid in reaction_labels]
        self._store_reactions_options({"muted": muted})
        return await self.async_step_init()

    # ---- Edit configured reaction ----

    async def async_step_reactions_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Select a configured reaction to edit."""
        configured: dict[str, Any] = self._reactions_options().get("configured", {})
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})
        if not configured:
            return await self.async_step_init()

        reaction_labels = {
            pid: self._reaction_label_from_config(pid, cfg, labels_map)
            for pid, cfg in configured.items()
        }

        if user_input is None:
            schema = vol.Schema({vol.Required("reaction"): vol.In(reaction_labels)})
            return self.async_show_form(step_id="reactions_edit", data_schema=schema)

        self._editing_reaction_id = user_input.get("reaction")
        return await self.async_step_reactions_edit_form()

    async def async_step_reactions_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Edit, disable, or request deletion of the selected configured reaction."""
        pid = getattr(self, "_editing_reaction_id", None)
        if not pid:
            return await self.async_step_init()

        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels_map: dict[str, str] = reactions_cfg.get("labels", {})
        cfg = dict(configured.get(pid, {}))
        reaction_type = self._reaction_type_from_cfg(cfg)

        if reaction_type == "room_darkness_lighting_assist":
            return await self._async_step_reactions_edit_room_lighting_assist(
                pid=pid,
                reactions_cfg=reactions_cfg,
                configured=configured,
                labels_map=labels_map,
                cfg=cfg,
                user_input=user_input,
            )

        if reaction_type in ("room_signal_assist", "room_air_quality_assist"):
            return await self._async_step_reactions_edit_room_signal_assist(
                pid=pid,
                reactions_cfg=reactions_cfg,
                configured=configured,
                labels_map=labels_map,
                cfg=cfg,
                user_input=user_input,
            )

        if user_input is None:
            current_steps = cfg.get("steps", [])
            current_entities = [
                s["target"] for s in current_steps if isinstance(s, dict) and "target" in s
            ]
            current_pre = cfg.get("pre_condition_min", 20)
            schema = vol.Schema(
                {
                    vol.Optional("enabled", default=bool(cfg.get("enabled", True))): bool,
                    vol.Optional("action_entities"): _entity_selector(
                        ["scene", "script"], multiple=True
                    ),
                    vol.Optional("pre_condition_min", default=current_pre): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=120)
                    ),
                    vol.Optional("delete_reaction", default=False): bool,
                }
            )
            label = self._reaction_label_from_config(pid, cfg, labels_map)
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    {
                        "enabled": bool(cfg.get("enabled", True)),
                        "action_entities": current_entities,
                        "pre_condition_min": current_pre,
                        "delete_reaction": False,
                    },
                ),
                description_placeholders={
                    "reaction_description": label,
                    "room_id": str(cfg.get("room_id") or "-"),
                    "available_signals": "",
                },
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        entities = self._normalize_multi_value(user_input.get("action_entities"))
        steps = self._action_entities_to_steps(entities)
        cfg["steps"] = steps
        cfg["enabled"] = bool(user_input.get("enabled", True))
        cfg["pre_condition_min"] = int(user_input.get("pre_condition_min") or 20)
        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def _async_step_reactions_edit_room_lighting_assist(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit a room darkness lighting assist reaction using its real config contract."""
        room_id = str(cfg.get("room_id") or "").strip()
        rooms = self._rooms()
        current_steps = [
            step for step in list(cfg.get("entity_steps", [])) if isinstance(step, dict)
        ]
        current_entities = [
            str(step.get("entity_id") or "").strip()
            for step in current_steps
            if str(step.get("entity_id") or "").strip()
        ]
        first_step = current_steps[0] if current_steps else {}
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "primary_signal_name": str(cfg.get("primary_signal_name") or "room_lux").strip(),
            "primary_bucket": str(cfg.get("primary_bucket") or "dim").strip() or "dim",
            "primary_bucket_match_mode": str(cfg.get("primary_bucket_match_mode") or "eq").strip()
            or "eq",
            "light_entities": current_entities,
            "action": str(first_step.get("action") or "on").strip() or "on",
            "brightness": int(first_step.get("brightness") or 190),
            "color_temp_kelvin": int(first_step.get("color_temp_kelvin") or 2850),
            "delete_reaction": False,
        }
        label = self._reaction_label_from_config(pid, cfg, labels_map)
        room_id_placeholder = room_id or "-"
        signals_placeholder = self._format_room_signals_placeholder(rooms, room_id)

        if user_input is None:
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._reactions_edit_room_lighting_assist_schema(defaults),
                description_placeholders={
                    "reaction_description": label,
                    "room_id": room_id_placeholder,
                    "available_signals": signals_placeholder,
                },
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        errors: dict[str, str] = {}
        primary_signal_name = str(
            user_input.get("primary_signal_name") or defaults["primary_signal_name"]
        ).strip()
        light_entities = self._normalize_multi_value(user_input.get("light_entities"))
        action = str(user_input.get("action") or "on").strip() or "on"

        if not light_entities:
            errors["light_entities"] = "required"

        valid_signals = room_signal_names(rooms, room_id)
        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"

        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode") or defaults["primary_bucket_match_mode"]
        ).strip()
        if not errors.get("primary_signal_name"):
            valid_buckets = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
            if not primary_bucket:
                errors["primary_bucket"] = "required"
                primary_bucket = defaults["primary_bucket"]
            elif primary_bucket not in valid_buckets:
                errors["primary_bucket"] = "invalid_bucket"
        elif not primary_bucket:
            primary_bucket = defaults["primary_bucket"]
        if primary_bucket_match_mode not in self._bucket_match_mode_options():
            errors["primary_bucket_match_mode"] = "invalid_option"
            primary_bucket_match_mode = defaults["primary_bucket_match_mode"]

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

        current_input = {
            "enabled": bool(user_input.get("enabled", defaults["enabled"])),
            "primary_signal_name": primary_signal_name,
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "light_entities": light_entities,
            "action": action,
            "brightness": user_input.get("brightness", defaults["brightness"]),
            "color_temp_kelvin": user_input.get("color_temp_kelvin", defaults["color_temp_kelvin"]),
            "delete_reaction": False,
        }

        if errors:
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._reactions_edit_room_lighting_assist_schema(current_input),
                errors=errors,
                description_placeholders={
                    "reaction_description": label,
                    "room_id": room_id_placeholder,
                    "available_signals": signals_placeholder,
                },
            )

        primary_entity_id = room_signal_entity_id(rooms, room_id, primary_signal_name)
        primary_signal_entities = [primary_entity_id] if primary_entity_id else []

        cfg["enabled"] = bool(user_input.get("enabled", True))
        cfg["primary_signal_entities"] = primary_signal_entities
        cfg["primary_signal_name"] = primary_signal_name
        cfg["primary_bucket"] = primary_bucket
        cfg["primary_bucket_match_mode"] = primary_bucket_match_mode
        cfg.pop("primary_threshold", None)
        cfg.pop("primary_threshold_mode", None)
        cfg["entity_steps"] = [
            {
                "entity_id": entity_id,
                "action": action,
                "brightness": brightness if action == "on" else None,
                "color_temp_kelvin": color_temp_kelvin if action == "on" else None,
                "rgb_color": None,
            }
            for entity_id in light_entities
        ]
        if self._has_redacted_payload(cfg):
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._reactions_edit_room_lighting_assist_schema(current_input),
                errors={"base": "redacted_payload"},
                description_placeholders={
                    "reaction_description": label,
                    "room_id": room_id_placeholder,
                    "available_signals": signals_placeholder,
                },
            )
        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def _async_step_reactions_edit_room_signal_assist(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit a room signal assist (or air quality assist) reaction."""
        room_id = str(cfg.get("room_id") or "").strip()
        rooms = self._rooms()
        current_steps = list(cfg.get("steps", []))
        current_entities = [
            str(s.get("target") or "").strip()
            for s in current_steps
            if isinstance(s, dict) and str(s.get("target") or "").strip()
        ]
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "primary_signal_name": str(cfg.get("primary_signal_name") or "").strip(),
            "primary_trigger_mode": str(cfg.get("primary_trigger_mode") or "bucket").strip() or "bucket",
            "primary_bucket": str(cfg.get("primary_bucket") or "").strip(),
            "primary_bucket_match_mode": str(cfg.get("primary_bucket_match_mode") or "eq").strip()
            or "eq",
            "corroboration_signal_name": str(cfg.get("corroboration_signal_name") or "").strip(),
            "corroboration_bucket": str(cfg.get("corroboration_bucket") or "").strip(),
            "corroboration_bucket_match_mode": str(
                cfg.get("corroboration_bucket_match_mode") or "eq"
            ).strip()
            or "eq",
            "action_entities": current_entities,
            "delete_reaction": False,
        }
        label = self._reaction_label_from_config(pid, cfg, labels_map)
        room_id_placeholder = room_id or "-"
        signals_placeholder = self._format_room_signals_placeholder(rooms, room_id)

        if user_input is None:
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._reactions_edit_room_signal_assist_schema(defaults),
                description_placeholders={
                    "reaction_description": label,
                    "room_id": room_id_placeholder,
                    "available_signals": signals_placeholder,
                },
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        errors: dict[str, str] = {}
        primary_signal_name = str(user_input.get("primary_signal_name") or "").strip()
        primary_trigger_mode = str(
            user_input.get("primary_trigger_mode") or defaults["primary_trigger_mode"]
        ).strip()
        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode") or defaults["primary_bucket_match_mode"]
        ).strip()
        corroboration_signal_name = str(
            user_input.get("corroboration_signal_name") or ""
        ).strip()
        corroboration_bucket = str(user_input.get("corroboration_bucket") or "").strip()
        corroboration_bucket_match_mode = str(
            user_input.get("corroboration_bucket_match_mode")
            or defaults["corroboration_bucket_match_mode"]
        ).strip()
        action_entities = self._normalize_multi_value(user_input.get("action_entities"))

        valid_signals = room_signal_names(rooms, room_id)
        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"

        if primary_trigger_mode not in self._trigger_mode_options():
            errors["primary_trigger_mode"] = "invalid_option"
        elif not errors.get("primary_signal_name"):
            if primary_trigger_mode == "burst":
                if not room_signal_has_burst(rooms, room_id, primary_signal_name):
                    errors["primary_trigger_mode"] = "no_burst_config"
            else:
                valid_buckets = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
                if not primary_bucket:
                    errors["primary_bucket"] = "required"
                elif primary_bucket not in valid_buckets:
                    errors["primary_bucket"] = "invalid_bucket"
                if primary_bucket_match_mode not in self._bucket_match_mode_options():
                    errors["primary_bucket_match_mode"] = "invalid_option"

        if corroboration_signal_name:
            if corroboration_signal_name not in valid_signals:
                errors["corroboration_signal_name"] = "invalid_signal_name"
            elif not errors.get("corroboration_signal_name"):
                valid_corr_buckets = room_signal_bucket_labels(
                    rooms, room_id, corroboration_signal_name
                )
                if corroboration_bucket and corroboration_bucket not in valid_corr_buckets:
                    errors["corroboration_bucket"] = "invalid_bucket"
        if corroboration_bucket_match_mode not in self._bucket_match_mode_options():
            errors["corroboration_bucket_match_mode"] = "invalid_option"

        if not action_entities:
            errors["action_entities"] = "required"

        current_input = {
            "enabled": bool(user_input.get("enabled", defaults["enabled"])),
            "primary_signal_name": primary_signal_name or defaults["primary_signal_name"],
            "primary_trigger_mode": primary_trigger_mode,
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "corroboration_signal_name": corroboration_signal_name,
            "corroboration_bucket": corroboration_bucket,
            "corroboration_bucket_match_mode": corroboration_bucket_match_mode,
            "action_entities": action_entities,
            "delete_reaction": False,
        }

        if errors:
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._reactions_edit_room_signal_assist_schema(current_input),
                errors=errors,
                description_placeholders={
                    "reaction_description": label,
                    "room_id": room_id_placeholder,
                    "available_signals": signals_placeholder,
                },
            )

        primary_entity_id = room_signal_entity_id(rooms, room_id, primary_signal_name)
        primary_entities = [primary_entity_id] if primary_entity_id else []

        corroboration_entities: list[str] = []
        if corroboration_signal_name:
            corr_entity_id = room_signal_entity_id(rooms, room_id, corroboration_signal_name)
            if corr_entity_id:
                corroboration_entities = [corr_entity_id]

        cfg["enabled"] = bool(user_input.get("enabled", True))
        cfg["primary_signal_name"] = primary_signal_name
        cfg["primary_trigger_mode"] = primary_trigger_mode
        cfg["primary_bucket"] = primary_bucket if primary_trigger_mode == "bucket" else None
        cfg["primary_bucket_match_mode"] = primary_bucket_match_mode
        cfg["primary_signal_entities"] = primary_entities
        cfg["trigger_signal_entities"] = primary_entities
        cfg["corroboration_signal_name"] = corroboration_signal_name or "corroboration"
        cfg["corroboration_bucket"] = corroboration_bucket or None
        cfg["corroboration_bucket_match_mode"] = corroboration_bucket_match_mode
        cfg["corroboration_signal_entities"] = corroboration_entities
        cfg["temperature_signal_entities"] = corroboration_entities
        cfg["steps"] = self._action_entities_to_steps(action_entities)
        for legacy_key in (
            "primary_threshold",
            "primary_threshold_mode",
            "primary_rise_threshold",
            "corroboration_threshold",
            "corroboration_threshold_mode",
            "corroboration_rise_threshold",
        ):
            cfg.pop(legacy_key, None)

        if self._has_redacted_payload(cfg):
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._reactions_edit_room_signal_assist_schema(current_input),
                errors={"base": "redacted_payload"},
                description_placeholders={
                    "reaction_description": label,
                    "room_id": room_id_placeholder,
                    "available_signals": signals_placeholder,
                },
            )

        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def async_step_reactions_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Confirm deletion of a configured reaction."""
        pid = getattr(self, "_deleting_reaction_id", None)
        if not pid:
            return await self.async_step_init()

        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels_map: dict[str, str] = reactions_cfg.get("labels", {})
        muted = list(reactions_cfg.get("muted", []))
        cfg = dict(configured.get(pid, {}))
        if not cfg:
            self._deleting_reaction_id = None
            self._editing_reaction_id = None
            return await self.async_step_init()

        reaction_label = self._reaction_label_from_config(pid, cfg, labels_map)
        if user_input is None:
            schema = vol.Schema({vol.Required("confirm", default=False): bool})
            return self.async_show_form(
                step_id="reactions_delete_confirm",
                data_schema=schema,
                description_placeholders={"reaction_description": reaction_label},
            )

        if not bool(user_input.get("confirm")):
            self._deleting_reaction_id = None
            return await self.async_step_reactions_edit_form()

        configured.pop(pid, None)
        labels_map.pop(pid, None)
        muted = [rid for rid in muted if rid != pid]
        reactions_cfg["configured"] = configured
        reactions_cfg["labels"] = labels_map
        reactions_cfg["muted"] = muted
        self._store_reactions_options(reactions_cfg)
        self._deleting_reaction_id = None
        self._editing_reaction_id = None
        return await self.async_step_init()

    # ---- Proposals step (P5) ----

    async def async_step_proposals(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Review pending learning proposals one at a time. Skip silently if none are pending."""
        coordinator = self._get_coordinator()
        pending = coordinator.proposal_engine.pending_proposals() if coordinator else []

        if not pending:
            self._proposal_review_queue = []
            return await self.async_step_init()

        pending_map = {proposal.proposal_id: proposal for proposal in pending}
        queue = list(getattr(self, "_proposal_review_queue", []))
        if not queue:
            queue = [proposal.proposal_id for proposal in pending]

        queue = [proposal_id for proposal_id in queue if proposal_id in pending_map]
        if not queue:
            self._proposal_review_queue = []
            return await self.async_step_init()

        current_id = queue[0]
        current = pending_map[current_id]

        if user_input is None:
            self._proposal_review_queue = queue
            schema = vol.Schema(
                {
                    vol.Required(
                        "review_action",
                        default="accept",
                    ): vol.In(self._proposal_review_action_options()),
                }
            )
            return self.async_show_form(
                step_id="proposals",
                data_schema=schema,
                description_placeholders=self._proposal_review_placeholders(
                    pending, current, len(queue)
                ),
            )

        action = str(user_input.get("review_action") or "skip").strip().lower()
        queue = queue[1:]
        self._proposal_review_queue = queue

        if not coordinator:
            return await self.async_step_proposals() if queue else await self.async_step_init()

        reactions_cfg = dict(self.options.get(OPT_REACTIONS, {}))
        configured = dict(reactions_cfg.get("configured", {}))
        labels: dict[str, str] = dict(reactions_cfg.get("labels", {}))
        followup = self._proposal_followup_target(current)

        if action == "accept":
            accepted_proposal = current
            if followup is not None and current.followup_kind != "tuning_suggestion":
                accepted_proposal = replace(
                    current,
                    followup_kind="tuning_suggestion",
                    target_reaction_id=str(followup["reaction_id"]),
                    target_reaction_type=self._reaction_type_from_cfg(followup["reaction_cfg"]),
                    target_reaction_origin=str(followup.get("target_reaction_origin") or ""),
                    target_template_id=str(followup.get("target_template_id") or ""),
                )
            target_id = current_id
            existing_cfg: dict[str, Any] | None = None
            if followup is not None:
                target_id = str(followup["reaction_id"])
                existing_cfg = dict(followup["reaction_cfg"])
            if self._proposal_requires_action_completion(current):
                pending_drafts = list(getattr(self, "_pending_action_drafts", []))
                pending_drafts.append(
                    {
                        "proposal": accepted_proposal,
                        "proposal_id": current_id,
                        "target_id": target_id,
                        "existing_config": existing_cfg,
                        "label": current.description,
                    }
                )
                self._pending_action_drafts = pending_drafts
                self._resume_proposal_review = True
                return await self.async_step_proposal_configure_action()

            if self._has_redacted_payload(accepted_proposal.suggested_reaction_config):
                self._proposal_review_queue = [current_id, *queue]
                return self.async_show_form(
                    step_id="proposals",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "review_action",
                                default="accept",
                            ): vol.In(self._proposal_review_action_options()),
                        }
                    ),
                    errors={"base": "redacted_payload"},
                    description_placeholders=self._proposal_review_placeholders(
                        pending, current, len(self._proposal_review_queue)
                    ),
                )

            await coordinator.proposal_engine.async_accept_proposal(current_id)
            configured[target_id] = self._configured_reaction_from_proposal(
                accepted_proposal,
                existing_config=existing_cfg,
            )
            if target_id != current_id:
                configured.pop(current_id, None)
                labels.pop(current_id, None)
            labels[target_id] = current.description
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._store_reactions_options(reactions_cfg)

        elif action == "reject":
            await coordinator.proposal_engine.async_reject_proposal(current_id)
            configured.pop(current_id, None)
            labels.pop(current_id, None)
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._store_reactions_options(reactions_cfg)

        return await self.async_step_proposals() if queue else await self.async_step_init()

    # ---- Proposal action configuration ----

    async def async_step_proposal_configure_action(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Configure the action(s) to trigger for each accepted proposal, one at a time."""
        pending_drafts: list[dict[str, Any]] = list(getattr(self, "_pending_action_drafts", []))
        if pending_drafts:
            current_draft = pending_drafts[0]
            current_pid = str(
                current_draft.get("target_id") or current_draft.get("proposal_id") or ""
            )
            proposal_description = str(current_draft.get("label") or current_pid)
        else:
            pending: list[str] = getattr(self, "_pending_action_configs", [])
            if not pending:
                return await self.async_step_init()
            current_pid = pending[0]
            labels_map: dict[str, str] = self._reactions_options().get("labels", {})
            proposal_description = labels_map.get(current_pid, current_pid)
            current_draft = None

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("action_entities"): _entity_selector(
                        ["scene", "script"], multiple=True
                    ),
                    vol.Optional("pre_condition_min", default=20): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=120)
                    ),
                }
            )
            return self.async_show_form(
                step_id="proposal_configure_action",
                data_schema=schema,
                description_placeholders={"proposal_description": proposal_description},
            )

        # Build steps from selected entities
        entities = self._normalize_multi_value(user_input.get("action_entities"))
        steps = self._action_entities_to_steps(entities)
        pre_condition_min = int(user_input.get("pre_condition_min") or 20)

        if current_draft is not None:
            proposal = current_draft["proposal"]
            proposal_id = str(current_draft.get("proposal_id") or "")
            target_id = str(current_draft.get("target_id") or proposal_id)
            existing_cfg = _safe_mapping(current_draft.get("existing_config"))
            reactions_cfg = dict(self._reactions_options())
            configured = dict(reactions_cfg.get("configured", {}))
            labels = dict(reactions_cfg.get("labels", {}))
            cfg = self._configured_reaction_from_proposal(
                proposal,
                existing_config=existing_cfg,
            )
            cfg["steps"] = steps
            cfg["pre_condition_min"] = pre_condition_min
            if self._has_redacted_payload(cfg):
                return self.async_show_form(
                    step_id="proposal_configure_action",
                    data_schema=vol.Schema(
                        {
                            vol.Optional("action_entities"): _entity_selector(
                                ["scene", "script"], multiple=True
                            ),
                            vol.Optional("pre_condition_min", default=pre_condition_min): vol.All(
                                vol.Coerce(int), vol.Range(min=1, max=120)
                            ),
                        }
                    ),
                    errors={"base": "redacted_payload"},
                    description_placeholders={
                        "proposal_description": str(
                            current_draft.get("label") or current_draft.get("target_id") or ""
                        )
                    },
                )
            coordinator = self._get_coordinator()
            if coordinator is not None:
                await coordinator.proposal_engine.async_accept_proposal(proposal_id)
            configured[target_id] = cfg
            if target_id != proposal_id:
                configured.pop(proposal_id, None)
                labels.pop(proposal_id, None)
            labels[target_id] = str(current_draft.get("label") or target_id)
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._store_reactions_options(reactions_cfg)
        else:
            reactions_cfg = dict(self._reactions_options())
            configured = dict(reactions_cfg.get("configured", {}))
            if current_pid in configured:
                cfg = dict(configured[current_pid])
                cfg["steps"] = steps
                cfg["pre_condition_min"] = pre_condition_min
                if self._has_redacted_payload(cfg):
                    return self.async_show_form(
                        step_id="proposal_configure_action",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("action_entities"): _entity_selector(
                                    ["scene", "script"], multiple=True
                                ),
                                vol.Optional(
                                    "pre_condition_min", default=pre_condition_min
                                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                            }
                        ),
                        errors={"base": "redacted_payload"},
                        description_placeholders={"proposal_description": proposal_description},
                    )
                configured[current_pid] = cfg
                reactions_cfg["configured"] = configured
                self._store_reactions_options(reactions_cfg)

        # Advance queue
        if pending_drafts:
            self._pending_action_drafts = pending_drafts[1:]
        else:
            self._pending_action_configs = pending[1:]
        if getattr(self, "_pending_action_drafts", []):
            return await self.async_step_proposal_configure_action()
        if getattr(self, "_pending_action_configs", []):
            return await self.async_step_proposal_configure_action()
        if getattr(self, "_resume_proposal_review", False):
            self._resume_proposal_review = False
            if getattr(self, "_proposal_review_queue", []):
                return await self.async_step_proposals()
        return await self.async_step_init()

    # ---- Helpers ----

    def _reactions_options(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_REACTIONS, {}))

    @staticmethod
    def _configured_reaction_from_proposal(
        proposal: ReactionProposal,
        *,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        configured = dict(_safe_mapping(existing_config))
        configured.update(cfg)
        configured.pop("reaction_class", None)

        is_followup = proposal.followup_kind == "tuning_suggestion" and bool(
            _safe_mapping(existing_config)
        )
        if is_followup:
            if proposal.updated_at:
                configured["last_tuned_at"] = proposal.updated_at
            configured["last_tuning_proposal_id"] = proposal.proposal_id
            configured["last_tuning_origin"] = proposal.origin
            configured["last_tuning_followup_kind"] = proposal.followup_kind
            return configured

        origin = proposal.origin
        configured["reaction_type"] = str(proposal.reaction_type or "").strip()
        configured["origin"] = origin
        configured["author_kind"] = "admin" if origin == "admin_authored" else "heima"
        configured["source_proposal_id"] = proposal.proposal_id
        if proposal.identity_key:
            configured["source_proposal_identity_key"] = proposal.identity_key
        if proposal.created_at:
            configured["created_at"] = proposal.created_at
        template_id = str(cfg.get("admin_authored_template_id") or "").strip()
        if template_id:
            configured["source_template_id"] = template_id
            configured["source_request"] = f"template:{template_id}"
            configured.setdefault("last_tuned_at", None)
        else:
            configured["source_request"] = "learned_pattern"
        return configured

    def _admin_authored_template_options(self) -> dict[str, str]:
        registry = self._learning_plugin_registry()
        if registry is None:
            return {}
        options: dict[str, str] = {}
        for template in registry.admin_authored_templates(implemented_only=True):
            available, _reason = self._admin_authored_template_availability(template.template_id)
            title = template.title
            if not available:
                title = f"{title} ({'non disponibile' if self._flow_language().startswith('it') else 'unavailable'})"
            options[template.template_id] = title
        return options

    def _admin_authored_template(self, template_id: str) -> Any | None:
        registry = self._learning_plugin_registry()
        if registry is None:
            return None
        return registry.get_admin_authored_template(
            template_id,
            implemented_only=True,
        )

    def _admin_authored_template_availability(self, template_id: str) -> tuple[bool, str]:
        template_id = str(template_id or "").strip()
        if not template_id:
            return False, ""
        if template_id != "security.vacation_presence_simulation.basic":
            return True, ""
        configured = dict(self._reactions_options().get("configured", {}))
        for cfg in configured.values():
            if not isinstance(cfg, dict):
                continue
            reaction_type = str(cfg.get("reaction_type") or "").strip()
            if reaction_type == "lighting_scene_schedule":
                return True, ""
            if self._reaction_type_from_cfg(cfg) == "lighting_scene_schedule":
                return True, ""
            template = str(cfg.get("source_template_id") or "").strip()
            if template == "lighting.scene_schedule.basic":
                return True, ""
        lang = self._flow_language()
        if lang.startswith("it"):
            return (
                False,
                "Template non disponibile: servono routine luci già accettate per costruire un profilo credibile.",
            )
        return (
            False,
            "Template unavailable: accepted lighting routines are required to build a credible source profile.",
        )

    def _admin_authored_template_availability_notes(self) -> str:
        registry = self._learning_plugin_registry()
        if registry is None:
            return ""
        lines: list[str] = []
        for template in registry.admin_authored_templates(implemented_only=True):
            available, reason = self._admin_authored_template_availability(template.template_id)
            if not available and reason:
                lines.append(f"- {template.title}: {reason}")
        return "\n".join(lines)

    def _learning_plugin_registry(self) -> Any | None:
        coordinator = self._get_coordinator()
        registry = getattr(coordinator, "learning_plugin_registry", None) if coordinator else None
        if registry is not None:
            return registry
        learning_cfg = dict(self.options.get("learning", {}))
        enabled_families = {
            str(item).strip()
            for item in learning_cfg.get("enabled_plugin_families") or []
            if str(item).strip()
        }
        return create_builtin_learning_plugin_registry(enabled_families=enabled_families or None)

    @staticmethod
    def _coerce_optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _admin_authored_lighting_schedule_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        action_options = self._admin_authored_lighting_action_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
                    vol.Required("weekday"): vol.In(self._weekday_options()),
                    vol.Required("scheduled_time"): str,
                    vol.Required("light_entities"): _entity_selector(["light"], multiple=True),
                    vol.Required("action", default="on"): vol.In(action_options),
                    vol.Optional("brightness", default=190): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=255)
                    ),
                    vol.Optional("color_temp_kelvin", default=2850): vol.All(
                        vol.Coerce(int), vol.Range(min=1500, max=9000)
                    ),
                }
            ),
            defaults,
        )

    def _admin_authored_security_presence_simulation_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        aggressiveness = (
            {"low": "Bassa", "medium": "Media", "high": "Alta"}
            if self._flow_language().startswith("it")
            else {"low": "Low", "medium": "Medium", "high": "High"}
        )
        return self._with_suggested(
            vol.Schema(
                {
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
                        default=str(
                            defaults.get("simulation_aggressiveness", "medium") or "medium"
                        ),
                    ): vol.In(aggressiveness),
                    vol.Optional(
                        "min_jitter_override_min", default=defaults.get("min_jitter_override_min")
                    ): vol.Any(None, vol.Coerce(int)),
                    vol.Optional(
                        "max_jitter_override_min", default=defaults.get("max_jitter_override_min")
                    ): vol.Any(None, vol.Coerce(int)),
                    vol.Optional(
                        "max_events_per_evening_override",
                        default=defaults.get("max_events_per_evening_override"),
                    ): vol.Any(None, vol.Coerce(int)),
                    vol.Optional(
                        "latest_end_time_override",
                        default=str(defaults.get("latest_end_time_override", "") or ""),
                    ): str,
                    vol.Required(
                        "skip_if_presence_detected",
                        default=bool(defaults.get("skip_if_presence_detected", True)),
                    ): bool,
                }
            ),
            defaults,
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
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        bucket_match_options = self._bucket_match_mode_options()
        trigger_mode_options = self._trigger_mode_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
                    vol.Required("primary_signal_name", default="room_humidity"): str,
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
            ),
            defaults,
        )

    def _admin_authored_room_darkness_lighting_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        action_options = self._admin_authored_lighting_action_options()
        bucket_match_options = self._bucket_match_mode_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
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
            ),
            defaults,
        )

    def _reactions_edit_room_signal_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        bucket_match_options = self._bucket_match_mode_options()
        trigger_mode_options = self._trigger_mode_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Optional("enabled", default=True): bool,
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
                    vol.Optional("delete_reaction", default=False): bool,
                }
            ),
            defaults,
        )

    def _format_room_signals_placeholder(
        self, rooms: list[dict[str, Any]], room_id: str
    ) -> str:
        """Return a human-readable signal/bucket map for description_placeholders."""
        signals = room_signal_names(rooms, room_id)
        if not signals:
            return "—"
        lines = []
        for signal_name in signals:
            labels = room_signal_bucket_labels(rooms, room_id, signal_name)
            lines.append(f"{signal_name}: {', '.join(labels) if labels else '—'}")
        return "\n".join(lines)

    def _admin_authored_room_vacancy_lighting_off_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        room_options = {room_id: room_id for room_id in self._room_ids()}
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
                    vol.Required("light_entities"): _entity_selector(["light"], multiple=True),
                    vol.Required("vacancy_delay_min", default=5): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=180)
                    ),
                }
            ),
            defaults,
        )

    def _reactions_edit_room_lighting_assist_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        defaults = defaults or {}
        action_options = self._admin_authored_lighting_action_options()
        bucket_match_options = self._bucket_match_mode_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Optional("enabled", default=True): bool,
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
                    vol.Optional("delete_reaction", default=False): bool,
                }
            ),
            defaults,
        )

    def _weekday_options(self) -> dict[str, str]:
        language = self._flow_language()
        return {str(index): self._weekday_label(index, language) for index in range(7)}

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

    def _build_admin_authored_lighting_schedule_proposal(
        self,
        *,
        room_id: str,
        weekday: int,
        scheduled_min: int,
        entity_ids: list[str],
        action: str,
        brightness: int | None,
        color_temp_kelvin: int | None,
    ) -> ReactionProposal:
        template_id = "lighting.scene_schedule.basic"
        entity_steps = [
            {
                "entity_id": entity_id,
                "action": action,
                "brightness": brightness if action == "on" else None,
                "color_temp_kelvin": color_temp_kelvin if action == "on" else None,
                "rgb_color": None,
            }
            for entity_id in entity_ids
        ]
        identity_key = self._lighting_identity_key(
            room_id=room_id,
            weekday=weekday,
            scheduled_min=scheduled_min,
            entity_steps=entity_steps,
        )
        hhmm = f"{scheduled_min // 60:02d}:{scheduled_min % 60:02d}"
        day = self._weekday_label(weekday, "en")
        description = f"{room_id}: {day} ~{hhmm} — {len(entity_steps)} entities"
        return ReactionProposal(
            analyzer_id="AdminAuthoredLightingTemplate",
            reaction_type="lighting_scene_schedule",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "lighting_scene_schedule",
                "room_id": room_id,
                "weekday": weekday,
                "scheduled_min": scheduled_min,
                "window_half_min": 10,
                "entity_steps": entity_steps,
                "plugin_family": "lighting",
                "admin_authored_template_id": template_id,
            },
        )

    def _build_admin_authored_room_signal_assist_proposal(
        self,
        *,
        room_id: str,
        primary_signal_entities: list[str],
        primary_signal_name: str,
        primary_trigger_mode: str,
        primary_bucket: str,
        primary_bucket_match_mode: str,
        corroboration_signal_entities: list[str],
        corroboration_signal_name: str,
        corroboration_bucket: str,
        corroboration_bucket_match_mode: str,
        action_entities: list[str],
    ) -> ReactionProposal:
        template_id = "room.signal_assist.basic"
        identity_key = (
            f"room_signal_assist|room={room_id}|primary={primary_signal_name.strip().lower()}"
            f"|mode={primary_trigger_mode}"
        )
        steps = self._action_entities_to_steps(action_entities)
        if primary_trigger_mode == "burst":
            trigger_text = f"{primary_signal_name.strip().lower()} bursts"
        else:
            primary_match_mode = primary_bucket_match_mode.strip() or "eq"
            if primary_match_mode == "lte":
                trigger_text = (
                    f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or lower"
                )
            elif primary_match_mode == "gte":
                trigger_text = (
                    f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or higher"
                )
            else:
                trigger_text = (
                    f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()}"
                )
        if corroboration_signal_entities and corroboration_bucket.strip():
            corroboration_match_mode = corroboration_bucket_match_mode.strip() or "eq"
            if corroboration_match_mode == "lte":
                corroboration_text = (
                    f"{corroboration_signal_name.strip().lower()} is {corroboration_bucket.strip()} or lower"
                )
            elif corroboration_match_mode == "gte":
                corroboration_text = (
                    f"{corroboration_signal_name.strip().lower()} is {corroboration_bucket.strip()} or higher"
                )
            else:
                corroboration_text = (
                    f"{corroboration_signal_name.strip().lower()} is {corroboration_bucket.strip()}"
                )
            trigger_text = f"{trigger_text} and {corroboration_text}"
        description = (
            f"{room_id}: when {trigger_text}, "
            f"trigger {len(steps)} action{'s' if len(steps) != 1 else ''}"
        )
        return ReactionProposal(
            analyzer_id="AdminAuthoredRoomSignalAssistTemplate",
            reaction_type="room_signal_assist",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "room_signal_assist",
                "room_id": room_id,
                "primary_trigger_mode": primary_trigger_mode,
                "trigger_signal_entities": list(primary_signal_entities),
                "primary_signal_entities": list(primary_signal_entities),
                "primary_bucket": primary_bucket.strip() if primary_trigger_mode == "bucket" else None,
                "primary_bucket_match_mode": primary_bucket_match_mode.strip() or "eq",
                "primary_signal_name": primary_signal_name.strip() or "primary",
                "temperature_signal_entities": list(corroboration_signal_entities),
                "corroboration_signal_entities": list(corroboration_signal_entities),
                "corroboration_bucket": corroboration_bucket.strip() or None,
                "corroboration_bucket_match_mode": (
                    corroboration_bucket_match_mode.strip() or "eq"
                ),
                "corroboration_signal_name": corroboration_signal_name.strip() or "corroboration",
                "correlation_window_s": 600,
                "followup_window_s": 900,
                "steps": steps,
                "plugin_family": "composite_room_assist",
                "admin_authored_template_id": template_id,
            },
        )

    def _build_admin_authored_room_darkness_lighting_assist_proposal(
        self,
        *,
        room_id: str,
        primary_signal_entities: list[str],
        primary_signal_name: str,
        primary_bucket: str,
        primary_bucket_match_mode: str,
        entity_ids: list[str],
        action: str,
        brightness: int | None,
        color_temp_kelvin: int | None,
    ) -> ReactionProposal:
        template_id = "room.darkness_lighting_assist.basic"
        identity_key = f"room_darkness_lighting_assist|room={room_id}|primary={primary_signal_name.strip().lower()}"
        entity_steps = [
            {
                "entity_id": entity_id,
                "action": action,
                "brightness": brightness if action == "on" else None,
                "color_temp_kelvin": color_temp_kelvin if action == "on" else None,
                "rgb_color": None,
            }
            for entity_id in entity_ids
        ]
        match_mode = primary_bucket_match_mode.strip() or "eq"
        if match_mode == "lte":
            trigger_text = f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or darker"
        elif match_mode == "gte":
            trigger_text = f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or brighter"
        else:
            trigger_text = f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()}"
        description = (
            f"{room_id}: when {trigger_text}, "
            f"apply {len(entity_steps)} light action{'s' if len(entity_steps) != 1 else ''}"
        )
        return ReactionProposal(
            analyzer_id="AdminAuthoredRoomDarknessLightingTemplate",
            reaction_type="room_darkness_lighting_assist",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "room_darkness_lighting_assist",
                "room_id": room_id,
                "primary_signal_entities": list(primary_signal_entities),
                "primary_bucket": primary_bucket.strip(),
                "primary_bucket_match_mode": primary_bucket_match_mode.strip() or "eq",
                "primary_signal_name": primary_signal_name.strip() or "room_lux",
                "corroboration_signal_entities": [],
                "corroboration_signal_name": "corroboration",
                "correlation_window_s": 600,
                "followup_window_s": 900,
                "entity_steps": entity_steps,
                "plugin_family": "composite_room_assist",
                "admin_authored_template_id": template_id,
            },
        )

    def _build_admin_authored_room_vacancy_lighting_off_proposal(
        self,
        *,
        room_id: str,
        entity_ids: list[str],
        vacancy_delay_min: int,
    ) -> ReactionProposal:
        template_id = "room.vacancy_lighting_off.basic"
        identity_key = f"room_vacancy_lighting_off|room={room_id}"
        entity_steps = [
            {
                "entity_id": entity_id,
                "action": "off",
                "brightness": None,
                "color_temp_kelvin": None,
                "rgb_color": None,
            }
            for entity_id in entity_ids
        ]
        description = (
            f"{room_id}: when vacancy persists for {vacancy_delay_min} minutes, "
            f"turn off {len(entity_steps)} light{'s' if len(entity_steps) != 1 else ''}"
        )
        return ReactionProposal(
            analyzer_id="AdminAuthoredRoomVacancyLightingOffTemplate",
            reaction_type="room_vacancy_lighting_off",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "room_vacancy_lighting_off",
                "room_id": room_id,
                "vacancy_delay_s": int(vacancy_delay_min) * 60,
                "followup_window_s": 900,
                "entity_steps": entity_steps,
                "plugin_family": "composite_room_assist",
                "admin_authored_template_id": template_id,
            },
        )

    def _build_admin_authored_security_presence_simulation_proposal(
        self,
        *,
        enabled: bool,
        allowed_rooms: list[str],
        allowed_entities: list[str],
        requires_dark_outside: bool,
        simulation_aggressiveness: str,
        min_jitter_override_min: int | None,
        max_jitter_override_min: int | None,
        max_events_per_evening_override: int | None,
        latest_end_time_override: str | None,
        skip_if_presence_detected: bool,
    ) -> ReactionProposal:
        template_id = "security.vacation_presence_simulation.basic"
        identity_key = "vacation_presence_simulation|scope=home"
        description = (
            "Vacation presence simulation using learned lighting routines as source profile"
        )
        return ReactionProposal(
            analyzer_id="AdminAuthoredSecurityPresenceSimulationTemplate",
            reaction_type="vacation_presence_simulation",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "vacation_presence_simulation",
                "enabled": enabled,
                "allowed_rooms": list(allowed_rooms),
                "allowed_entities": list(allowed_entities),
                "requires_dark_outside": requires_dark_outside,
                "simulation_aggressiveness": simulation_aggressiveness,
                "min_jitter_override_min": min_jitter_override_min,
                "max_jitter_override_min": max_jitter_override_min,
                "max_events_per_evening_override": max_events_per_evening_override,
                "latest_end_time_override": latest_end_time_override,
                "skip_if_presence_detected": skip_if_presence_detected,
                "plugin_family": "security_presence_simulation",
                "admin_authored_template_id": template_id,
                "dynamic_policy": True,
                "source_profile_kind": "accepted_lighting_reactions",
            },
        )

    @staticmethod
    def _action_entities_to_steps(entities: list[str]) -> list[dict[str, Any]]:
        """Normalize selected action entities into executable ApplyStep-like dicts."""
        steps: list[dict[str, Any]] = []
        for entity_id in entities:
            domain = str(entity_id).split(".", 1)[0]
            if domain == "scene":
                steps.append(
                    {
                        "domain": "lighting",
                        "target": entity_id,
                        "action": "scene.turn_on",
                        "params": {"entity_id": entity_id},
                    }
                )
            elif domain == "script":
                steps.append(
                    {
                        "domain": "script",
                        "target": entity_id,
                        "action": "script.turn_on",
                        "params": {"entity_id": entity_id},
                    }
                )
        return steps

    @staticmethod
    def _proposal_requires_action_completion(proposal: ReactionProposal) -> bool:
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        reaction_type = resolve_reaction_type(cfg) or str(proposal.reaction_type or "").strip()
        if reaction_type in {
            "lighting_scene_schedule",
            "room_darkness_lighting_assist",
            "vacation_presence_simulation",
        }:
            return False
        steps = cfg.get("steps")
        if isinstance(steps, list) and steps:
            return False
        entity_steps = cfg.get("entity_steps")
        if isinstance(entity_steps, list) and entity_steps:
            return False
        return True

    @staticmethod
    def _proposal_review_label(proposal: ReactionProposal) -> str:
        """Build a compact proposal review label with context and freshness."""
        description = str(proposal.description or "").strip()
        if len(description) > 72:
            description = description[:69].rstrip() + "..."

        cfg = dict(proposal.suggested_reaction_config or {})
        context_parts: list[str] = []
        room_id = str(cfg.get("room_id") or "").strip()
        house_state = str(cfg.get("house_state") or "").strip()
        weekday = cfg.get("weekday")

        if room_id:
            context_parts.append(f"room:{room_id}")
        elif house_state:
            context_parts.append(f"state:{house_state}")
        elif weekday not in (None, ""):
            context_parts.append(f"weekday:{weekday}")
        else:
            context_parts.append(f"type:{proposal.reaction_type}")

        badges = [f"{proposal.confidence:.0%}"]
        if proposal.origin == "admin_authored":
            badges.insert(0, "admin")
        last_seen = _format_last_seen(proposal.last_observed_at)
        if last_seen:
            badges.append(f"seen {last_seen}")

        return f"{description} ({', '.join(context_parts)}) [{' | '.join(badges)}]"

    def _proposal_review_placeholders(
        self,
        proposals: list[ReactionProposal],
        current: ReactionProposal,
        queue_len: int,
    ) -> dict[str, str]:
        """Build placeholders for guided proposal review."""
        pending = [proposal for proposal in proposals if proposal.status == "pending"]
        total = len(pending)
        position = total - queue_len + 1
        remaining = max(total - position, 0)
        return {
            "summary": self._proposals_step_summary(
                proposals, current=current, remaining=remaining
            ),
            "current_position": f"{position}/{total}",
            "proposal_label": self._proposal_review_title(current),
            "proposal_details": self._proposal_review_details(current),
        }

    def _proposal_review_action_options(self) -> dict[str, str]:
        """Return localized review actions for the proposal step."""
        language = self._flow_language()
        if language.startswith("it"):
            return {
                "accept": "Accetta questa proposta",
                "reject": "Rifiuta questa proposta",
                "skip": "Salta per ora",
            }
        return {
            "accept": "Accept this proposal",
            "reject": "Reject this proposal",
            "skip": "Skip for now",
        }

    def _proposal_review_title(self, proposal: ReactionProposal) -> str:
        """Build a concise, user-facing title for the current proposal."""
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        followup = self._proposal_followup_target(proposal)
        presenter = self._reaction_presenter_for_cfg(cfg)
        language = self._flow_language()
        if presenter is not None and presenter.proposal_review_title is not None:
            title = presenter.proposal_review_title(
                self,
                proposal,
                cfg,
                language,
                followup is not None,
            )
            if title:
                return title
        title = self._proposal_human_label(proposal, cfg)
        if followup is not None:
            if language.startswith("it"):
                return f"Affinamento: {title}"
            return f"Tuning: {title}"
        if proposal.origin != "admin_authored":
            return title
        if language.startswith("it"):
            return f"Bozza admin: {title}"
        return f"Admin draft: {title}"

    def _proposal_review_details(self, proposal: ReactionProposal) -> str:
        """Build a human-readable review body for one proposal."""
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        learning = _safe_mapping(cfg.get("learning_diagnostics"))
        language = self._flow_language()
        is_it = language.startswith("it")

        details: list[str] = []
        if proposal.origin == "admin_authored":
            details.extend(self._admin_authored_review_details(proposal, cfg, language))
            return "\n".join(details)

        followup = self._proposal_followup_target(proposal)
        if followup is not None:
            details.extend(self._proposal_tuning_review_details(proposal, followup, language))

        pattern_description = str(proposal.description or "").strip()
        title = self._proposal_human_label(proposal, cfg)
        if pattern_description and pattern_description != title:
            details.append(
                f"Pattern osservato: {pattern_description}"
                if is_it
                else f"Observed pattern: {pattern_description}"
            )

        evidence_parts: list[str] = []
        observations = learning.get("observations_count")
        episodes = learning.get("episodes_observed")
        weeks = learning.get("weeks_observed")
        if observations not in (None, ""):
            evidence_parts.append(
                f"{observations} osservazioni" if is_it else f"{observations} observations"
            )
        if episodes not in (None, ""):
            evidence_parts.append(f"{episodes} episodi" if is_it else f"{episodes} episodes")
        if weeks not in (None, ""):
            evidence_parts.append(f"{weeks} settimane" if is_it else f"{weeks} weeks")
        if evidence_parts:
            details.append(
                f"Evidenza: {', '.join(evidence_parts)}"
                if is_it
                else f"Evidence: {', '.join(evidence_parts)}"
            )

        details.append(
            f"Affidabilità: {proposal.confidence:.0%}"
            if is_it
            else f"Confidence: {proposal.confidence:.0%}"
        )
        last_seen = _format_last_seen(proposal.last_observed_at)
        if last_seen:
            details.append(
                f"Osservata l'ultima volta: {last_seen}" if is_it else f"Last seen: {last_seen}"
            )

        room_id = str(cfg.get("room_id") or "").strip()
        if room_id:
            details.append(f"Stanza: {room_id}" if is_it else f"Applies to room: {room_id}")
        house_state = str(cfg.get("house_state") or "").strip()
        if house_state:
            details.append(
                f"Si applica quando lo stato casa è: {house_state}"
                if is_it
                else f"Applies when house state is: {house_state}"
            )

        weekday = cfg.get("weekday")
        if weekday not in (None, ""):
            weekday_label = self._weekday_label(weekday, language)
            details.append(
                f"Giorno ricorrente: {weekday_label}"
                if is_it
                else f"Recurring day: {weekday_label}"
            )

        presenter = self._reaction_presenter_for_cfg(cfg)
        if presenter is not None and presenter.learned_review_details is not None:
            details.extend(presenter.learned_review_details(self, proposal, cfg, language))

        return "\n".join(details)

    def _proposal_tuning_review_details(
        self,
        proposal: ReactionProposal,
        followup: dict[str, Any],
        language: str,
    ) -> list[str]:
        is_it = language.startswith("it")
        details: list[str] = [
            (
                "Tipo proposta: affinamento di una automazione esistente"
                if is_it
                else "Proposal type: tuning of an existing automation"
            )
        ]

        reaction_label = str(followup.get("reaction_label") or "").strip()
        if reaction_label:
            details.append(
                f"Automazione target: {reaction_label}"
                if is_it
                else f"Target automation: {reaction_label}"
            )

        target_origin = str(followup.get("target_reaction_origin") or "").strip()
        if target_origin:
            origin_label = self._proposal_origin_label(target_origin, language)
            details.append(
                f"Origine automazione attiva: {origin_label}"
                if is_it
                else f"Active automation origin: {origin_label}"
            )

        target_template_id = str(followup.get("target_template_id") or "").strip()
        if target_template_id:
            details.append(f"Template target: {target_template_id}")

        reaction_cfg = _safe_mapping(followup.get("reaction_cfg"))
        presenter = self._reaction_presenter_for_cfg(reaction_cfg)
        if presenter is not None and presenter.tuning_review_details is not None:
            details.extend(
                presenter.tuning_review_details(
                    self,
                    proposal,
                    _safe_mapping(proposal.suggested_reaction_config),
                    reaction_cfg,
                    language,
                )
            )
        return details

    def _admin_authored_review_details(
        self,
        proposal: ReactionProposal,
        cfg: dict[str, Any],
        language: str,
    ) -> list[str]:
        is_it = language.startswith("it")
        details: list[str] = []

        template_id = str(cfg.get("admin_authored_template_id") or "").strip()
        if is_it:
            details.append("Origine: bozza richiesta dall'amministratore")
        else:
            details.append("Origin: draft requested by the administrator")

        if template_id:
            details.append(f"Template: {template_id}")

        details.append("Stato UX: bozza" if is_it else "UX state: draft")
        details.append(
            f"Affidabilità: {proposal.confidence:.0%}"
            if is_it
            else f"Confidence: {proposal.confidence:.0%}"
        )

        room_id = str(cfg.get("room_id") or "").strip()
        if room_id:
            details.append(f"Stanza: {room_id}" if is_it else f"Room: {room_id}")
        presenter = self._reaction_presenter_for_cfg(cfg)
        if presenter is not None and presenter.admin_authored_review_details is not None:
            details.extend(presenter.admin_authored_review_details(self, proposal, cfg, language))

        return details

    def _proposal_human_label(
        self,
        proposal: ReactionProposal,
        cfg: dict[str, Any] | None = None,
    ) -> str:
        """Build the most readable label available for a proposal."""
        cfg = _safe_mapping(cfg if cfg is not None else proposal.suggested_reaction_config)
        language = self._flow_language()
        presenter = self._reaction_presenter_for_cfg(cfg)
        if presenter is not None and presenter.proposal_human_label is not None:
            presented = presenter.proposal_human_label(self, proposal, cfg, language)
            if presented:
                return presented

        derived = self._reaction_label_from_config(
            proposal.proposal_id,
            cfg,
            {},
        )
        if derived != proposal.proposal_id:
            return derived

        room_id = str(cfg.get("room_id") or "").strip()
        house_state = str(cfg.get("house_state") or "").strip()
        weekday = cfg.get("weekday")

        if proposal.reaction_type == "room_cooling_assist" and room_id:
            return (
                f"Raffrescamento {room_id}" if language.startswith("it") else f"Cooling {room_id}"
            )
        if proposal.reaction_type == "room_air_quality_assist" and room_id:
            return f"Aria {room_id}" if language.startswith("it") else f"Air quality {room_id}"
        if proposal.reaction_type == "heating_preference" and house_state:
            return (
                f"Riscaldamento {house_state}"
                if language.startswith("it")
                else f"Heating {house_state}"
            )
        if proposal.reaction_type == "presence_preheat" and weekday not in (None, ""):
            day = self._weekday_label(weekday, language)
            if language.startswith("it"):
                return f"{day}: arrivo tipico"
            return f"{day}: typical arrival"

        return str(proposal.description or proposal.proposal_id)

    def _proposal_followup_target(self, proposal: ReactionProposal) -> dict[str, Any] | None:
        explicit_target_id = str(proposal.target_reaction_id or "").strip()
        if explicit_target_id:
            cfg = self._configured_reaction_cfg(explicit_target_id)
            reaction_cfg = dict(cfg or {})
            labels_map: dict[str, str] = self._reactions_options().get("labels", {})
            return {
                "reaction_id": explicit_target_id,
                "reaction_cfg": reaction_cfg,
                "reaction_label": self._reaction_label_from_config(
                    explicit_target_id, reaction_cfg, labels_map
                ),
                "target_reaction_origin": str(
                    proposal.target_reaction_origin or reaction_cfg.get("origin") or ""
                ),
                "target_template_id": str(
                    proposal.target_template_id or reaction_cfg.get("source_template_id") or ""
                ),
            }

        identity_key = str(proposal.identity_key or "").strip()
        if not identity_key:
            return None
        configured = dict(self._reactions_options().get("configured", {}))
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})
        for reaction_id, raw in configured.items():
            reaction_cfg = _safe_mapping(raw)
            if str(reaction_cfg.get("source_proposal_identity_key") or "").strip() != identity_key:
                continue
            return {
                "reaction_id": str(reaction_id),
                "reaction_cfg": reaction_cfg,
                "reaction_label": self._reaction_label_from_config(
                    str(reaction_id), reaction_cfg, labels_map
                ),
                "target_reaction_origin": str(reaction_cfg.get("origin") or ""),
                "target_template_id": str(reaction_cfg.get("source_template_id") or ""),
            }

        followup_slot_key = self._proposal_followup_slot_key(proposal)
        if followup_slot_key:
            ranked: list[tuple[tuple[int, int, int, str], str, dict[str, Any]]] = []
            proposal_cfg = _safe_mapping(proposal.suggested_reaction_config)
            proposal_entities = self._lighting_entity_actions(proposal_cfg)
            proposal_min = int(proposal_cfg.get("scheduled_min") or 0)
            for reaction_id, raw in configured.items():
                reaction_cfg = _safe_mapping(raw)
                if self._lighting_followup_slot_key_from_cfg(reaction_cfg) != followup_slot_key:
                    continue
                reaction_entities = self._lighting_entity_actions(reaction_cfg)
                overlap = len(proposal_entities & reaction_entities)
                symmetric_diff = len(proposal_entities ^ reaction_entities)
                reaction_min = int(reaction_cfg.get("scheduled_min") or 0)
                ranked.append(
                    (
                        (
                            -overlap,
                            symmetric_diff,
                            abs(proposal_min - reaction_min),
                            str(reaction_id),
                        ),
                        str(reaction_id),
                        reaction_cfg,
                    )
                )
            if ranked:
                ranked.sort(key=lambda item: item[0])
                _, reaction_id, reaction_cfg = ranked[0]
                return {
                    "reaction_id": reaction_id,
                    "reaction_cfg": reaction_cfg,
                    "reaction_label": self._reaction_label_from_config(
                        reaction_id, reaction_cfg, labels_map
                    ),
                    "target_reaction_origin": str(reaction_cfg.get("origin") or ""),
                    "target_template_id": str(reaction_cfg.get("source_template_id") or ""),
                }
        return None

    @staticmethod
    def _proposal_followup_slot_key(proposal: ReactionProposal) -> str:
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        reaction_type = str(proposal.reaction_type or "").strip() or resolve_reaction_type(cfg)
        if reaction_type != "lighting_scene_schedule":
            return ""
        scheduled_min = cfg.get("scheduled_min")
        bucket = None
        if isinstance(scheduled_min, (int, float)):
            bucket = (int(scheduled_min) // 30) * 30
        return (
            f"lighting_scene_schedule|room={cfg.get('room_id')}|weekday={cfg.get('weekday')}"
            f"|bucket={bucket}"
        )

    @staticmethod
    def _lighting_followup_slot_key_from_cfg(cfg: dict[str, Any]) -> str:
        reaction_type = resolve_reaction_type(cfg)
        if reaction_type != "lighting_scene_schedule":
            return ""
        scheduled_min = cfg.get("scheduled_min")
        bucket = None
        if isinstance(scheduled_min, (int, float)):
            bucket = (int(scheduled_min) // 30) * 30
        return (
            f"lighting_scene_schedule|room={cfg.get('room_id')}|weekday={cfg.get('weekday')}"
            f"|bucket={bucket}"
        )

    @staticmethod
    def _lighting_entity_actions(cfg: dict[str, Any]) -> set[tuple[str, str]]:
        entity_steps = cfg.get("entity_steps")
        if not isinstance(entity_steps, list):
            return set()
        pairs: set[tuple[str, str]] = set()
        for step in entity_steps:
            if not isinstance(step, dict):
                continue
            entity_id = str(step.get("entity_id") or "").strip()
            action = str(step.get("action") or "").strip()
            if entity_id:
                pairs.add((entity_id, action))
        return pairs

    @staticmethod
    def _lighting_identity_key(
        *,
        room_id: str,
        weekday: int,
        scheduled_min: int,
        entity_steps: list[dict[str, Any]],
    ) -> str:
        bucket = (scheduled_min // 30) * 30
        scene_signature = _lighting_scene_signature(entity_steps)
        return (
            f"lighting_scene_schedule|room={room_id}|weekday={weekday}"
            f"|bucket={bucket}|scene={scene_signature}"
        )

    def _configured_reaction_cfg(self, reaction_id: str) -> dict[str, Any] | None:
        configured = dict(self._reactions_options().get("configured", {}))
        raw = configured.get(reaction_id)
        if isinstance(raw, dict):
            return dict(raw)
        return None

    @staticmethod
    def _reaction_presenter_for_cfg(cfg: dict[str, Any]) -> Any | None:
        reaction_type = resolve_reaction_type(cfg)
        if not reaction_type:
            return None
        registry = create_builtin_reaction_plugin_registry()
        return registry.presenter_for(reaction_type)

    @staticmethod
    def _proposal_origin_label(origin: str, language: str) -> str:
        if language.startswith("it"):
            if origin == "admin_authored":
                return "bozza amministratore"
            if origin == "learned":
                return "appresa da Heima"
        else:
            if origin == "admin_authored":
                return "admin-authored"
            if origin == "learned":
                return "learned"
        return origin

    @staticmethod
    def _weekday_label(weekday: Any, language: str) -> str:
        it_days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        en_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        try:
            index = int(weekday)
            if 0 <= index <= 6:
                return it_days[index] if language.startswith("it") else en_days[index]
        except (TypeError, ValueError):
            pass
        return str(weekday)

    def _proposals_step_summary(
        self,
        proposals: list[ReactionProposal],
        *,
        current: ReactionProposal | None = None,
        remaining: int | None = None,
    ) -> str:
        language = self._flow_language()
        is_it = language.startswith("it")
        pending = [proposal for proposal in proposals if proposal.status == "pending"]
        if not pending:
            return "—"
        total = len(pending)
        if current is None:
            if is_it:
                return "1 proposta pendente" if total == 1 else f"{total} proposte pendenti"
            return f"{total} pending proposal{'s' if total != 1 else ''}"
        return ""

    def _flow_language(self) -> str:
        return str(getattr(getattr(self.hass, "config", None), "language", "en") or "en").lower()

    def _get_coordinator(self) -> Any | None:
        """Return the running coordinator for this entry, or None."""
        try:
            entry_id = self._config_entry.entry_id
            coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id, {}).get("coordinator")
            return coordinator
        except Exception:
            _LOGGER.debug("Could not retrieve coordinator", exc_info=True)
            return None

    def _get_registered_reaction_labels(self) -> dict[str, str]:
        """Return {reaction_id: human_readable_label} for all reactions available for muting.

        Label is derived from the stored reaction config (always up-to-date), with the
        saved ``labels`` entry as fallback for unknown reaction classes.
        """
        result: dict[str, str] = {}
        configured: dict[str, Any] = self._reactions_options().get("configured", {})
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})

        # 1. Running engine reactions (already persisted and loaded)
        try:
            coordinator = self._get_coordinator()
            engine = getattr(coordinator, "engine", None) if coordinator else None
            for r in getattr(engine, "_reactions", []):
                rid = r.reaction_id
                if rid not in result:
                    cfg = configured.get(rid, {})
                    result[rid] = self._reaction_label_from_config(rid, cfg, labels_map)
        except Exception:
            _LOGGER.debug("Could not query registered reactions", exc_info=True)

        # 2. Configured reactions from in-session accepted proposals (not yet saved)
        for pid, cfg in configured.items():
            if pid not in result:
                result[pid] = self._reaction_label_from_config(pid, cfg, labels_map)

        return result

    @staticmethod
    def _reaction_label_from_config(
        reaction_id: str, cfg: dict[str, Any], labels_map: dict[str, str]
    ) -> str:
        """Derive a human-readable label from a stored reaction config dict.

        For PresencePatternReaction: generates "Weekday: arrival at HH:MM (± N min)"
        from weekday + median_arrival_min + window_half_min stored in the config.
        Falls back to labels_map, then to reaction_id.
        """
        registry = create_builtin_reaction_plugin_registry()
        reaction_type = resolve_reaction_type(cfg)
        presenter = registry.presenter_for(reaction_type)
        if presenter is not None and presenter.reaction_label_from_config is not None:
            presented = presenter.reaction_label_from_config(reaction_id, cfg, labels_map)
            if presented:
                return presented

        if reaction_type == "presence_preheat":
            try:
                weekday = int(cfg["weekday"])
                median_min = int(cfg["median_arrival_min"])
                window_half = int(cfg.get("window_half_min", 0))
                hhmm = f"{median_min // 60:02d}:{median_min % 60:02d}"
                spread = f" (± {window_half} min)" if window_half > 0 else ""
                day = _ReactionsStepsMixin._weekday_label(weekday, "it")
                return f"{day}: arrivo alle {hhmm}{spread}"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        if reaction_type == "lighting_scene_schedule":
            try:
                weekday = int(cfg["weekday"])
                scheduled_min = int(cfg["scheduled_min"])
                room_id = str(cfg.get("room_id", ""))
                hhmm = f"{scheduled_min // 60:02d}:{scheduled_min % 60:02d}"
                day = _ReactionsStepsMixin._weekday_label(weekday, "it")
                n_steps = len(cfg.get("entity_steps", []))
                return f"Luci {room_id} — {day} ~{hhmm} ({n_steps} entità)"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        if reaction_type in {
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
        }:
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                humidity_entities = list(cfg.get("trigger_signal_entities", []))
                temperature_entities = list(cfg.get("temperature_signal_entities", []))
                observed = int(cfg.get("episodes_observed", 0))
                parts = [f"Assist {room_id}"]
                if humidity_entities:
                    parts.append(f"hum:{len(humidity_entities)}")
                if temperature_entities:
                    parts.append(f"temp:{len(temperature_entities)}")
                if observed > 0:
                    parts.append(f"{observed} episodi")
                return " — ".join(parts)
            except (TypeError, ValueError):
                pass

        if reaction_type == "room_darkness_lighting_assist":
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                primary_entities = list(cfg.get("primary_signal_entities", []))
                entity_steps = list(cfg.get("entity_steps", []))
                parts = [f"Luce {room_id}"]
                if primary_entities:
                    parts.append(f"lux:{len(primary_entities)}")
                if entity_steps:
                    parts.append(f"{len(entity_steps)} entità")
                return " — ".join(parts)
            except (TypeError, ValueError):
                pass

        return labels_map.get(reaction_id, reaction_id)


def _format_last_seen(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (TypeError, ValueError):
        return ""


def _safe_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _parse_hhmm_to_min(value: str) -> int | None:
    raw = value.strip()
    if not raw or ":" not in raw:
        return None
    hour_str, minute_str = raw.split(":", 1)
    try:
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _lighting_scene_signature(entity_steps: list[dict[str, Any]]) -> str:
    normalized_steps: list[str] = []
    for raw_step in entity_steps:
        if not isinstance(raw_step, dict):
            continue
        entity_id = str(raw_step.get("entity_id") or "").strip()
        action = str(raw_step.get("action") or "").strip() or "unknown"
        if not entity_id:
            continue
        brightness = _coarse_numeric_bucket(raw_step.get("brightness"), step=32)
        color_temp = _coarse_numeric_bucket(raw_step.get("color_temp_kelvin"), step=250)
        rgb = _normalize_rgb(raw_step.get("rgb_color"))
        normalized_steps.append(
            "|".join(
                [
                    entity_id,
                    action,
                    f"b={brightness if brightness is not None else '-'}",
                    f"k={color_temp if color_temp is not None else '-'}",
                    f"rgb={rgb if rgb is not None else '-'}",
                ]
            )
        )
    if not normalized_steps:
        return "none"
    normalized_steps.sort()
    return "||".join(normalized_steps)


def _coarse_numeric_bucket(value: Any, *, step: int) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    return int(round(float(value) / step) * step)


def _normalize_rgb(value: Any) -> str | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return ",".join(str(int(channel)) for channel in value)
    except (TypeError, ValueError):
        return None
