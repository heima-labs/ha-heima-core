"""Options flow: admin-authored reaction creation steps."""

# mypy: ignore-errors

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from ..const import OPT_REACTIONS
from ..room_sources import room_signal_bucket_labels, room_signal_entity_id, room_signal_names
from ..runtime.analyzers.base import ReactionProposal
from ..runtime.reactions import validate_contextual_lighting_contract

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _ReactionAdminAuthoredStepsMixin:
    """Mixin for admin-authored reaction creation flows."""

    def _persist_admin_authored_reaction(self, proposal: ReactionProposal) -> None:
        """Persist an admin-authored reaction to options without closing the flow."""
        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels: dict[str, str] = dict(reactions_cfg.get("labels", {}))
        reaction_id = proposal.proposal_id
        configured[reaction_id] = self._configured_reaction_from_proposal(proposal)
        labels[reaction_id] = proposal.description
        reactions_cfg["configured"] = configured
        reactions_cfg["labels"] = labels
        options = self._entry_options_snapshot()
        options[OPT_REACTIONS] = reactions_cfg
        self.options = options
        config_entry = getattr(self, "_config_entry", None)
        if config_entry is not None:
            try:
                config_entry.options = dict(options)
            except (AttributeError, TypeError):
                pass

    async def _store_admin_authored_reaction_directly(
        self, proposal: ReactionProposal
    ) -> "FlowResult":
        """Persist an admin-authored reaction and return to the main menu."""
        self._persist_admin_authored_reaction(proposal)
        return await self.async_step_init(None)

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
                data_schema=self._vacation_presence_simulation_editor_schema(
                    defaults,
                    include_delete=False,
                ),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )
        current_input, resolved, errors = self._normalize_security_presence_simulation_submission(
            user_input=user_input,
            defaults=defaults,
            include_delete=False,
        )

        if errors:
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._vacation_presence_simulation_editor_schema(
                    current_input,
                    include_delete=False,
                ),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal = self._build_admin_authored_security_presence_simulation_proposal(
            enabled=bool(resolved["enabled"]),
            allowed_rooms=list(resolved["allowed_rooms"]),
            allowed_entities=list(resolved["allowed_entities"]),
            requires_dark_outside=bool(resolved["requires_dark_outside"]),
            simulation_aggressiveness=str(resolved["simulation_aggressiveness"]),
            min_jitter_override_min=resolved["min_jitter_override_min"],
            max_jitter_override_min=resolved["max_jitter_override_min"],
            max_events_per_evening_override=resolved["max_events_per_evening_override"],
            latest_end_time_override=resolved["latest_end_time_override"],
            skip_if_presence_detected=bool(resolved["skip_if_presence_detected"]),
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._vacation_presence_simulation_editor_schema(
                    current_input,
                    include_delete=False,
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self.async_show_form(
                step_id="admin_authored_security_presence_simulation",
                data_schema=self._vacation_presence_simulation_editor_schema(
                    current_input,
                    include_delete=False,
                ),
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

        if user_input is None:
            return self._show_room_signal_assist_editor(
                step_id="admin_authored_room_signal_assist",
                defaults=defaults,
                template_title=template.title,
                template_description=template.description,
                room_id=defaults["room_id"],
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        current_input, resolved, errors = self._normalize_room_signal_assist_editor_submission(
            user_input=user_input,
            defaults=defaults,
            room_id=None,
            include_room_id=True,
            include_enabled=False,
            include_delete=False,
        )
        room_id = str(resolved["room_id"])

        if errors:
            return self._show_room_signal_assist_editor(
                step_id="admin_authored_room_signal_assist",
                defaults=current_input,
                errors=errors,
                template_title=template.title,
                template_description=template.description,
                room_id=room_id or defaults["room_id"],
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        proposal = self._build_admin_authored_room_signal_assist_proposal(
            room_id=room_id,
            primary_signal_entities=resolved["primary_signal_entities"],
            primary_signal_name=str(resolved["primary_signal_name"]),
            primary_trigger_mode=str(resolved["primary_trigger_mode"]),
            primary_bucket=str(resolved["primary_bucket"]),
            primary_bucket_match_mode=str(resolved["primary_bucket_match_mode"]),
            corroboration_signal_entities=resolved["corroboration_signal_entities"],
            corroboration_signal_name=str(resolved["corroboration_signal_name"]),
            corroboration_bucket=str(resolved["corroboration_bucket"]),
            corroboration_bucket_match_mode=str(resolved["corroboration_bucket_match_mode"]),
            action_entities=list(resolved["action_entities"]),
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self._show_room_signal_assist_editor(
                step_id="admin_authored_room_signal_assist",
                defaults=current_input,
                errors={"base": "duplicate"},
                template_title=template.title,
                template_description=template.description,
                room_id=room_id,
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self._show_room_signal_assist_editor(
                step_id="admin_authored_room_signal_assist",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                template_title=template.title,
                template_description=template.description,
                room_id=room_id,
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    async def async_step_admin_authored_room_darkness_lighting_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Legacy alias for the Phase AB smart lighting template."""
        return await self.async_step_admin_authored_room_smart_lighting_assist(user_input)

    async def async_step_admin_authored_room_smart_lighting_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored room smart lighting assist proposal."""
        return await self._async_step_admin_authored_room_smart_lighting_assist_form(
            user_input=user_input,
            step_id="admin_authored_room_smart_lighting_assist",
        )

    async def _async_step_admin_authored_room_smart_lighting_assist_form(
        self,
        *,
        user_input: dict[str, Any] | None,
        step_id: str,
    ) -> "FlowResult":
        template = self._admin_authored_template("room.smart_lighting_assist.basic")
        room_ids = self._room_ids()
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
            "light_entities": [],
        }

        if user_input is None:
            return self._show_room_darkness_lighting_editor(
                step_id=step_id,
                defaults=defaults,
                template_title=template.title,
                template_description=template.description,
                room_id=default_room_id,
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        current_input, resolved, errors = self._normalize_room_darkness_lighting_editor_submission(
            user_input=user_input,
            defaults=defaults,
            room_id=None,
            include_room_id=True,
            include_enabled=False,
            include_delete=False,
        )
        room_id = str(resolved["room_id"])

        if errors:
            return self._show_room_darkness_lighting_editor(
                step_id=step_id,
                defaults=current_input,
                errors=errors,
                template_title=template.title,
                template_description=template.description,
                room_id=room_id or default_room_id,
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        proposal = self._build_admin_authored_room_smart_lighting_assist_proposal(
            room_id=room_id,
            primary_signal_entities=resolved["primary_signal_entities"],
            primary_signal_name=str(resolved["primary_signal_name"]),
            primary_bucket=str(resolved["primary_bucket"]),
            primary_bucket_match_mode=str(resolved["primary_bucket_match_mode"]),
            entity_ids=list(resolved["light_entities"]),
            action=str(resolved["action"]),
            brightness=resolved["brightness"],
            color_temp_kelvin=resolved["color_temp_kelvin"],
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self._show_room_darkness_lighting_editor(
                step_id=step_id,
                defaults=current_input,
                errors={"base": "duplicate"},
                template_title=template.title,
                template_description=template.description,
                room_id=room_id,
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self._show_room_darkness_lighting_editor(
                step_id=step_id,
                defaults=current_input,
                errors={"base": "redacted_payload"},
                template_title=template.title,
                template_description=template.description,
                room_id=room_id,
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )

        return await self._store_admin_authored_reaction_directly(proposal)

    async def async_step_admin_authored_room_contextual_lighting_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a contextual lighting assist via guided inputs + JSON policy."""
        return await self.async_step_admin_authored_room_smart_lighting_assist(user_input)
        template = self._admin_authored_template("room.contextual_lighting_assist.basic")
        room_ids = self._room_ids()
        rooms = self._rooms()
        if template is None or not room_ids:
            return await self.async_step_init()

        default_room_id = room_ids[0]
        defaults = {
            "room_id": default_room_id,
            "primary_signal_name": "room_lux",
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "preset": "all_day_adaptive",
            "light_entities": [],
        }
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_room_contextual_lighting_assist",
                data_schema=self._admin_authored_room_contextual_lighting_assist_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                    "available_signals": self._format_room_signals_placeholder(
                        rooms, default_room_id
                    ),
                    "preset_previews": self._contextual_lighting_preset_previews(),
                },
            )

        room_id = str(user_input.get("room_id") or defaults.get("room_id") or "").strip()
        primary_signal_name = str(user_input.get("primary_signal_name") or "room_lux").strip()
        primary_bucket = str(user_input.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(
            user_input.get("primary_bucket_match_mode") or defaults["primary_bucket_match_mode"]
        ).strip()
        preset = str(user_input.get("preset") or defaults["preset"]).strip()
        light_entities = self._normalize_multi_value(user_input.get("light_entities"))

        if not room_id:
            errors["room_id"] = "required"
        if not light_entities:
            errors["light_entities"] = "required"
        valid_signals = room_signal_names(rooms, room_id) if room_id else []
        if not primary_signal_name:
            errors["primary_signal_name"] = "required"
        elif valid_signals and primary_signal_name not in valid_signals:
            errors["primary_signal_name"] = "invalid_signal_name"
        if not errors.get("primary_signal_name") and room_id:
            valid_buckets = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
            if not primary_bucket:
                errors["primary_bucket"] = "required"
            elif valid_buckets and primary_bucket not in valid_buckets:
                errors["primary_bucket"] = "invalid_bucket"
        if primary_bucket_match_mode not in self._bucket_match_mode_options():
            errors["primary_bucket_match_mode"] = "invalid_option"
        if preset not in self._contextual_lighting_preset_options():
            errors["preset"] = "invalid_option"

        current_input = {
            "room_id": room_id or default_room_id,
            "primary_signal_name": primary_signal_name or "room_lux",
            "primary_bucket": primary_bucket or defaults["primary_bucket"],
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "preset": preset or defaults["preset"],
            "light_entities": light_entities,
        }
        if errors:
            return self.async_show_form(
                step_id="admin_authored_room_contextual_lighting_assist",
                data_schema=self._admin_authored_room_contextual_lighting_assist_schema(
                    current_input
                ),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                    "available_signals": self._format_room_signals_placeholder(
                        rooms, room_id or default_room_id
                    ),
                    "preset_previews": self._contextual_lighting_preset_previews(),
                },
            )

        primary_entity_id = room_signal_entity_id(rooms, room_id, primary_signal_name)
        primary_signal_entities = [primary_entity_id] if primary_entity_id else []
        self._pending_contextual_lighting_seed = {
            "room_id": room_id,
            "primary_signal_name": primary_signal_name,
            "primary_signal_entities": primary_signal_entities,
            "primary_bucket": primary_bucket,
            "primary_bucket_match_mode": primary_bucket_match_mode,
            "preset": preset,
            "light_entities": light_entities,
            "template_title": template.title,
            "template_description": template.description,
        }
        return await self.async_step_admin_authored_room_contextual_lighting_assist_json()

    async def async_step_admin_authored_room_contextual_lighting_assist_json(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Edit the generated contextual lighting JSON before persisting it."""
        return await self.async_step_init()
        seed = dict(getattr(self, "_pending_contextual_lighting_seed", {}) or {})
        if not seed:
            return await self.async_step_init()

        light_entities = list(seed.get("light_entities") or [])
        preset = str(seed.get("preset") or "all_day_adaptive")
        default_json = self._contextual_lighting_policy_json(
            preset=preset,
            light_entities=light_entities,
        )
        defaults = {"preset": preset, "config_json": default_json}
        if user_input is None:
            return self._show_contextual_lighting_policy_editor(
                step_id="admin_authored_room_contextual_lighting_assist_json",
                defaults=defaults,
                template_title=str(seed.get("template_title") or ""),
                template_description=str(seed.get("template_description") or ""),
                include_enabled=False,
                include_delete=False,
            )

        normalized_preset, config_json = self._normalize_contextual_policy_editor_submission(
            user_input=user_input,
            defaults=defaults,
            light_entities=light_entities,
        )
        try:
            contract = json.loads(config_json)
            if not isinstance(contract, dict):
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._show_contextual_lighting_policy_editor(
                step_id="admin_authored_room_contextual_lighting_assist_json",
                defaults={"preset": normalized_preset, "config_json": config_json},
                template_title=str(seed.get("template_title") or ""),
                template_description=str(seed.get("template_description") or ""),
                errors={"config_json": "invalid_json"},
                include_enabled=False,
                include_delete=False,
            )

        if not validate_contextual_lighting_contract(contract):
            return self._show_contextual_lighting_policy_editor(
                step_id="admin_authored_room_contextual_lighting_assist_json",
                defaults={"preset": normalized_preset, "config_json": config_json},
                template_title=str(seed.get("template_title") or ""),
                template_description=str(seed.get("template_description") or ""),
                errors={"config_json": "invalid_contextual_contract"},
                include_enabled=False,
                include_delete=False,
            )

        proposal = self._build_admin_authored_room_contextual_lighting_assist_proposal(
            room_id=str(seed.get("room_id") or ""),
            primary_signal_name=str(seed.get("primary_signal_name") or "room_lux"),
            primary_signal_entities=list(seed.get("primary_signal_entities") or []),
            primary_bucket=str(seed.get("primary_bucket") or ""),
            primary_bucket_match_mode=str(seed.get("primary_bucket_match_mode") or "eq"),
            contract=contract,
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self._show_contextual_lighting_policy_editor(
                step_id="admin_authored_room_contextual_lighting_assist_json",
                defaults={"preset": normalized_preset, "config_json": config_json},
                template_title=str(seed.get("template_title") or ""),
                template_description=str(seed.get("template_description") or ""),
                errors={"base": "duplicate"},
                include_enabled=False,
                include_delete=False,
            )
        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self._show_contextual_lighting_policy_editor(
                step_id="admin_authored_room_contextual_lighting_assist_json",
                defaults={"preset": normalized_preset, "config_json": config_json},
                template_title=str(seed.get("template_title") or ""),
                template_description=str(seed.get("template_description") or ""),
                errors={"base": "redacted_payload"},
                include_enabled=False,
                include_delete=False,
            )

        self._pending_contextual_lighting_seed = {}
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
            return self._show_admin_authored_room_vacancy_lighting_off_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                defaults=defaults,
                template_title=template.title,
                template_description=template.description,
            )
        current_input, resolved, errors = (
            self._normalize_room_vacancy_lighting_off_editor_submission(
                user_input=user_input,
                defaults=defaults,
                room_id="",
                include_room_id=True,
                include_enabled=False,
                include_delete=False,
            )
        )
        if errors:
            return self._show_admin_authored_room_vacancy_lighting_off_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                defaults=current_input,
                errors=errors,
                template_title=template.title,
                template_description=template.description,
            )

        proposal = self._build_admin_authored_room_vacancy_lighting_off_proposal(
            room_id=str(resolved["room_id"]),
            entity_ids=list(resolved["light_entities"]),
            vacancy_delay_min=int(resolved["vacancy_delay_min"]),
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self._show_admin_authored_room_vacancy_lighting_off_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                defaults=current_input,
                errors={"base": "duplicate"},
                template_title=template.title,
                template_description=template.description,
            )

        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self._show_admin_authored_room_vacancy_lighting_off_form(
                step_id="admin_authored_room_vacancy_lighting_off",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                template_title=template.title,
                template_description=template.description,
            )

        self._persist_admin_authored_reaction(proposal)
        return self.async_create_entry(title="", data=self._finalize_options())

    async def async_step_admin_authored_scheduled_routine(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored scheduled routine."""
        template = self._admin_authored_template("scheduled_routine.basic")
        if template is None:
            return await self.async_step_init()

        defaults = {
            "weekday": "0",
            "scheduled_time": "20:00",
            "routine_kind": "scene",
            "target_entities": [],
            "entity_action": "turn_on",
            "house_state_in": [],
            "skip_if_anyone_home": False,
        }
        if user_input is None:
            return self._show_scheduled_routine_editor(
                step_id="admin_authored_scheduled_routine",
                defaults=defaults,
                template_title=template.title,
                template_description=template.description,
                include_enabled=False,
                include_delete=False,
            )

        current_input, resolved, errors = self._normalize_scheduled_routine_submission(
            user_input=user_input,
            defaults=defaults,
            include_enabled=False,
            include_delete=False,
        )
        if errors:
            return self._show_scheduled_routine_editor(
                step_id="admin_authored_scheduled_routine",
                defaults=current_input,
                errors=errors,
                template_title=template.title,
                template_description=template.description,
                include_enabled=False,
                include_delete=False,
            )

        proposal = self._build_admin_authored_scheduled_routine_proposal(
            weekday=int(resolved["weekday"]),
            scheduled_min=int(resolved["scheduled_min"]),
            routine_kind=str(resolved["routine_kind"]),
            target_entities=list(resolved["target_entities"]),
            entity_action=str(resolved["entity_action"]),
            house_state_in=list(resolved["house_state_in"]),
            skip_if_anyone_home=bool(resolved["skip_if_anyone_home"]),
        )
        if self._admin_authored_identity_conflicts(proposal):
            return self._show_scheduled_routine_editor(
                step_id="admin_authored_scheduled_routine",
                defaults=current_input,
                errors={"base": "duplicate"},
                template_title=template.title,
                template_description=template.description,
                include_enabled=False,
                include_delete=False,
            )
        if self._has_redacted_payload(proposal.suggested_reaction_config):
            return self._show_scheduled_routine_editor(
                step_id="admin_authored_scheduled_routine",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                template_title=template.title,
                template_description=template.description,
                include_enabled=False,
                include_delete=False,
            )

        self._persist_admin_authored_reaction(proposal)
        return self.async_create_entry(title="", data=self._finalize_options())
