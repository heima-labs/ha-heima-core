"""Options flow: configured reaction mute/edit/delete steps."""

# mypy: ignore-errors

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..coordinator import (
    PROMOTION_ACTION_APPROVE_AUTO_APPLY,
    PROMOTION_ACTION_DISABLE_FUTURE_PROMPTS,
    PROMOTION_ACTION_DISMISS_NOT_NOW,
)
from ..runtime.reactions import validate_contextual_lighting_contract
from ._common import _entity_selector, _number_box_selector
from ._reaction_builders import _lux_on_buckets_from_primary_bucket
from ._reaction_helpers import format_min_to_hhmm as _format_min_to_hhmm

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


def _last_lux_on_bucket(value: Any) -> str:
    buckets = [str(item).strip() for item in list(value or []) if str(item).strip()]
    return buckets[-1] if buckets else ""


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _runtime_promotion_review_summary(
    *,
    reviews: dict[str, dict[str, Any]],
    stats_by_reaction: dict[str, Any],
    review_options: dict[str, str],
    limit: int = 5,
) -> str:
    """Build a compact admin-facing summary for pending runtime promotions."""
    lines: list[str] = []
    for reaction_id, review in list(reviews.items())[:limit]:
        stats = stats_by_reaction.get(reaction_id, {})
        stats = dict(stats) if isinstance(stats, dict) else {}
        approved = _safe_int(stats.get("approved"))
        dismissed = _safe_int(stats.get("dismissed"))
        explicit_total = approved + dismissed
        approval_rate = round((approved / explicit_total) * 100) if explicit_total else 0
        requested = _safe_int(stats.get("requested"))
        timeout_applied = _safe_int(stats.get("timeout_applied"))
        timeout_skipped = _safe_int(stats.get("timeout_skipped"))
        failed = _safe_int(stats.get("failed"))
        review_bits = [
            f"explicit yes/no {approved}/{dismissed}",
            f"approval rate {approval_rate}%",
            f"requests {requested}",
        ]
        if timeout_applied or timeout_skipped:
            review_bits.append(f"timeouts apply/skip {timeout_applied}/{timeout_skipped}")
        if failed:
            review_bits.append(f"failed {failed}")
        if review.get("reminder_due") is True:
            review_bits.append("reminder due")
        elif review.get("next_reminder_after"):
            review_bits.append(f"next reminder after {review['next_reminder_after']}")
        label = review_options.get(reaction_id, reaction_id)
        lines.append(f"{label}: " + "; ".join(review_bits))

    remaining = max(0, len(reviews) - limit)
    if remaining:
        lines.append(f"...and {remaining} more pending review(s).")
    return "\n".join(lines)


class _ReactionEditingStepsMixin:
    """Mixin for configured reaction mute, edit, and delete flows."""

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

    async def async_step_runtime_promotion_reviews(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Review pending resident-confirmation promotion decisions."""
        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels_map: dict[str, str] = reactions_cfg.get("labels", {})
        reviews = {
            reaction_id: dict(review)
            for reaction_id, review in dict(reactions_cfg.get("promotion_reviews", {})).items()
            if isinstance(review, dict)
            and str(review.get("status") or "") == "pending_admin_review"
            and reaction_id in configured
        }
        if not reviews:
            return await self.async_step_init()

        review_options = {
            reaction_id: self._reaction_label_from_config(
                reaction_id,
                dict(configured.get(reaction_id, {})),
                labels_map,
            )
            for reaction_id in reviews
        }
        action_options = {
            PROMOTION_ACTION_APPROVE_AUTO_APPLY: "Yes, make it automatic",
            PROMOTION_ACTION_DISMISS_NOT_NOW: "No, not now",
            PROMOTION_ACTION_DISABLE_FUTURE_PROMPTS: "Do not ask again",
        }
        stats_by_reaction = dict(reactions_cfg.get("confirmation_stats", {}))
        description_placeholders = {
            "pending_count": str(len(reviews)),
            "review_summary": _runtime_promotion_review_summary(
                reviews=reviews,
                stats_by_reaction=stats_by_reaction,
                review_options=review_options,
            ),
        }
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("reaction"): vol.In(review_options),
                    vol.Required("action"): vol.In(action_options),
                }
            )
            return self.async_show_form(
                step_id="runtime_promotion_reviews",
                data_schema=schema,
                description_placeholders=description_placeholders,
            )

        reaction_id = str(user_input.get("reaction") or "").strip()
        action = str(user_input.get("action") or "").strip()
        coordinator = self._get_coordinator()
        reviewer = getattr(coordinator, "async_review_runtime_promotion", None)
        if reaction_id not in reviews or action not in action_options or not callable(reviewer):
            return self.async_show_form(
                step_id="runtime_promotion_reviews",
                data_schema=vol.Schema(
                    {
                        vol.Required("reaction"): vol.In(review_options),
                        vol.Required("action"): vol.In(action_options),
                    }
                ),
                errors={"base": "invalid_selection"},
                description_placeholders=description_placeholders,
            )
        accepted = await reviewer(reaction_id, action)
        if not accepted:
            return self.async_show_form(
                step_id="runtime_promotion_reviews",
                data_schema=vol.Schema(
                    {
                        vol.Required("reaction"): vol.In(review_options),
                        vol.Required("action"): vol.In(action_options),
                    }
                ),
                errors={"base": "promotion_review_not_available"},
                description_placeholders=description_placeholders,
            )
        return await self.async_step_init()

    async def async_step_runtime_confirmation_maintenance(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Reset runtime confirmation stats and promotion cooldown state."""
        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels_map: dict[str, str] = reactions_cfg.get("labels", {})
        stats_by_reaction = dict(reactions_cfg.get("confirmation_stats", {}))
        reviews = dict(reactions_cfg.get("promotion_reviews", {}))
        reaction_ids = sorted(
            {
                str(reaction_id)
                for reaction_id in [*stats_by_reaction.keys(), *reviews.keys()]
                if str(reaction_id).strip()
            }
        )
        if not reaction_ids:
            return await self.async_step_init()

        reaction_options = {
            reaction_id: self._reaction_label_from_config(
                reaction_id,
                dict(configured.get(reaction_id, {})),
                labels_map,
            )
            for reaction_id in reaction_ids
        }
        description_placeholders = {
            "reaction_count": str(len(reaction_options)),
        }
        schema = vol.Schema(
            {
                vol.Required("reaction"): vol.In(reaction_options),
                vol.Required("confirm_reset", default=False): bool,
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="runtime_confirmation_maintenance",
                data_schema=schema,
                description_placeholders=description_placeholders,
            )

        reaction_id = str(user_input.get("reaction") or "").strip()
        if reaction_id not in reaction_options:
            return self.async_show_form(
                step_id="runtime_confirmation_maintenance",
                data_schema=schema,
                errors={"base": "invalid_selection"},
                description_placeholders=description_placeholders,
            )
        if not bool(user_input.get("confirm_reset", False)):
            return await self.async_step_init()

        coordinator = self._get_coordinator()
        resetter = getattr(
            coordinator,
            "async_reset_runtime_confirmation_promotion_state",
            None,
        )
        if not callable(resetter):
            return self.async_show_form(
                step_id="runtime_confirmation_maintenance",
                data_schema=schema,
                errors={"base": "runtime_state_not_available"},
                description_placeholders=description_placeholders,
            )
        accepted = await resetter(reaction_id)
        if not accepted:
            return self.async_show_form(
                step_id="runtime_confirmation_maintenance",
                data_schema=schema,
                errors={"base": "runtime_state_not_available"},
                description_placeholders=description_placeholders,
            )
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
        if not cfg:
            self._editing_reaction_id = None
            return await self.async_step_init()
        reaction_type = self._reaction_type_from_cfg(cfg)

        if reaction_type == "room_smart_lighting_assist":
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

        if reaction_type == "room_cooling_assist":
            return await self._async_step_reactions_edit_room_signal_assist(
                pid=pid,
                reactions_cfg=reactions_cfg,
                configured=configured,
                labels_map=labels_map,
                cfg=cfg,
                user_input=user_input,
            )

        if reaction_type == "room_vacancy_lighting_off":
            return await self._async_step_reactions_edit_room_vacancy_lighting_off(
                pid=pid,
                reactions_cfg=reactions_cfg,
                configured=configured,
                labels_map=labels_map,
                cfg=cfg,
                user_input=user_input,
            )

        if reaction_type == "context_conditioned_lighting_scene":
            return await self._async_step_reactions_edit_context_conditioned_lighting_scene(
                pid=pid,
                reactions_cfg=reactions_cfg,
                configured=configured,
                labels_map=labels_map,
                cfg=cfg,
                user_input=user_input,
            )

        if reaction_type == "scheduled_routine":
            return await self._async_step_reactions_edit_scheduled_routine(
                pid=pid,
                reactions_cfg=reactions_cfg,
                configured=configured,
                labels_map=labels_map,
                cfg=cfg,
                user_input=user_input,
            )

        if reaction_type == "vacation_presence_simulation":
            return await self._async_step_reactions_edit_vacation_presence_simulation(
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
                    vol.Optional("pre_condition_min", default=current_pre): _number_box_selector(
                        min_value=1, max_value=120, step=1
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

    async def _async_step_reactions_edit_room_vacancy_lighting_off(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit a vacancy lights-off reaction using its real config contract."""
        room_id = str(cfg.get("room_id") or "").strip()
        current_steps = [
            step for step in list(cfg.get("entity_steps", [])) if isinstance(step, dict)
        ]
        current_entities = [
            str(step.get("entity_id") or "").strip()
            for step in current_steps
            if str(step.get("entity_id") or "").strip()
        ]
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "light_entities": current_entities,
            "vacancy_delay_min": max(1, int(cfg.get("vacancy_delay_s") or 0) // 60),
            "delete_reaction": False,
        }
        label = self._reaction_label_from_config(pid, cfg, labels_map)
        room_id_placeholder = room_id or "-"

        if user_input is None:
            return self._show_room_vacancy_lighting_off_editor(
                step_id="reactions_edit_form",
                defaults=defaults,
                reaction_description=label,
                room_id=room_id_placeholder,
                include_enabled=True,
                include_delete=True,
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        current_input, resolved, errors = (
            self._normalize_room_vacancy_lighting_off_editor_submission(
                user_input=user_input,
                defaults=defaults,
                room_id=room_id,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
            )
        )
        if errors:
            return self._show_room_vacancy_lighting_off_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors=errors,
                reaction_description=label,
                room_id=room_id_placeholder,
                include_enabled=True,
                include_delete=True,
            )

        cfg["enabled"] = bool(resolved["enabled"])
        cfg["vacancy_delay_s"] = int(resolved["vacancy_delay_min"]) * 60
        cfg["entity_steps"] = [
            {"entity_id": entity_id, "action": "off", "brightness": None, "color_temp_kelvin": None}
            for entity_id in list(resolved["light_entities"])
        ]
        if self._has_redacted_payload(cfg):
            return self._show_room_vacancy_lighting_off_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                reaction_description=label,
                room_id=room_id_placeholder,
                include_enabled=True,
                include_delete=True,
            )

        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def _async_step_reactions_edit_vacation_presence_simulation(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit a vacation presence simulation policy using its real contract."""
        label = self._reaction_label_from_config(pid, cfg, labels_map)
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "allowed_rooms": list(cfg.get("allowed_rooms", [])),
            "allowed_entities": list(cfg.get("allowed_entities", [])),
            "requires_dark_outside": bool(cfg.get("requires_dark_outside", True)),
            "simulation_aggressiveness": str(
                cfg.get("simulation_aggressiveness", "medium") or "medium"
            ),
            "min_jitter_override_min": cfg.get("min_jitter_override_min"),
            "max_jitter_override_min": cfg.get("max_jitter_override_min"),
            "max_events_per_evening_override": cfg.get("max_events_per_evening_override"),
            "latest_end_time_override": str(cfg.get("latest_end_time_override", "") or ""),
            "skip_if_presence_detected": bool(cfg.get("skip_if_presence_detected", True)),
            "delete_reaction": False,
        }

        if user_input is None:
            return self._show_vacation_presence_simulation_editor(
                step_id="reactions_edit_form",
                defaults=defaults,
                reaction_description=label,
                include_delete=True,
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        current_input, resolved, errors = self._normalize_security_presence_simulation_submission(
            user_input=user_input,
            defaults=defaults,
            include_delete=True,
        )
        if errors:
            return self._show_vacation_presence_simulation_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors=errors,
                reaction_description=label,
                include_delete=True,
            )

        cfg["enabled"] = bool(resolved["enabled"])
        cfg["allowed_rooms"] = list(resolved["allowed_rooms"])
        cfg["allowed_entities"] = list(resolved["allowed_entities"])
        cfg["requires_dark_outside"] = bool(resolved["requires_dark_outside"])
        cfg["simulation_aggressiveness"] = str(resolved["simulation_aggressiveness"])
        cfg["min_jitter_override_min"] = resolved["min_jitter_override_min"]
        cfg["max_jitter_override_min"] = resolved["max_jitter_override_min"]
        cfg["max_events_per_evening_override"] = resolved["max_events_per_evening_override"]
        cfg["latest_end_time_override"] = resolved["latest_end_time_override"]
        cfg["skip_if_presence_detected"] = bool(resolved["skip_if_presence_detected"])
        if self._has_redacted_payload(cfg):
            return self._show_vacation_presence_simulation_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                reaction_description=label,
                include_delete=True,
            )

        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def _async_step_reactions_edit_scheduled_routine(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit a scheduled routine using its real contract."""
        steps = list(cfg.get("steps") or [])
        target_entities = [
            str(step.get("target") or "").strip()
            for step in steps
            if isinstance(step, dict) and str(step.get("target") or "").strip()
        ]
        routine_kind = str(cfg.get("routine_kind") or "").strip()
        if not routine_kind and target_entities:
            domains = {
                entity_id.split(".", 1)[0] for entity_id in target_entities if "." in entity_id
            }
            if domains == {"scene"}:
                routine_kind = "scene"
            elif domains == {"script"}:
                routine_kind = "script"
            else:
                routine_kind = "entity_action"
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "weekday": str(cfg.get("weekday", 0)),
            "scheduled_time": _format_min_to_hhmm(int(cfg.get("scheduled_min", 0))),
            "routine_kind": routine_kind or "scene",
            "target_entities": target_entities,
            "entity_action": str(cfg.get("entity_action") or "turn_on"),
            "house_state_in": list(cfg.get("house_state_in") or []),
            "skip_if_anyone_home": bool(cfg.get("skip_if_anyone_home", False)),
            "delete_reaction": False,
        }
        label = self._reaction_label_from_config(pid, cfg, labels_map)

        if user_input is None:
            return self._show_scheduled_routine_editor(
                step_id="reactions_edit_form",
                defaults=defaults,
                reaction_description=label,
                include_enabled=True,
                include_delete=True,
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        current_input, resolved, errors = self._normalize_scheduled_routine_submission(
            user_input=user_input,
            defaults=defaults,
            include_enabled=True,
            include_delete=True,
        )
        if errors:
            return self._show_scheduled_routine_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors=errors,
                reaction_description=label,
                include_enabled=True,
                include_delete=True,
            )

        cfg["enabled"] = bool(resolved["enabled"])
        cfg["weekday"] = int(resolved["weekday"])
        cfg["scheduled_min"] = int(resolved["scheduled_min"])
        cfg["window_half_min"] = int(cfg.get("window_half_min", 0) or 0)
        cfg["routine_kind"] = str(resolved["routine_kind"])
        cfg["target_entities"] = list(resolved["target_entities"])
        cfg["entity_action"] = str(resolved["entity_action"])
        cfg["entity_domains"] = sorted(
            {entity_id.split(".", 1)[0] for entity_id in list(resolved["target_entities"])}
        )
        cfg["house_state_in"] = list(resolved["house_state_in"])
        cfg["skip_if_anyone_home"] = bool(resolved["skip_if_anyone_home"])
        cfg["steps"] = self._scheduled_routine_targets_to_steps(
            routine_kind=str(resolved["routine_kind"]),
            target_entities=list(resolved["target_entities"]),
            entity_action=str(resolved["entity_action"]),
        )
        if self._has_redacted_payload(cfg):
            return self._show_scheduled_routine_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                reaction_description=label,
                include_enabled=True,
                include_delete=True,
            )

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
        """Edit a room smart lighting assist reaction using its real config contract."""
        room_id = str(cfg.get("room_id") or "").strip()
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
            "primary_signal_name": str(
                cfg.get("indoor_lux_signal") or cfg.get("primary_signal_name") or "room_lux"
            ).strip(),
            "primary_bucket": str(
                cfg.get("primary_bucket")
                or (_last_lux_on_bucket(cfg.get("lux_on_buckets")) or "dim")
            ).strip()
            or "dim",
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

        if user_input is None:
            return self._show_room_darkness_lighting_editor(
                step_id="reactions_edit_form",
                defaults=defaults,
                reaction_description=label,
                room_id=room_id_placeholder,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        current_input, resolved, errors = self._normalize_room_darkness_lighting_editor_submission(
            user_input=user_input,
            defaults=defaults,
            room_id=room_id,
            include_room_id=False,
            include_enabled=True,
            include_delete=True,
        )

        if errors:
            return self._show_room_darkness_lighting_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors=errors,
                reaction_description=label,
                room_id=room_id_placeholder,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
            )

        cfg["enabled"] = bool(resolved["enabled"])
        cfg["reaction_type"] = "room_smart_lighting_assist"
        cfg["primary_signal_entities"] = list(resolved["primary_signal_entities"])
        cfg["primary_signal_name"] = str(resolved["primary_signal_name"])
        cfg["indoor_lux_signal"] = str(resolved["primary_signal_name"])
        cfg["lux_on_buckets"] = _lux_on_buckets_from_primary_bucket(str(resolved["primary_bucket"]))
        cfg.setdefault("room_type", "generic")
        cfg.setdefault("suppress_on_states", ["away", "vacation"])
        cfg.setdefault("night_mode_states", ["sleeping"])
        cfg.setdefault("timeout_mode", "learned")
        cfg["primary_bucket"] = str(resolved["primary_bucket"])
        cfg["primary_bucket_match_mode"] = str(resolved["primary_bucket_match_mode"])
        cfg.pop("primary_threshold", None)
        cfg.pop("primary_threshold_mode", None)
        cfg["entity_steps"] = [
            {
                "entity_id": entity_id,
                "action": str(resolved["action"]),
                "brightness": (resolved["brightness"] if str(resolved["action"]) == "on" else None),
                "color_temp_kelvin": (
                    resolved["color_temp_kelvin"] if str(resolved["action"]) == "on" else None
                ),
                "rgb_color": None,
            }
            for entity_id in list(resolved["light_entities"])
        ]
        if self._has_redacted_payload(cfg):
            return self._show_room_darkness_lighting_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                reaction_description=label,
                room_id=room_id_placeholder,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
            )
        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def _async_step_reactions_edit_context_conditioned_lighting_scene(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit runtime execution policy for a contextual learned lighting scene."""
        label = self._reaction_label_from_config(pid, cfg, labels_map)
        defaults = self._runtime_confirmation_defaults_from_cfg(cfg)

        if user_input is None:
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._runtime_confirmation_editor_schema(
                    defaults,
                    include_delete=True,
                ),
                description_placeholders={"reaction_description": label},
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        current_input, execution_policy, errors = self._normalize_runtime_confirmation_submission(
            user_input=user_input,
            defaults=defaults,
        )
        if errors:
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self._runtime_confirmation_editor_schema(
                    current_input,
                    include_delete=True,
                ),
                errors=errors,
                description_placeholders={"reaction_description": label},
            )

        existing_policy = cfg.get("execution_policy")
        existing_policy = dict(existing_policy) if isinstance(existing_policy, dict) else {}
        reset_promotion_state = self._runtime_confirmation_edit_resets_promotion_state(
            existing_policy=existing_policy,
            submitted_policy=execution_policy,
        )

        cfg["enabled"] = bool(current_input.get("enabled", True))
        cfg["execution_policy"] = self._merge_runtime_confirmation_execution_policy(
            existing_policy=existing_policy,
            submitted_policy=execution_policy,
        )
        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        if reset_promotion_state:
            stats_by_reaction = dict(reactions_cfg.get("confirmation_stats", {}))
            reviews = dict(reactions_cfg.get("promotion_reviews", {}))
            stats_by_reaction.pop(pid, None)
            reviews.pop(pid, None)
            reactions_cfg["confirmation_stats"] = stats_by_reaction
            reactions_cfg["promotion_reviews"] = reviews
        self._store_reactions_options(reactions_cfg)
        self._editing_reaction_id = None
        return await self.async_step_init()

    async def _async_step_reactions_edit_room_contextual_lighting_assist(
        self,
        *,
        pid: str,
        reactions_cfg: dict[str, Any],
        configured: dict[str, Any],
        labels_map: dict[str, str],
        cfg: dict[str, Any],
        user_input: dict[str, Any] | None,
    ) -> "FlowResult":
        """Edit a contextual lighting assist using the guided JSON contract."""
        room_id = str(cfg.get("room_id") or "").strip() or "-"
        label = self._reaction_label_from_config(pid, cfg, labels_map)
        light_entities = self._contextual_lighting_light_entities_from_cfg(cfg)
        preset = self._contextual_lighting_preset_from_cfg(cfg)
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "preset": preset,
            "config_json": self._contextual_lighting_policy_for_form(cfg),
            "delete_reaction": False,
        }

        if user_input is None:
            return self._show_contextual_lighting_policy_editor(
                step_id="reactions_edit_form",
                defaults=defaults,
                reaction_description=label,
                room_id=room_id,
                include_enabled=True,
                include_delete=True,
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        normalized_preset, config_json = self._normalize_contextual_policy_editor_submission(
            user_input=user_input,
            defaults=defaults,
            light_entities=light_entities,
            allow_custom_preset=True,
        )
        try:
            contract = json.loads(config_json)
            if not isinstance(contract, dict):
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._show_contextual_lighting_policy_editor(
                step_id="reactions_edit_form",
                defaults={
                    "enabled": bool(user_input.get("enabled", defaults["enabled"])),
                    "preset": normalized_preset,
                    "config_json": config_json,
                    "delete_reaction": False,
                },
                reaction_description=label,
                room_id=room_id,
                errors={"config_json": "invalid_json"},
                include_enabled=True,
                include_delete=True,
            )

        if not validate_contextual_lighting_contract(contract):
            return self._show_contextual_lighting_policy_editor(
                step_id="reactions_edit_form",
                defaults={
                    "enabled": bool(user_input.get("enabled", defaults["enabled"])),
                    "preset": normalized_preset,
                    "config_json": config_json,
                    "delete_reaction": False,
                },
                reaction_description=label,
                room_id=room_id,
                errors={"config_json": "invalid_contextual_contract"},
                include_enabled=True,
                include_delete=True,
            )

        cfg["enabled"] = bool(user_input.get("enabled", True))
        cfg["profiles"] = dict(contract.get("profiles") or {})
        cfg["rules"] = list(contract.get("rules") or [])
        cfg["default_profile"] = str(contract.get("default_profile") or "").strip()
        if contract.get("ambient_modulation") not in (None, {}):
            cfg["ambient_modulation"] = dict(contract.get("ambient_modulation") or {})
        else:
            cfg.pop("ambient_modulation", None)
        cfg["followup_window_s"] = int(
            contract.get("followup_window_s", cfg.get("followup_window_s", 900))
        )
        if self._has_redacted_payload(cfg):
            return self._show_contextual_lighting_policy_editor(
                step_id="reactions_edit_form",
                defaults={
                    "enabled": bool(user_input.get("enabled", defaults["enabled"])),
                    "preset": normalized_preset,
                    "config_json": config_json,
                    "delete_reaction": False,
                },
                reaction_description=label,
                room_id=room_id,
                errors={"base": "redacted_payload"},
                include_enabled=True,
                include_delete=True,
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
        current_steps = list(cfg.get("steps", []))
        current_entities = [
            str(s.get("target") or "").strip()
            for s in current_steps
            if isinstance(s, dict) and str(s.get("target") or "").strip()
        ]
        defaults = {
            "enabled": bool(cfg.get("enabled", True)),
            "primary_signal_name": str(cfg.get("primary_signal_name") or "").strip(),
            "primary_trigger_mode": str(cfg.get("primary_trigger_mode") or "bucket").strip()
            or "bucket",
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

        if user_input is None:
            return self._show_room_signal_assist_editor(
                step_id="reactions_edit_form",
                defaults=defaults,
                reaction_description=label,
                room_id=room_id_placeholder,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
            )

        if bool(user_input.get("delete_reaction", False)):
            self._deleting_reaction_id = pid
            return await self.async_step_reactions_delete_confirm()

        current_input, resolved, errors = self._normalize_room_signal_assist_editor_submission(
            user_input=user_input,
            defaults=defaults,
            room_id=room_id,
            include_room_id=False,
            include_enabled=True,
            include_delete=True,
        )

        if errors:
            return self._show_room_signal_assist_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors=errors,
                reaction_description=label,
                room_id=room_id_placeholder,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
            )

        cfg["enabled"] = bool(resolved["enabled"])
        cfg["primary_signal_name"] = str(resolved["primary_signal_name"])
        cfg["primary_trigger_mode"] = str(resolved["primary_trigger_mode"])
        cfg["primary_bucket"] = (
            str(resolved["primary_bucket"])
            if str(resolved["primary_trigger_mode"]) == "bucket"
            else None
        )
        cfg["primary_bucket_match_mode"] = str(resolved["primary_bucket_match_mode"])
        cfg["primary_signal_entities"] = list(resolved["primary_signal_entities"])
        cfg["trigger_signal_entities"] = list(resolved["primary_signal_entities"])
        cfg["corroboration_signal_name"] = str(resolved["corroboration_signal_name"])
        cfg["corroboration_bucket"] = str(resolved["corroboration_bucket"]) or None
        cfg["corroboration_bucket_match_mode"] = str(resolved["corroboration_bucket_match_mode"])
        cfg["corroboration_signal_entities"] = list(resolved["corroboration_signal_entities"])
        cfg["temperature_signal_entities"] = list(resolved["corroboration_signal_entities"])
        cfg["steps"] = self._action_entities_to_steps(list(resolved["action_entities"]))
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
            return self._show_room_signal_assist_editor(
                step_id="reactions_edit_form",
                defaults=current_input,
                errors={"base": "redacted_payload"},
                reaction_description=label,
                room_id=room_id_placeholder,
                include_room_id=False,
                include_enabled=True,
                include_delete=True,
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

    def _runtime_confirmation_defaults_from_cfg(self, cfg: dict[str, Any]) -> dict[str, Any]:
        policy = cfg.get("execution_policy")
        policy = dict(policy) if isinstance(policy, dict) else {}
        confirmation = policy.get("confirmation")
        confirmation = dict(confirmation) if isinstance(confirmation, dict) else {}
        return {
            "enabled": bool(cfg.get("enabled", True)),
            "execution_mode": str(policy.get("mode") or "auto_apply"),
            "confirmation_expires_in_minutes": int(confirmation.get("expires_in_minutes") or 10),
            "confirmation_on_timeout": str(confirmation.get("on_timeout") or "skip"),
            "confirmation_target_recipients": ", ".join(
                self._runtime_confirmation_string_list(confirmation.get("target_recipients"))
            ),
            "confirmation_target_groups": ", ".join(
                self._runtime_confirmation_string_list(confirmation.get("target_groups"))
            ),
            "confirmation_use_default_route_targets": bool(
                confirmation.get("use_default_route_targets", True)
            ),
            "delete_reaction": False,
        }

    def _normalize_runtime_confirmation_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        errors: dict[str, str] = {}
        mode = str(user_input.get("execution_mode") or defaults.get("execution_mode") or "").strip()
        if mode not in self._runtime_confirmation_mode_options():
            errors["execution_mode"] = "invalid_option"
            mode = str(defaults.get("execution_mode") or "auto_apply")

        on_timeout = str(
            user_input.get("confirmation_on_timeout")
            or defaults.get("confirmation_on_timeout")
            or ""
        ).strip()
        if on_timeout not in self._runtime_confirmation_timeout_options():
            errors["confirmation_on_timeout"] = "invalid_option"
            on_timeout = str(defaults.get("confirmation_on_timeout") or "skip")

        try:
            expires_in = int(
                user_input.get("confirmation_expires_in_minutes")
                or defaults.get("confirmation_expires_in_minutes")
                or 10
            )
            if expires_in < 1 or expires_in > 240:
                raise ValueError
        except (TypeError, ValueError):
            errors["confirmation_expires_in_minutes"] = "invalid_number"
            expires_in = int(defaults.get("confirmation_expires_in_minutes") or 10)

        target_recipients = self._runtime_confirmation_string_list(
            user_input.get("confirmation_target_recipients", "")
        )
        target_groups = self._runtime_confirmation_string_list(
            user_input.get("confirmation_target_groups", "")
        )
        use_default_route_targets = bool(
            user_input.get(
                "confirmation_use_default_route_targets",
                defaults.get("confirmation_use_default_route_targets", True),
            )
        )

        current_input = {
            "enabled": bool(user_input.get("enabled", defaults.get("enabled", True))),
            "execution_mode": mode,
            "confirmation_expires_in_minutes": expires_in,
            "confirmation_on_timeout": on_timeout,
            "confirmation_target_recipients": ", ".join(target_recipients),
            "confirmation_target_groups": ", ".join(target_groups),
            "confirmation_use_default_route_targets": use_default_route_targets,
            "delete_reaction": False,
        }
        execution_policy = {
            "mode": mode,
            "confirmation": {
                "expires_in_minutes": expires_in,
                "on_timeout": on_timeout,
                "target_recipients": target_recipients,
                "target_groups": target_groups,
                "use_default_route_targets": use_default_route_targets,
            },
        }
        return current_input, execution_policy, errors

    @staticmethod
    def _merge_runtime_confirmation_execution_policy(
        *,
        existing_policy: dict[str, Any],
        submitted_policy: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve promotion settings while applying runtime confirmation edits."""
        merged = dict(submitted_policy)
        existing_promotion = existing_policy.get("promotion")
        if isinstance(existing_promotion, dict):
            merged["promotion"] = dict(existing_promotion)
        if str(merged.get("mode") or "") == "auto_apply":
            for key in ("promoted_from_confirmation", "promoted_at"):
                if key in existing_policy:
                    merged[key] = existing_policy[key]
        return merged

    @staticmethod
    def _runtime_confirmation_edit_resets_promotion_state(
        *,
        existing_policy: dict[str, Any],
        submitted_policy: dict[str, Any],
    ) -> bool:
        """Return whether an admin edit invalidates old promotion evidence."""
        return (
            str(existing_policy.get("mode") or "") == "auto_apply"
            and bool(existing_policy.get("promoted_from_confirmation"))
            and str(submitted_policy.get("mode") or "") == "ask_residents"
        )

    @staticmethod
    def _runtime_confirmation_string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            raw_items = value.replace("\n", ",").split(",")
        elif isinstance(value, list | tuple | set):
            raw_items = list(value)
        else:
            raw_items = []
        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result
