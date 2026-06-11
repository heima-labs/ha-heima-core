"""Options flow: configured reaction mute/edit/delete steps."""

# mypy: ignore-errors

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..runtime.reactions import validate_contextual_lighting_contract
from ._common import _entity_selector, _number_box_selector
from ._reaction_builders import _lux_on_buckets_from_primary_bucket
from ._reaction_helpers import format_min_to_hhmm as _format_min_to_hhmm

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


def _last_lux_on_bucket(value: Any) -> str:
    buckets = [str(item).strip() for item in list(value or []) if str(item).strip()]
    return buckets[-1] if buckets else ""


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
