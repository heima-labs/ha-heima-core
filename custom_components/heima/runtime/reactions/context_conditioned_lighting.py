"""Context-conditioned learned lighting scene reaction."""

from __future__ import annotations

from typing import Any

from ..analyzers.context_conditions import normalize_context_conditions
from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .lighting_schedule import (
    _ScheduledLightingBase,
    present_admin_authored_lighting_schedule_details,
    present_tuning_lighting_schedule_details,
)


class ContextConditionedLightingReaction(_ScheduledLightingBase):
    """Scheduled lighting scene gated by abstract context conditions."""

    def __init__(
        self,
        *,
        room_id: str,
        weekday: int,
        scheduled_min: int,
        window_half_min: int = 10,
        house_state_filter: str | None = None,
        entity_steps: list[dict[str, Any]],
        context_conditions: list[dict[str, Any]],
        reaction_id: str | None = None,
    ) -> None:
        super().__init__(
            room_id=room_id,
            weekday=weekday,
            scheduled_min=scheduled_min,
            window_half_min=window_half_min,
            house_state_filter=house_state_filter,
            entity_steps=entity_steps,
            reaction_id=reaction_id,
        )
        self._context_conditions = normalize_context_conditions(context_conditions)

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not self._context_conditions:
            return []
        if not history:
            return []
        current = history[-1]
        context_signals = dict(current.context_signals or {})
        if not self._matches_context_conditions(context_signals):
            return []
        return super().evaluate(history)

    def diagnostics(self) -> dict[str, Any]:
        base = super().diagnostics()
        base["context_conditions"] = [item.as_dict() for item in self._context_conditions]
        return base

    def _matches_context_conditions(self, context_signals: dict[str, str]) -> bool:
        for condition in self._context_conditions:
            current_state = str(context_signals.get(condition.signal_name) or "").strip().lower()
            if current_state not in condition.state_in:
                return False
        return True


def build_context_conditioned_lighting_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> ContextConditionedLightingReaction | None:
    try:
        room_id = str(cfg["room_id"]).strip()
        weekday = int(cfg["weekday"])
        scheduled_min = int(cfg["scheduled_min"])
        window_half = int(cfg.get("window_half_min", 10))
        house_state_filter = cfg.get("house_state_filter") or None
        entity_steps = list(cfg.get("entity_steps", []))
        context_conditions = list(cfg.get("context_conditions", []))
        if not room_id or not entity_steps or not context_conditions:
            raise ValueError("room_id, entity_steps or context_conditions missing")
    except (KeyError, TypeError, ValueError):
        return None
    return ContextConditionedLightingReaction(
        room_id=room_id,
        weekday=weekday,
        scheduled_min=scheduled_min,
        window_half_min=window_half,
        house_state_filter=house_state_filter,
        entity_steps=entity_steps,
        context_conditions=context_conditions,
        reaction_id=proposal_id,
    )


def present_context_conditioned_lighting_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    conditions = normalize_context_conditions(cfg.get("context_conditions"))
    if not room_id:
        return labels_map.get(reaction_id)
    if conditions:
        bits = [f"{item.signal_name}:{'/'.join(item.state_in)}" for item in conditions]
        return f"Luci {room_id} · contesto {' + '.join(bits)}"
    return f"Luci {room_id} · contesto"


def present_learned_context_conditioned_lighting_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    details = present_admin_authored_lighting_schedule_details(flow, proposal, cfg, language)
    is_it = language.startswith("it")
    conditions = normalize_context_conditions(cfg.get("context_conditions"))
    for condition in conditions:
        state_label = ", ".join(condition.state_in)
        details.append(
            f"Contesto: {condition.signal_name} in [{state_label}]"
            if is_it
            else f"Context: {condition.signal_name} in [{state_label}]"
        )
    diagnostics = dict(cfg.get("learning_diagnostics") or {})
    concentration = diagnostics.get("concentration")
    if isinstance(concentration, (int, float)):
        details.append(
            f"Concentrazione: {float(concentration):.2f}"
            if is_it
            else f"Concentration: {float(concentration):.2f}"
        )
    lift = diagnostics.get("lift")
    if isinstance(lift, (int, float)):
        details.append(f"Lift: {float(lift):.2f}")
    else:
        details.append("Lift: n/d" if is_it else "Lift: n/a")
    negative_episode_count = diagnostics.get("negative_episode_count")
    if isinstance(negative_episode_count, (int, float)):
        details.append(
            f"Episodi negativi: {int(negative_episode_count)}"
            if is_it
            else f"Negative episodes: {int(negative_episode_count)}"
        )
    if "contrast_status" in diagnostics:
        details.append(
            f"Contrasto: {diagnostics.get('contrast_status')}"
            if is_it
            else f"Contrast: {diagnostics.get('contrast_status')}"
        )
    if diagnostics.get("competing_explanation_type"):
        details.append(
            f"Spiegazione prevalente: {diagnostics.get('competing_explanation_type')}"
            if is_it
            else f"Winning explanation: {diagnostics.get('competing_explanation_type')}"
        )
    return details


def present_context_conditioned_lighting_proposal_label(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    if not room_id:
        return None
    conditions = normalize_context_conditions(cfg.get("context_conditions"))
    context_suffix = ""
    if conditions:
        first = conditions[0]
        context_suffix = f" · {first.signal_name}"
    if language.startswith("it"):
        return f"Luci contestuali {room_id}{context_suffix}"
    return f"Contextual lighting {room_id}{context_suffix}"


def present_context_conditioned_lighting_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_followup: bool,
) -> str | None:
    base = present_context_conditioned_lighting_proposal_label(flow, proposal, cfg, language)
    if not base:
        return None
    if language.startswith("it"):
        return f"Nuova automazione luci contestuali: {base}"
    return f"New contextual lighting automation: {base}"


def present_tuning_context_conditioned_lighting_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    details = present_tuning_lighting_schedule_details(flow, proposal, cfg, target_cfg, language)
    is_it = language.startswith("it")
    current = normalize_context_conditions(target_cfg.get("context_conditions"))
    proposed = normalize_context_conditions(cfg.get("context_conditions"))
    if current != proposed:
        details.append(
            f"Contesto: {len(current)} -> {len(proposed)}"
            if is_it
            else f"Context conditions: {len(current)} -> {len(proposed)}"
        )
    return details
