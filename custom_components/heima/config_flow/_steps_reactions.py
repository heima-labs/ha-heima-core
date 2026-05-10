"""Options flow: Reactions step (persisted mute management + proposal review)."""

# mypy: ignore-errors

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ..const import DOMAIN, OPT_REACTIONS
from ..runtime.analyzers import create_builtin_learning_plugin_registry
from ..runtime.analyzers.base import ReactionProposal
from ..runtime.reactions import (
    create_builtin_reaction_plugin_registry,
    resolve_reaction_type,
)
from ._reaction_forms import _ReactionFormHelpersMixin
from ._reaction_helpers import (
    format_min_to_hhmm as _format_min_to_hhmm,
)
from ._reaction_helpers import (
    safe_mapping as _safe_mapping,
)
from ._steps_reaction_admin_authored import _ReactionAdminAuthoredStepsMixin
from ._steps_reaction_editing import _ReactionEditingStepsMixin
from ._steps_reaction_proposals import _ReactionProposalStepsMixin

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)
_REDACTED_SENTINEL = "**REDACTED**"


class _ReactionsStepsMixin(
    _ReactionAdminAuthoredStepsMixin,
    _ReactionEditingStepsMixin,
    _ReactionFormHelpersMixin,
    _ReactionProposalStepsMixin,
):
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

    @staticmethod
    def _configured_reaction_slot_key(cfg: dict[str, Any]) -> str:
        """Return a coarse slot key used to avoid duplicate configured reactions."""
        reaction_type = resolve_reaction_type(cfg)
        room_id = str(cfg.get("room_id") or "").strip()
        house_state_filter = str(cfg.get("house_state_filter") or "").strip()
        house_state_suffix = f"|house_state={house_state_filter}" if house_state_filter else ""

        if reaction_type in {
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
        }:
            primary_signal = str(cfg.get("primary_signal_name") or "").strip().lower()
            primary_trigger_mode = str(cfg.get("primary_trigger_mode") or "").strip().lower()
            trigger_mode_suffix = (
                f"|mode={primary_trigger_mode}" if reaction_type == "room_signal_assist" else ""
            )
            return (
                f"{reaction_type}|room={room_id}|primary={primary_signal}"
                f"{trigger_mode_suffix}{house_state_suffix}"
            )

        if reaction_type in {
            "room_darkness_lighting_assist",
            "room_contextual_lighting_assist",
        }:
            primary_signal = str(cfg.get("primary_signal_name") or "").strip().lower()
            return f"{reaction_type}|room={room_id}|primary={primary_signal}{house_state_suffix}"

        if reaction_type == "room_vacancy_lighting_off":
            return f"{reaction_type}|room={room_id}"

        return ""

    def _configured_slot_matches_for_proposal(
        self,
        proposal: ReactionProposal,
        configured: dict[str, Any],
        *,
        exclude_ids: set[str] | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return configured reactions that occupy the same canonical slot."""
        exclude = exclude_ids or set()
        slot_key = self._configured_reaction_slot_key(
            _safe_mapping(proposal.suggested_reaction_config)
        )
        if not slot_key:
            return []

        matches: list[tuple[str, dict[str, Any]]] = []
        for reaction_id, raw in configured.items():
            if reaction_id in exclude:
                continue
            reaction_cfg = _safe_mapping(raw)
            if self._configured_reaction_slot_key(reaction_cfg) != slot_key:
                continue
            matches.append((str(reaction_id), reaction_cfg))
        matches.sort(key=lambda item: item[0])
        return matches

    def _resolve_configured_target_for_proposal(
        self,
        proposal: ReactionProposal,
        configured: dict[str, Any],
    ) -> tuple[ReactionProposal, str, dict[str, Any] | None, list[str]]:
        """Resolve the configured reaction target for a proposal accept/update."""
        accepted_proposal = proposal
        target_id = proposal.proposal_id
        existing_cfg: dict[str, Any] | None = None
        duplicate_ids: list[str] = []

        followup = self._proposal_followup_target(proposal)
        if followup is not None:
            target_id = str(followup["reaction_id"])
            existing_cfg = dict(followup["reaction_cfg"])
            if proposal.followup_kind == "discovery":
                accepted_proposal = replace(
                    proposal,
                    followup_kind="tuning_suggestion",
                    target_reaction_id=target_id,
                    target_reaction_type=self._reaction_type_from_cfg(existing_cfg),
                    target_reaction_origin=str(followup.get("target_reaction_origin") or ""),
                    target_template_id=str(followup.get("target_template_id") or ""),
                )
            return accepted_proposal, target_id, existing_cfg, duplicate_ids

        slot_matches = self._configured_slot_matches_for_proposal(
            proposal,
            configured,
            exclude_ids={proposal.proposal_id},
        )
        if not slot_matches:
            return accepted_proposal, target_id, existing_cfg, duplicate_ids

        target_id, existing_cfg = slot_matches[0]
        duplicate_ids = [reaction_id for reaction_id, _cfg in slot_matches[1:]]
        accepted_proposal = replace(
            proposal,
            followup_kind="tuning_suggestion",
            target_reaction_id=target_id,
            target_reaction_type=self._reaction_type_from_cfg(existing_cfg),
            target_reaction_origin=str(existing_cfg.get("origin") or ""),
            target_template_id=str(existing_cfg.get("source_template_id") or ""),
        )
        return accepted_proposal, target_id, existing_cfg, duplicate_ids

    def _store_reactions_options(self, updates: dict[str, Any]) -> None:
        """Persist reaction options without dropping sibling reaction state."""
        reactions_cfg = dict(self._reactions_options())
        reactions_cfg.update(updates)
        self._update_options({OPT_REACTIONS: reactions_cfg})

    # ---- Helpers ----

    def _reactions_options(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_REACTIONS, {}))

    def _configured_reaction_from_proposal(
        self,
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

        is_improvement = proposal.followup_kind == "improvement" and bool(
            _safe_mapping(existing_config)
        )
        if is_improvement:
            previous = _safe_mapping(existing_config)
            registry = self._learning_plugin_registry()
            if registry is not None:
                return registry.build_improvement_config(
                    proposal,
                    existing_config=previous,
                )

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
        if template_id == "security.vacation_presence_simulation.basic":
            configured = self._reactions_options().get("configured", {})
            has_lighting = any(
                resolve_reaction_type(cfg) == "context_conditioned_lighting_scene"
                for cfg in configured.values()
                if isinstance(cfg, dict)
            )
            if not has_lighting:
                is_it = self._flow_language().startswith("it")
                reason = (
                    "Servono routine luci già accettate per costruire un profilo credibile."
                    if is_it
                    else "Accepted lighting routines are required to build a credible presence profile."
                )
                return False, reason
        return True, ""

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

        if reaction_type in {
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
        }:
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                primary_signal_name = str(cfg.get("primary_signal_name") or "").strip().lower()
                corroboration_signal_name = (
                    str(cfg.get("corroboration_signal_name") or "").strip().lower()
                )
                primary_entities = list(cfg.get("primary_signal_entities") or [])
                corroboration_entities = list(cfg.get("corroboration_signal_entities") or [])
                legacy_trigger_entities = list(cfg.get("trigger_signal_entities") or [])
                legacy_temperature_entities = list(cfg.get("temperature_signal_entities") or [])
                primary_trigger_mode = str(cfg.get("primary_trigger_mode") or "").strip().lower()
                house_state_filter = str(cfg.get("house_state_filter") or "").strip().lower()
                observed = int(cfg.get("episodes_observed", 0))
                if reaction_type == "room_cooling_assist":
                    parts = [f"Raffrescamento {room_id}"]
                elif reaction_type == "room_air_quality_assist":
                    parts = [f"Aria {room_id}"]
                else:
                    parts = [f"Assist {room_id}"]
                if primary_signal_name:
                    signal_bits = [primary_signal_name]
                    if corroboration_signal_name:
                        signal_bits.append(corroboration_signal_name)
                    parts.append(" + ".join(signal_bits))
                elif legacy_trigger_entities or legacy_temperature_entities:
                    if legacy_trigger_entities:
                        parts.append(f"hum:{len(legacy_trigger_entities)}")
                    if legacy_temperature_entities:
                        parts.append(f"temp:{len(legacy_temperature_entities)}")
                elif primary_entities:
                    parts.append(f"sig:{len(primary_entities)}")
                    if corroboration_entities:
                        parts.append(f"corr:{len(corroboration_entities)}")
                if primary_trigger_mode:
                    parts.append(primary_trigger_mode)
                if house_state_filter:
                    parts.append(f"stato:{house_state_filter}")
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

        if reaction_type == "room_contextual_lighting_assist":
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                profiles = dict(cfg.get("profiles") or {})
                rules = list(cfg.get("rules") or [])
                return f"Luce contestuale {room_id} — {len(profiles)} profili — {len(rules)} regole"
            except (TypeError, ValueError):
                pass

        return labels_map.get(reaction_id, reaction_id)
