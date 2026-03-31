"""Options flow: Reactions step (persisted mute management + proposal review)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN, OPT_REACTIONS
from ..runtime.analyzers import create_builtin_learning_plugin_registry
from ..runtime.analyzers.base import ReactionProposal
from ..runtime.reactions import create_builtin_reaction_plugin_registry
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class _ReactionsStepsMixin:
    """Mixin for reactions step."""

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
            )

        template_id = str(user_input.get("template_id") or "").strip()
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
        coordinator = self._get_coordinator()
        proposal_engine = getattr(coordinator, "proposal_engine", None) if coordinator else None
        if proposal_engine is None:
            return await self.async_step_init()

        existing = proposal_engine.proposal_by_identity_key(proposal.identity_key)
        if existing is not None and existing.status != "pending":
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
                        "color_temp_kelvin": color_temp_kelvin
                        or defaults["color_temp_kelvin"],
                    }
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal_id = await proposal_engine.async_submit_proposal(proposal)
        self._proposal_review_queue = [proposal_id]
        return await self.async_step_proposals()

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
            "primary_signal_name": "humidity",
            "primary_threshold_mode": "rise",
            "primary_threshold": 8.0,
            "corroboration_signal_name": "temperature",
            "corroboration_threshold_mode": "rise",
            "corroboration_threshold": 0.8,
            "action_entities": [],
        }
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        room_id = str(user_input.get("room_id") or "").strip()
        primary_signal_entities = self._normalize_multi_value(
            user_input.get("primary_signal_entities")
        )
        primary_signal_name = str(user_input.get("primary_signal_name") or "primary").strip()
        corroboration_signal_entities = self._normalize_multi_value(
            user_input.get("corroboration_signal_entities")
        )
        corroboration_signal_name = str(
            user_input.get("corroboration_signal_name") or "corroboration"
        ).strip()
        action_entities = self._normalize_multi_value(user_input.get("action_entities"))

        if not room_id:
            errors["room_id"] = "required"
        if not primary_signal_entities:
            errors["primary_signal_entities"] = "required"
        if not action_entities:
            errors["action_entities"] = "required"

        primary_threshold_mode = str(user_input.get("primary_threshold_mode") or "rise").strip()
        if primary_threshold_mode not in self._signal_threshold_mode_options():
            errors["primary_threshold_mode"] = "invalid_selection"
            primary_threshold_mode = defaults["primary_threshold_mode"]

        try:
            primary_threshold = float(user_input.get("primary_threshold") or 0)
            if primary_threshold <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors["primary_threshold"] = "invalid_number"
            primary_threshold = defaults["primary_threshold"]

        corroboration_threshold_mode = str(
            user_input.get("corroboration_threshold_mode") or "rise"
        ).strip()
        if corroboration_threshold_mode not in self._signal_threshold_mode_options():
            errors["corroboration_threshold_mode"] = "invalid_selection"
            corroboration_threshold_mode = defaults["corroboration_threshold_mode"]

        try:
            corroboration_threshold = float(user_input.get("corroboration_threshold") or 0)
            if corroboration_signal_entities and corroboration_threshold <= 0:
                raise ValueError
            if not corroboration_signal_entities:
                corroboration_threshold = 0.0
        except (TypeError, ValueError):
            errors["corroboration_threshold"] = "invalid_number"
            corroboration_threshold = defaults["corroboration_threshold"]

        if errors:
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(
                    {
                        "room_id": room_id or defaults["room_id"],
                        "primary_signal_entities": primary_signal_entities,
                        "primary_signal_name": primary_signal_name or defaults["primary_signal_name"],
                        "primary_threshold_mode": primary_threshold_mode,
                        "primary_threshold": primary_threshold,
                        "corroboration_signal_entities": corroboration_signal_entities,
                        "corroboration_signal_name": corroboration_signal_name
                        or defaults["corroboration_signal_name"],
                        "corroboration_threshold_mode": corroboration_threshold_mode,
                        "corroboration_threshold": corroboration_threshold,
                        "action_entities": action_entities,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal = self._build_admin_authored_room_signal_assist_proposal(
            room_id=room_id,
            primary_signal_entities=primary_signal_entities,
            primary_signal_name=primary_signal_name or "primary",
            primary_threshold_mode=primary_threshold_mode,
            primary_threshold=primary_threshold,
            corroboration_signal_entities=corroboration_signal_entities,
            corroboration_signal_name=corroboration_signal_name or "corroboration",
            corroboration_threshold_mode=corroboration_threshold_mode,
            corroboration_threshold=corroboration_threshold,
            action_entities=action_entities,
        )
        coordinator = self._get_coordinator()
        proposal_engine = getattr(coordinator, "proposal_engine", None) if coordinator else None
        if proposal_engine is None:
            return await self.async_step_init()

        existing = proposal_engine.proposal_by_identity_key(proposal.identity_key)
        if existing is not None and existing.status != "pending":
            return self.async_show_form(
                step_id="admin_authored_room_signal_assist",
                data_schema=self._admin_authored_room_signal_assist_schema(
                    {
                        "room_id": room_id,
                        "primary_signal_entities": primary_signal_entities,
                        "primary_signal_name": primary_signal_name,
                        "primary_threshold_mode": primary_threshold_mode,
                        "primary_threshold": primary_threshold,
                        "corroboration_signal_entities": corroboration_signal_entities,
                        "corroboration_signal_name": corroboration_signal_name,
                        "corroboration_threshold_mode": corroboration_threshold_mode,
                        "corroboration_threshold": corroboration_threshold,
                        "action_entities": action_entities,
                    }
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal_id = await proposal_engine.async_submit_proposal(proposal)
        self._proposal_review_queue = [proposal_id]
        return await self.async_step_proposals()

    async def async_step_admin_authored_room_darkness_lighting_assist(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Create a bounded admin-authored room darkness lighting assist proposal."""
        template = self._admin_authored_template("room.darkness_lighting_assist.basic")
        room_ids = self._room_ids()
        if template is None or not room_ids:
            return await self.async_step_init()

        defaults = {
            "room_id": room_ids[0],
            "primary_signal_name": "room_lux",
            "primary_threshold": 120.0,
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(defaults),
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        room_id = str(user_input.get("room_id") or "").strip()
        primary_signal_entities = self._normalize_multi_value(
            user_input.get("primary_signal_entities")
        )
        primary_signal_name = str(user_input.get("primary_signal_name") or "room_lux").strip()
        action = str(user_input.get("action") or "on").strip()
        entity_ids = self._normalize_multi_value(user_input.get("light_entities"))

        if not room_id:
            errors["room_id"] = "required"
        if not primary_signal_entities:
            errors["primary_signal_entities"] = "required"
        if not entity_ids:
            errors["light_entities"] = "required"

        try:
            primary_threshold = float(user_input.get("primary_threshold") or 0)
            if primary_threshold <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors["primary_threshold"] = "invalid_number"
            primary_threshold = defaults["primary_threshold"]

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
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(
                    {
                        "room_id": room_id or defaults["room_id"],
                        "primary_signal_entities": primary_signal_entities,
                        "primary_signal_name": primary_signal_name or defaults["primary_signal_name"],
                        "primary_threshold": primary_threshold,
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

        proposal = self._build_admin_authored_room_darkness_lighting_assist_proposal(
            room_id=room_id,
            primary_signal_entities=primary_signal_entities,
            primary_signal_name=primary_signal_name or "room_lux",
            primary_threshold=primary_threshold,
            entity_ids=entity_ids,
            action=action,
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
        )
        coordinator = self._get_coordinator()
        proposal_engine = getattr(coordinator, "proposal_engine", None) if coordinator else None
        if proposal_engine is None:
            return await self.async_step_init()

        existing = proposal_engine.proposal_by_identity_key(proposal.identity_key)
        if existing is not None and existing.status != "pending":
            return self.async_show_form(
                step_id="admin_authored_room_darkness_lighting_assist",
                data_schema=self._admin_authored_room_darkness_lighting_assist_schema(
                    {
                        "room_id": room_id,
                        "primary_signal_entities": primary_signal_entities,
                        "primary_signal_name": primary_signal_name,
                        "primary_threshold": primary_threshold,
                        "light_entities": entity_ids,
                        "action": action,
                        "brightness": brightness or defaults["brightness"],
                        "color_temp_kelvin": color_temp_kelvin
                        or defaults["color_temp_kelvin"],
                    }
                ),
                errors={"base": "duplicate"},
                description_placeholders={
                    "template_title": template.title,
                    "template_description": template.description,
                },
            )

        proposal_id = await proposal_engine.async_submit_proposal(proposal)
        self._proposal_review_queue = [proposal_id]
        return await self.async_step_proposals()

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
        self._update_options({OPT_REACTIONS: {"muted": muted}})
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
            schema = vol.Schema(
                {vol.Required("reaction"): vol.In(reaction_labels)}
            )
            return self.async_show_form(step_id="reactions_edit", data_schema=schema)

        self._editing_reaction_id = user_input.get("reaction")
        return await self.async_step_reactions_edit_form()

    async def async_step_reactions_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Edit action_entities and pre_condition_min for the selected reaction."""
        pid = getattr(self, "_editing_reaction_id", None)
        if not pid:
            return await self.async_step_init()

        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels_map: dict[str, str] = reactions_cfg.get("labels", {})
        cfg = dict(configured.get(pid, {}))

        if user_input is None:
            current_steps = cfg.get("steps", [])
            current_entities = [s["target"] for s in current_steps if isinstance(s, dict) and "target" in s]
            current_pre = cfg.get("pre_condition_min", 20)
            schema = vol.Schema(
                {
                    vol.Optional("action_entities"): _entity_selector(
                        ["scene", "script"], multiple=True
                    ),
                    vol.Optional("pre_condition_min", default=current_pre): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=120)
                    ),
                }
            )
            label = self._reaction_label_from_config(pid, cfg, labels_map)
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self.add_suggested_values_to_schema(
                    schema, {"action_entities": current_entities, "pre_condition_min": current_pre}
                ),
                description_placeholders={"reaction_description": label},
            )

        entities = self._normalize_multi_value(user_input.get("action_entities"))
        steps = self._action_entities_to_steps(entities)
        cfg["steps"] = steps
        cfg["pre_condition_min"] = int(user_input.get("pre_condition_min") or 20)
        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._update_options({OPT_REACTIONS: reactions_cfg})
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
                description_placeholders=self._proposal_review_placeholders(pending, current, len(queue)),
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
                    target_reaction_class=str(followup["reaction_cfg"].get("reaction_class") or ""),
                    target_reaction_origin=str(followup.get("target_reaction_origin") or ""),
                    target_template_id=str(followup.get("target_template_id") or ""),
                )
            await coordinator.proposal_engine.async_accept_proposal(current_id)
            target_id = current_id
            existing_cfg: dict[str, Any] | None = None
            if followup is not None:
                target_id = str(followup["reaction_id"])
                existing_cfg = dict(followup["reaction_cfg"])
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
            self._update_options({OPT_REACTIONS: reactions_cfg})

            if self._proposal_requires_action_completion(current):
                self._pending_action_configs = [target_id]
                self._resume_proposal_review = True
                return await self.async_step_proposal_configure_action()

        elif action == "reject":
            await coordinator.proposal_engine.async_reject_proposal(current_id)
            configured.pop(current_id, None)
            labels.pop(current_id, None)
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._update_options({OPT_REACTIONS: reactions_cfg})

        return await self.async_step_proposals() if queue else await self.async_step_init()

    # ---- Proposal action configuration ----

    async def async_step_proposal_configure_action(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Configure the action(s) to trigger for each accepted proposal, one at a time."""
        pending: list[str] = getattr(self, "_pending_action_configs", [])
        if not pending:
            return await self.async_step_init()

        current_pid = pending[0]
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})
        proposal_description = labels_map.get(current_pid, current_pid)

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

        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        if current_pid in configured:
            cfg = dict(configured[current_pid])
            cfg["steps"] = steps
            cfg["pre_condition_min"] = pre_condition_min
            configured[current_pid] = cfg
            reactions_cfg["configured"] = configured
            self._update_options({OPT_REACTIONS: reactions_cfg})

        # Advance queue
        self._pending_action_configs = pending[1:]
        if self._pending_action_configs:
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

        is_followup = (
            proposal.followup_kind == "tuning_suggestion"
            and bool(_safe_mapping(existing_config))
        )
        if is_followup:
            if proposal.updated_at:
                configured["last_tuned_at"] = proposal.updated_at
            configured["last_tuning_proposal_id"] = proposal.proposal_id
            configured["last_tuning_origin"] = proposal.origin
            configured["last_tuning_followup_kind"] = proposal.followup_kind
            return configured

        origin = proposal.origin
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
            options[template.template_id] = template.title
        return options

    def _admin_authored_template(self, template_id: str) -> Any | None:
        registry = self._learning_plugin_registry()
        if registry is None:
            return None
        return registry.get_admin_authored_template(
            template_id,
            implemented_only=True,
        )

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
        return create_builtin_learning_plugin_registry(
            enabled_families=enabled_families or None
        )

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
        threshold_modes = self._signal_threshold_mode_options()
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
                    vol.Required("primary_signal_entities"): _entity_selector(
                        ["sensor", "binary_sensor"], multiple=True
                    ),
                    vol.Required("primary_signal_name", default="humidity"): str,
                    vol.Required("primary_threshold_mode", default="rise"): vol.In(
                        threshold_modes
                    ),
                    vol.Required("primary_threshold", default=8.0): vol.Coerce(float),
                    vol.Optional("corroboration_signal_entities"): _entity_selector(
                        ["sensor", "binary_sensor"], multiple=True
                    ),
                    vol.Optional("corroboration_signal_name", default="temperature"): str,
                    vol.Optional("corroboration_threshold_mode", default="rise"): vol.In(
                        threshold_modes
                    ),
                    vol.Optional("corroboration_threshold", default=0.8): vol.Coerce(float),
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
        return self._with_suggested(
            vol.Schema(
                {
                    vol.Required("room_id"): vol.In(room_options),
                    vol.Required("primary_signal_entities"): _entity_selector(
                        ["sensor", "binary_sensor"], multiple=True
                    ),
                    vol.Required("primary_signal_name", default="room_lux"): str,
                    vol.Required("primary_threshold", default=120.0): vol.Coerce(float),
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

    def _weekday_options(self) -> dict[str, str]:
        language = self._flow_language()
        return {
            str(index): self._weekday_label(index, language)
            for index in range(7)
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
        fingerprint = (
            f"lighting_scene_schedule|room={room_id}|weekday={weekday}"
            f"|bucket={(scheduled_min // 30) * 30}"
        )
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
        hhmm = f"{scheduled_min // 60:02d}:{scheduled_min % 60:02d}"
        day = self._weekday_label(weekday, "en")
        description = f"{room_id}: {day} ~{hhmm} — {len(entity_steps)} entities"
        return ReactionProposal(
            analyzer_id="AdminAuthoredLightingTemplate",
            reaction_type="lighting_scene_schedule",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=fingerprint,
            fingerprint=fingerprint,
            suggested_reaction_config={
                "reaction_class": "LightingScheduleReaction",
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
        primary_threshold_mode: str,
        primary_threshold: float,
        corroboration_signal_entities: list[str],
        corroboration_signal_name: str,
        corroboration_threshold_mode: str,
        corroboration_threshold: float,
        action_entities: list[str],
    ) -> ReactionProposal:
        template_id = "room.signal_assist.basic"
        identity_key = (
            f"room_signal_assist|room={room_id}|primary={primary_signal_name.strip().lower()}"
        )
        steps = self._action_entities_to_steps(action_entities)
        description = (
            f"{room_id}: when {primary_signal_name.strip().lower()} changes quickly, "
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
                "reaction_class": "RoomSignalAssistReaction",
                "room_id": room_id,
                "trigger_signal_entities": list(primary_signal_entities),
                "primary_signal_entities": list(primary_signal_entities),
                "primary_threshold": float(primary_threshold),
                "primary_threshold_mode": primary_threshold_mode,
                "primary_rise_threshold": float(primary_threshold),
                "primary_signal_name": primary_signal_name.strip() or "primary",
                "temperature_signal_entities": list(corroboration_signal_entities),
                "corroboration_signal_entities": list(corroboration_signal_entities),
                "corroboration_threshold": float(corroboration_threshold),
                "corroboration_threshold_mode": corroboration_threshold_mode,
                "corroboration_rise_threshold": float(corroboration_threshold),
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
        primary_threshold: float,
        entity_ids: list[str],
        action: str,
        brightness: int | None,
        color_temp_kelvin: int | None,
    ) -> ReactionProposal:
        template_id = "room.darkness_lighting_assist.basic"
        identity_key = (
            f"room_darkness_lighting_assist|room={room_id}|primary={primary_signal_name.strip().lower()}"
        )
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
        description = (
            f"{room_id}: when {primary_signal_name.strip().lower()} drops too low, "
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
                "reaction_class": "RoomLightingAssistReaction",
                "room_id": room_id,
                "primary_signal_entities": list(primary_signal_entities),
                "primary_threshold": float(primary_threshold),
                "primary_signal_name": primary_signal_name.strip() or "room_lux",
                "primary_threshold_mode": "below",
                "corroboration_signal_entities": [],
                "corroboration_threshold": None,
                "corroboration_signal_name": "corroboration",
                "corroboration_threshold_mode": "below",
                "correlation_window_s": 600,
                "followup_window_s": 900,
                "entity_steps": entity_steps,
                "plugin_family": "composite_room_assist",
                "admin_authored_template_id": template_id,
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
        reaction_class = str(cfg.get("reaction_class") or "")
        if reaction_class in {"LightingScheduleReaction", "RoomLightingAssistReaction"}:
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
            "summary": self._proposals_step_summary(proposals, current=current, remaining=remaining),
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
        title = self._proposal_human_label(proposal, cfg)
        if self._proposal_followup_target(proposal) is not None:
            language = self._flow_language()
            if language.startswith("it"):
                return f"Affinamento: {title}"
            return f"Tuning: {title}"
        if proposal.origin != "admin_authored":
            return title
        language = self._flow_language()
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
                f"Osservata l'ultima volta: {last_seen}"
                if is_it
                else f"Last seen: {last_seen}"
            )

        room_id = str(cfg.get("room_id") or "").strip()
        if room_id:
            details.append(
                f"Stanza: {room_id}" if is_it else f"Applies to room: {room_id}"
            )
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
            details.extend(
                presenter.learned_review_details(self, proposal, cfg, language)
            )

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
            details.append(
                f"Template: {template_id}"
            )

        details.append(
            f"Stato UX: bozza" if is_it else "UX state: draft"
        )
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
            details.extend(
                presenter.admin_authored_review_details(self, proposal, cfg, language)
            )

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
            return f"Raffrescamento {room_id}" if language.startswith("it") else f"Cooling {room_id}"
        if proposal.reaction_type == "room_air_quality_assist" and room_id:
            return f"Aria {room_id}" if language.startswith("it") else f"Air quality {room_id}"
        if proposal.reaction_type == "heating_preference" and house_state:
            return (
                f"Riscaldamento {house_state}" if language.startswith("it") else f"Heating {house_state}"
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
        return None

    def _configured_reaction_cfg(self, reaction_id: str) -> dict[str, Any] | None:
        configured = dict(self._reactions_options().get("configured", {}))
        raw = configured.get(reaction_id)
        if isinstance(raw, dict):
            return dict(raw)
        return None

    @staticmethod
    def _reaction_presenter_for_cfg(cfg: dict[str, Any]) -> Any | None:
        reaction_class = str(cfg.get("reaction_class") or "").strip()
        if not reaction_class:
            return None
        registry = create_builtin_reaction_plugin_registry()
        return registry.presenter_for(reaction_class)

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
        reaction_class = str(cfg.get("reaction_class") or "").strip()
        presenter = registry.presenter_for(reaction_class)
        if presenter is not None and presenter.reaction_label_from_config is not None:
            presented = presenter.reaction_label_from_config(reaction_id, cfg, labels_map)
            if presented:
                return presented

        if cfg.get("reaction_class") == "PresencePatternReaction":
            try:
                weekday = int(cfg["weekday"])
                median_min = int(cfg["median_arrival_min"])
                window_half = int(cfg.get("window_half_min", 0))
                hhmm = f"{median_min // 60:02d}:{median_min % 60:02d}"
                spread = f" (± {window_half} min)" if window_half > 0 else ""
                day = _WEEKDAY_IT[weekday] if 0 <= weekday <= 6 else str(weekday)
                return f"{day}: arrivo alle {hhmm}{spread}"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        if cfg.get("reaction_class") == "LightingScheduleReaction":
            try:
                weekday = int(cfg["weekday"])
                scheduled_min = int(cfg["scheduled_min"])
                room_id = str(cfg.get("room_id", ""))
                hhmm = f"{scheduled_min // 60:02d}:{scheduled_min % 60:02d}"
                day = _WEEKDAY_IT[weekday] if 0 <= weekday <= 6 else str(weekday)
                n_steps = len(cfg.get("entity_steps", []))
                return f"Luci {room_id} — {day} ~{hhmm} ({n_steps} entità)"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        if cfg.get("reaction_class") == "RoomSignalAssistReaction":
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

        if cfg.get("reaction_class") == "RoomLightingAssistReaction":
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
