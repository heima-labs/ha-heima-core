"""Options flow helpers: build reaction proposals from form submissions."""

# mypy: ignore-errors

from __future__ import annotations

from typing import Any

from ..runtime.analyzers.base import ReactionProposal
from ..runtime.analyzers.reaction_identity import admin_room_signal_assist_identity_key
from ._reaction_helpers import format_min_to_hhmm as _format_min_to_hhmm


class _ReactionBuildersMixin:
    """Mixin for admin-authored reaction proposal builders."""

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
        identity_key = admin_room_signal_assist_identity_key(
            room_id=room_id,
            primary_signal_name=primary_signal_name,
            primary_trigger_mode=primary_trigger_mode,
        )
        steps = self._action_entities_to_steps(action_entities)
        if primary_trigger_mode == "burst":
            trigger_text = f"{primary_signal_name.strip().lower()} bursts"
        else:
            primary_match_mode = primary_bucket_match_mode.strip() or "eq"
            if primary_match_mode == "lte":
                trigger_text = f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or lower"
            elif primary_match_mode == "gte":
                trigger_text = f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or higher"
            else:
                trigger_text = (
                    f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()}"
                )
        if corroboration_signal_entities and corroboration_bucket.strip():
            corroboration_match_mode = corroboration_bucket_match_mode.strip() or "eq"
            if corroboration_match_mode == "lte":
                corroboration_text = f"{corroboration_signal_name.strip().lower()} is {corroboration_bucket.strip()} or lower"
            elif corroboration_match_mode == "gte":
                corroboration_text = f"{corroboration_signal_name.strip().lower()} is {corroboration_bucket.strip()} or higher"
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
                "primary_bucket": primary_bucket.strip()
                if primary_trigger_mode == "bucket"
                else None,
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
            trigger_text = (
                f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or darker"
            )
        elif match_mode == "gte":
            trigger_text = (
                f"{primary_signal_name.strip().lower()} enters {primary_bucket.strip()} or brighter"
            )
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

    def _build_admin_authored_room_contextual_lighting_assist_proposal(
        self,
        *,
        room_id: str,
        primary_signal_name: str,
        primary_signal_entities: list[str],
        primary_bucket: str,
        primary_bucket_match_mode: str,
        contract: dict[str, Any],
    ) -> ReactionProposal:
        template_id = "room.contextual_lighting_assist.basic"
        identity_key = (
            "room_contextual_lighting_assist"
            f"|room={room_id}|primary={primary_signal_name.strip().lower()}"
        )
        profiles = dict(contract.get("profiles") or {})
        rules = list(contract.get("rules") or [])
        default_profile = str(contract.get("default_profile") or "").strip()
        followup_window_s = int(contract.get("followup_window_s", 900))
        ambient_modulation = dict(contract.get("ambient_modulation") or {})
        description = (
            f"{room_id}: contextual lighting ({len(profiles)} profiles, {len(rules)} rules)"
        )
        return ReactionProposal(
            analyzer_id="AdminAuthoredRoomContextualLightingTemplate",
            reaction_type="room_contextual_lighting_assist",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "room_contextual_lighting_assist",
                "room_id": room_id,
                "primary_signal_entities": list(primary_signal_entities),
                "primary_signal_name": primary_signal_name.strip() or "room_lux",
                "primary_bucket": primary_bucket.strip(),
                "primary_bucket_match_mode": primary_bucket_match_mode.strip() or "eq",
                "profiles": profiles,
                "rules": rules,
                "default_profile": default_profile,
                "ambient_modulation": ambient_modulation,
                "followup_window_s": followup_window_s,
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

    def _build_admin_authored_scheduled_routine_proposal(
        self,
        *,
        weekday: int,
        scheduled_min: int,
        routine_kind: str,
        target_entities: list[str],
        entity_action: str,
        house_state_in: list[str],
        skip_if_anyone_home: bool,
    ) -> ReactionProposal:
        template_id = "scheduled_routine.basic"
        identity_key = (
            f"scheduled_routine|weekday={weekday}|scheduled_min={scheduled_min}"
            f"|kind={routine_kind}|targets={','.join(sorted(target_entities))}"
        )
        steps = self._scheduled_routine_targets_to_steps(
            routine_kind=routine_kind,
            target_entities=target_entities,
            entity_action=entity_action,
        )
        description = (
            f"Routine {self._weekday_label(weekday, 'it')} ~{_format_min_to_hhmm(scheduled_min)}"
            f" ({len(target_entities)} target{'s' if len(target_entities) != 1 else ''})"
        )
        return ReactionProposal(
            analyzer_id="AdminAuthoredScheduledRoutineTemplate",
            reaction_type="scheduled_routine",
            description=description,
            confidence=1.0,
            origin="admin_authored",
            identity_key=identity_key,
            fingerprint=identity_key,
            suggested_reaction_config={
                "reaction_type": "scheduled_routine",
                "weekday": weekday,
                "scheduled_min": scheduled_min,
                "window_half_min": 0,
                "routine_kind": routine_kind,
                "target_entities": list(target_entities),
                "entity_action": entity_action,
                "entity_domains": sorted(
                    {entity_id.split(".", 1)[0] for entity_id in list(target_entities)}
                ),
                "house_state_in": list(house_state_in),
                "skip_if_anyone_home": skip_if_anyone_home,
                "steps": steps,
                "plugin_family": "scheduled_routine",
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
    def _scheduled_routine_targets_to_steps(
        *,
        routine_kind: str,
        target_entities: list[str],
        entity_action: str,
    ) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for entity_id in target_entities:
            domain = str(entity_id).split(".", 1)[0]
            if routine_kind == "scene" and domain == "scene":
                action = "scene.turn_on"
            elif routine_kind == "script" and domain == "script":
                action = "script.turn_on"
            elif routine_kind == "entity_action" and domain in {"light", "switch", "input_boolean"}:
                action = f"{domain}.{entity_action}"
            else:
                continue
            steps.append(
                {
                    "domain": domain,
                    "target": entity_id,
                    "action": action,
                    "params": {"entity_id": entity_id},
                }
            )
        return steps

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
