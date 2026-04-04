"""Security-owned vacation presence simulation reaction skeleton."""

from __future__ import annotations

from typing import Any

from .base import HeimaReaction


class VacationPresenceSimulationReaction(HeimaReaction):
    """Skeleton dynamic-policy reaction for vacation presence simulation.

    The first coding slice persists the policy and exposes diagnostics, but the
    derived nightly plan remains a later step.
    """

    def __init__(
        self,
        *,
        reaction_id: str,
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
    ) -> None:
        self._reaction_id = reaction_id
        self._enabled = enabled
        self._allowed_rooms = list(allowed_rooms)
        self._allowed_entities = list(allowed_entities)
        self._requires_dark_outside = requires_dark_outside
        self._simulation_aggressiveness = simulation_aggressiveness
        self._min_jitter_override_min = min_jitter_override_min
        self._max_jitter_override_min = max_jitter_override_min
        self._max_events_per_evening_override = max_events_per_evening_override
        self._latest_end_time_override = latest_end_time_override
        self._skip_if_presence_detected = skip_if_presence_detected

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def diagnostics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "allowed_rooms": list(self._allowed_rooms),
            "allowed_entities": list(self._allowed_entities),
            "requires_dark_outside": self._requires_dark_outside,
            "simulation_aggressiveness": self._simulation_aggressiveness,
            "min_jitter_override_min": self._min_jitter_override_min,
            "max_jitter_override_min": self._max_jitter_override_min,
            "max_events_per_evening_override": self._max_events_per_evening_override,
            "latest_end_time_override": self._latest_end_time_override,
            "skip_if_presence_detected": self._skip_if_presence_detected,
            "active_tonight": False,
            "blocked_reason": "not_implemented_yet",
        }


def build_vacation_presence_simulation_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> VacationPresenceSimulationReaction | None:
    """Build the persisted policy reaction for the security family."""
    try:
        enabled = bool(cfg.get("enabled", True))
        allowed_rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
        allowed_entities = [str(item).strip() for item in cfg.get("allowed_entities", []) or [] if str(item).strip()]
        requires_dark_outside = bool(cfg.get("requires_dark_outside", True))
        simulation_aggressiveness = str(cfg.get("simulation_aggressiveness", "medium") or "medium").strip()
        if simulation_aggressiveness not in {"low", "medium", "high"}:
            simulation_aggressiveness = "medium"
        min_jitter_override_min = _optional_int(cfg.get("min_jitter_override_min"))
        max_jitter_override_min = _optional_int(cfg.get("max_jitter_override_min"))
        max_events_per_evening_override = _optional_int(cfg.get("max_events_per_evening_override"))
        latest_end_time_override = str(cfg.get("latest_end_time_override") or "").strip() or None
        skip_if_presence_detected = bool(cfg.get("skip_if_presence_detected", True))
    except Exception:
        return None
    return VacationPresenceSimulationReaction(
        reaction_id=proposal_id,
        enabled=enabled,
        allowed_rooms=allowed_rooms,
        allowed_entities=allowed_entities,
        requires_dark_outside=requires_dark_outside,
        simulation_aggressiveness=simulation_aggressiveness,
        min_jitter_override_min=min_jitter_override_min,
        max_jitter_override_min=max_jitter_override_min,
        max_events_per_evening_override=max_events_per_evening_override,
        latest_end_time_override=latest_end_time_override,
        skip_if_presence_detected=skip_if_presence_detected,
    )


def present_vacation_presence_simulation_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    scope = ", ".join(str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip())
    if scope:
        return f"Simulazione presenza vacation · {scope}"
    return "Simulazione presenza vacation"


def present_admin_authored_vacation_presence_simulation_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    details = ["Tipo: policy dinamica security-driven"]
    rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
    entities = [str(item).strip() for item in cfg.get("allowed_entities", []) or [] if str(item).strip()]
    if rooms:
        details.append(f"Stanze consentite: {', '.join(rooms)}")
    if entities:
        details.append(f"Entità consentite: {', '.join(entities)}")
    details.append(
        "Profilo di esecuzione: derivato da lighting reactions accettate recenti"
    )
    if bool(cfg.get("requires_dark_outside", True)):
        details.append("Buio richiesto: sì")
    if bool(cfg.get("skip_if_presence_detected", True)):
        details.append("Stop su presenza: sì")
    return details


def present_vacation_presence_simulation_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_admin_authored: bool,
) -> str | None:
    return "Simulazione presenza in vacation"


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
