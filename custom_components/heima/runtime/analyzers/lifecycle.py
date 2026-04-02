"""Plugin-owned proposal lifecycle hooks for learning plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import ReactionProposal

LifecycleIdentityKey = Callable[[ReactionProposal], str]
LifecycleFollowupSlotKey = Callable[[ReactionProposal], str]
LifecycleFallbackFollowupMatch = Callable[
    [list[ReactionProposal], ReactionProposal, str],
    tuple[int, ReactionProposal] | None,
]
LifecycleShouldSuppressFollowup = Callable[[ReactionProposal, ReactionProposal], bool]


@dataclass(frozen=True)
class ProposalLifecycleHooks:
    """Lifecycle policy owned by one learning plugin family."""

    identity_key: LifecycleIdentityKey
    followup_slot_key: LifecycleFollowupSlotKey | None = None
    fallback_followup_match: LifecycleFallbackFollowupMatch | None = None
    should_suppress_followup: LifecycleShouldSuppressFollowup | None = None


def presence_lifecycle_hooks() -> ProposalLifecycleHooks:
    return ProposalLifecycleHooks(identity_key=_presence_identity_key)


def heating_lifecycle_hooks() -> ProposalLifecycleHooks:
    return ProposalLifecycleHooks(identity_key=_heating_identity_key)


def lighting_lifecycle_hooks() -> ProposalLifecycleHooks:
    return ProposalLifecycleHooks(
        identity_key=_lighting_identity_key,
        followup_slot_key=_lighting_followup_slot_key,
        fallback_followup_match=_lighting_fallback_followup_match,
        should_suppress_followup=_lighting_should_suppress_followup,
    )


def composite_room_assist_lifecycle_hooks() -> ProposalLifecycleHooks:
    return ProposalLifecycleHooks(identity_key=_composite_room_identity_key)


def _presence_identity_key(proposal: ReactionProposal) -> str:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    return f"presence_preheat|weekday={cfg.get('weekday')}"


def _heating_identity_key(proposal: ReactionProposal) -> str:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    if proposal.reaction_type == "heating_preference":
        return f"heating_preference|house_state={cfg.get('house_state')}"
    if proposal.reaction_type == "heating_eco":
        return "heating_eco"
    return proposal.reaction_type


def _lighting_identity_key(proposal: ReactionProposal) -> str:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    scheduled_min = cfg.get("scheduled_min")
    bucket = None
    if isinstance(scheduled_min, (int, float)):
        bucket = (int(scheduled_min) // 30) * 30
    scene_signature = _lighting_scene_signature(cfg)
    return (
        f"lighting_scene_schedule|room={cfg.get('room_id')}|weekday={cfg.get('weekday')}"
        f"|bucket={bucket}|scene={scene_signature}"
    )


def _lighting_followup_slot_key(proposal: ReactionProposal) -> str:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    scheduled_min = cfg.get("scheduled_min")
    bucket = None
    if isinstance(scheduled_min, (int, float)):
        bucket = (int(scheduled_min) // 30) * 30
    return (
        f"lighting_scene_schedule|room={cfg.get('room_id')}|weekday={cfg.get('weekday')}"
        f"|bucket={bucket}"
    )


def _lighting_fallback_followup_match(
    proposals: list[ReactionProposal],
    candidate: ReactionProposal,
    followup_slot_key: str,
) -> tuple[int, ReactionProposal] | None:
    candidate_cfg = _safe_dict(candidate.suggested_reaction_config)
    candidate_entities = _lighting_entity_actions(candidate_cfg)
    ranked: list[tuple[tuple[int, int, int, str], int, ReactionProposal]] = []
    for idx, current in enumerate(proposals):
        if current.status != "accepted":
            continue
        if _lighting_followup_slot_key(current) != followup_slot_key:
            continue
        current_cfg = _safe_dict(current.suggested_reaction_config)
        current_entities = _lighting_entity_actions(current_cfg)
        overlap = len(candidate_entities & current_entities)
        symmetric_diff = len(candidate_entities ^ current_entities)
        schedule_gap = abs(
            int(candidate_cfg.get("scheduled_min") or 0)
            - int(current_cfg.get("scheduled_min") or 0)
        )
        ranked.append(
            (
                (-overlap, symmetric_diff, schedule_gap, current.proposal_id),
                idx,
                current,
            )
        )

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    _, idx, proposal = ranked[0]
    return idx, proposal


def _lighting_should_suppress_followup(
    candidate: ReactionProposal,
    accepted: ReactionProposal,
) -> bool:
    candidate_cfg = _safe_dict(candidate.suggested_reaction_config)
    accepted_cfg = _safe_dict(accepted.suggested_reaction_config)
    if not candidate_cfg or not accepted_cfg:
        return False

    candidate_steps = _lighting_steps_by_entity(candidate_cfg)
    accepted_steps = _lighting_steps_by_entity(accepted_cfg)
    if set(candidate_steps) != set(accepted_steps):
        return False

    candidate_min = int(candidate_cfg.get("scheduled_min") or 0)
    accepted_min = int(accepted_cfg.get("scheduled_min") or 0)
    if abs(candidate_min - accepted_min) > 5:
        return False

    for entity_id in sorted(candidate_steps):
        current = accepted_steps[entity_id]
        proposed = candidate_steps[entity_id]
        if str(current.get("action") or "") != str(proposed.get("action") or ""):
            return False
        if _numeric_gap(current.get("brightness"), proposed.get("brightness")) > 16:
            return False
        if _numeric_gap(current.get("color_temp_kelvin"), proposed.get("color_temp_kelvin")) > 150:
            return False
        if _normalize_rgb(current.get("rgb_color")) != _normalize_rgb(proposed.get("rgb_color")):
            return False

    return True


def _composite_room_identity_key(proposal: ReactionProposal) -> str:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    return f"{proposal.reaction_type}|room={cfg.get('room_id')}"


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _lighting_scene_signature(cfg: dict[str, Any]) -> str:
    entity_steps = cfg.get("entity_steps")
    if not isinstance(entity_steps, list):
        return "none"

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


def _lighting_steps_by_entity(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entity_steps = cfg.get("entity_steps")
    if not isinstance(entity_steps, list):
        return {}
    by_entity: dict[str, dict[str, Any]] = {}
    for step in entity_steps:
        if not isinstance(step, dict):
            continue
        entity_id = str(step.get("entity_id") or "").strip()
        if entity_id:
            by_entity[entity_id] = dict(step)
    return by_entity


def _numeric_gap(current: Any, proposed: Any) -> int:
    if current in (None, "") and proposed in (None, ""):
        return 0
    if not isinstance(current, (int, float)) or not isinstance(proposed, (int, float)):
        return 10**9
    return abs(int(current) - int(proposed))
