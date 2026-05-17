"""Alarm-state-driven admin-authored action reaction."""

from __future__ import annotations

from typing import Any

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction

VALID_ALARM_STATES = {
    "armed_away",
    "armed_home",
    "armed_night",
    "triggered",
    "disarmed",
}
_SUPPORTED_STEP_ACTIONS = {
    "light": {"light.turn_on", "light.turn_off"},
    "switch": {"switch.turn_on", "switch.turn_off"},
    "input_boolean": {"input_boolean.turn_on", "input_boolean.turn_off"},
    "scene": {"scene.turn_on"},
    "script": {"script.turn_on"},
    "climate": {"climate.set_hvac_mode", "climate.set_preset_mode"},
}


class AlarmStateActionReaction(HeimaReaction):
    """Run configured steps once when the alarm enters a configured state."""

    def __init__(
        self,
        *,
        alarm_states: list[str],
        steps: list[dict[str, Any]],
        reaction_id: str | None = None,
    ) -> None:
        self._alarm_states = _normalize_alarm_states(alarm_states)
        self._steps = _normalize_steps(steps)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._last_fired_state: str | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history or not self._alarm_states or not self._steps:
            return []
        security_state = str(getattr(history[-1], "security_state", "") or "").strip()
        if security_state not in self._alarm_states:
            self._last_fired_state = None
            return []
        if security_state == self._last_fired_state:
            return []
        self._last_fired_state = security_state
        return self._build_steps(security_state)

    def reset_learning_state(self) -> None:
        self._last_fired_state = None

    def diagnostics(self) -> dict[str, Any]:
        return {
            "alarm_states": list(self._alarm_states),
            "steps": len(self._steps),
            "last_fired_state": self._last_fired_state,
        }

    def _build_steps(self, security_state: str) -> list[ApplyStep]:
        return [
            ApplyStep(
                domain=str(step["domain"]),
                target=str(step["target"]),
                action=str(step["action"]),
                params=dict(step["params"]),
                reason=f"alarm_state_action:{self._reaction_id}:{security_state}",
            )
            for step in self._steps
        ]


def normalize_alarm_state_action_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted alarm-state-action config to the canonical contract."""
    return {
        "reaction_type": "alarm_state_action",
        "alarm_states": _normalize_alarm_states(cfg.get("alarm_states")),
        "steps": _normalize_steps(cfg.get("steps")),
    }


def build_alarm_state_action_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> AlarmStateActionReaction | None:
    del engine
    normalized = normalize_alarm_state_action_config(cfg)
    alarm_states = list(normalized.get("alarm_states") or [])
    steps = list(normalized.get("steps") or [])
    if not alarm_states or not steps:
        return None
    return AlarmStateActionReaction(
        alarm_states=alarm_states,
        steps=steps,
        reaction_id=proposal_id,
    )


def present_alarm_state_action_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    if reaction_id in labels_map:
        return labels_map[reaction_id]
    normalized = normalize_alarm_state_action_config(cfg)
    states = list(normalized.get("alarm_states") or [])
    steps = list(normalized.get("steps") or [])
    state_label = ", ".join(states) if states else "alarm state"
    return f"Alarm policy: {state_label} -> {len(steps)} action(s)"


def present_admin_authored_alarm_state_action_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    del flow, proposal
    is_it = language.startswith("it")
    normalized = normalize_alarm_state_action_config(cfg)
    states = list(normalized.get("alarm_states") or [])
    steps = list(normalized.get("steps") or [])
    return [
        f"Stati allarme: {', '.join(states)}" if is_it else f"Alarm states: {', '.join(states)}",
        f"Azioni configurate: {len(steps)}" if is_it else f"Configured actions: {len(steps)}",
    ]


def _normalize_alarm_states(raw: Any) -> list[str]:
    states: list[str] = []
    seen: set[str] = set()
    for value in list(raw or []):
        state = str(value).strip()
        if state not in VALID_ALARM_STATES or state in seen:
            continue
        seen.add(state)
        states.append(state)
    return states


def _normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for raw_step in list(raw_steps or []):
        if not isinstance(raw_step, dict):
            continue
        params = dict(raw_step.get("params") or {})
        target = str(raw_step.get("target") or params.get("entity_id") or "").strip()
        action = str(raw_step.get("action") or "").strip()
        domain = str(raw_step.get("domain") or "").strip()
        if not target or "." not in target:
            continue
        target_domain = target.split(".", 1)[0]
        if not domain:
            domain = target_domain
        if domain != target_domain:
            continue
        if action not in _SUPPORTED_STEP_ACTIONS.get(domain, set()):
            continue
        normalized_params = dict(params)
        normalized_params["entity_id"] = target
        steps.append(
            {
                "domain": domain,
                "target": target,
                "action": action,
                "params": normalized_params,
            }
        )
    return steps
