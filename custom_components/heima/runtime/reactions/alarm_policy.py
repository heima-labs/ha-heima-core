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
_MESSAGES = {
    "en": {
        "alarm_state_fallback": "alarm state",
        "label": "Alarm policy: {states} -> {action}",
        "proposal_label": "Alarm policy: when alarm changes to {states}, {action}",
        "zero_actions": "0 actions",
        "target_one": "target",
        "target_many": "targets",
        "action_count": "{count} actions",
        "type": "Type: semantic policy suggestion from configured topology",
        "alarm_states": "Alarm states: {states}",
        "configured_actions": "Configured actions: {count}",
        "action_line": "Action {index}: {detail}",
        "fallback_action": "{action} -> {target}{params}",
        "climate_preset": "set thermostat {target} to preset '{preset}'",
        "climate_hvac": "set thermostat {target} to HVAC mode '{mode}'",
        "turn_off": "turn off {target}",
        "turn_on": "turn on {target}",
        "activate_scene": "activate scene {target}",
        "run_script": "run script {target}",
        "deactivate": "turn off {target}",
        "activate": "turn on {target}",
    },
    "it": {
        "alarm_state_fallback": "stato allarme",
        "label": "Policy allarme: {states} -> {action}",
        "proposal_label": "Policy allarme: quando l'allarme passa a {states}, {action}",
        "zero_actions": "0 azioni",
        "target_one": "target",
        "target_many": "target",
        "action_count": "{count} azioni",
        "type": "Tipo: suggerimento policy da configurazione",
        "alarm_states": "Stati allarme: {states}",
        "configured_actions": "Azioni configurate: {count}",
        "action_line": "Azione {index}: {detail}",
        "fallback_action": "{action} -> {target}{params}",
        "climate_preset": "imposta il termostato {target} sul preset '{preset}'",
        "climate_hvac": "imposta il termostato {target} in modalita '{mode}'",
        "turn_off": "spegni {target}",
        "turn_on": "accendi {target}",
        "activate_scene": "attiva la scena {target}",
        "run_script": "esegui lo script {target}",
        "deactivate": "disattiva {target}",
        "activate": "attiva {target}",
    },
}


class AlarmStateActionReaction(HeimaReaction):
    """Run configured steps once when the alarm enters a configured state."""

    def __init__(
        self,
        *,
        alarm_states: list[str],
        steps: list[dict[str, Any]],
        reaction_id: str | None = None,
        skip_house_states: list[str] | None = None,
    ) -> None:
        self._alarm_states = _normalize_alarm_states(alarm_states)
        self._steps = _normalize_steps(steps)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._skip_house_states = skip_house_states or []
        self._last_fired_state: str | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history or not self._alarm_states or not self._steps:
            return []
        snapshot = history[-1]
        security_state = str(getattr(snapshot, "security_state", "") or "").strip()
        if security_state not in self._alarm_states:
            self._last_fired_state = None
            return []
        house_state = str(getattr(snapshot, "house_state", "") or "").strip()
        if self._skip_house_states and house_state in self._skip_house_states:
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
            "skip_house_states": list(self._skip_house_states),
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
        "skip_house_states": _normalize_house_states(cfg.get("skip_house_states")),
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
    skip_house_states = list(normalized.get("skip_house_states") or [])
    if not alarm_states or not steps:
        return None
    return AlarmStateActionReaction(
        alarm_states=alarm_states,
        steps=steps,
        reaction_id=proposal_id,
        skip_house_states=skip_house_states,
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
    return _format_policy_label(states=states, steps=steps, language="en", template="label")


def present_alarm_state_action_proposal_label(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> str | None:
    del flow, proposal
    normalized = normalize_alarm_state_action_config(cfg)
    states = list(normalized.get("alarm_states") or [])
    steps = list(normalized.get("steps") or [])
    return _format_policy_label(
        states=states,
        steps=steps,
        language=language,
        template="proposal_label",
        human_single_step=True,
    )


def present_admin_authored_alarm_state_action_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    del flow, proposal
    normalized = normalize_alarm_state_action_config(cfg)
    states = list(normalized.get("alarm_states") or [])
    steps = list(normalized.get("steps") or [])
    messages = _messages(language)
    state_label = _state_label(states, language=language)
    details = [
        messages["type"],
        messages["alarm_states"].format(states=state_label),
        messages["configured_actions"].format(count=len(steps)),
    ]
    for index, step in enumerate(steps, start=1):
        details.append(_format_step_detail(step, index=index, language=language))
    return details


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


def _normalize_house_states(raw: Any) -> list[str]:
    """Normalize house states list."""
    states: list[str] = []
    seen: set[str] = set()
    for value in list(raw or []):
        state = str(value).strip()
        if not state or state in seen:
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


def _format_policy_label(
    *,
    states: list[str],
    steps: list[dict[str, Any]],
    language: str,
    template: str,
    human_single_step: bool = False,
) -> str:
    messages = _messages(language)
    return messages[template].format(
        states=_state_label(states, language=language),
        action=_action_summary(steps, language=language, human_single_step=human_single_step),
    )


def _action_summary(
    steps: list[dict[str, Any]],
    *,
    language: str,
    human_single_step: bool = False,
) -> str:
    messages = _messages(language)
    if not steps:
        return messages["zero_actions"]
    if human_single_step and len(steps) == 1:
        step = steps[0]
        detail = _human_action_detail(
            action=str(step.get("action") or "").strip(),
            target=str(step.get("target") or "").strip(),
            params=dict(step.get("params") or {}),
            language=language,
        )
        if detail:
            return detail
    actions = [str(step.get("action") or "").strip() for step in steps]
    unique_actions = sorted({action for action in actions if action})
    if len(unique_actions) == 1:
        target_count = len(steps)
        target_label = messages["target_one"] if target_count == 1 else messages["target_many"]
        return f"{unique_actions[0]} ({target_count} {target_label})"
    return messages["action_count"].format(count=len(steps))


def _format_step_detail(step: dict[str, Any], *, index: int, language: str) -> str:
    messages = _messages(language)
    action = str(step.get("action") or "").strip() or "unknown"
    target = str(step.get("target") or "").strip() or "unknown"
    params = dict(step.get("params") or {})
    detail = _human_action_detail(action=action, target=target, params=params, language=language)
    if not detail:
        detail = messages["fallback_action"].format(
            action=action,
            target=target,
            params=_format_params(params),
        )
    return messages["action_line"].format(index=index, detail=detail)


def _human_action_detail(
    *,
    action: str,
    target: str,
    params: dict[str, Any],
    language: str,
) -> str:
    messages = _messages(language)
    if action == "climate.set_preset_mode":
        preset = str(params.get("preset_mode") or "").strip()
        if preset:
            return messages["climate_preset"].format(target=target, preset=preset)
    if action == "climate.set_hvac_mode":
        hvac_mode = str(params.get("hvac_mode") or "").strip()
        if hvac_mode:
            return messages["climate_hvac"].format(target=target, mode=hvac_mode)
    if action == "light.turn_off":
        return messages["turn_off"].format(target=target)
    if action == "light.turn_on":
        return messages["turn_on"].format(target=target)
    if action == "switch.turn_off":
        return messages["turn_off"].format(target=target)
    if action == "switch.turn_on":
        return messages["turn_on"].format(target=target)
    if action == "scene.turn_on":
        return messages["activate_scene"].format(target=target)
    if action == "script.turn_on":
        return messages["run_script"].format(target=target)
    if action == "input_boolean.turn_off":
        return messages["deactivate"].format(target=target)
    if action == "input_boolean.turn_on":
        return messages["activate"].format(target=target)
    return ""


def _state_label(states: list[str], *, language: str) -> str:
    return ", ".join(states) if states else _messages(language)["alarm_state_fallback"]


def _messages(language: str) -> dict[str, str]:
    return _MESSAGES["it"] if language.startswith("it") else _MESSAGES["en"]


def _format_params(params: dict[str, Any]) -> str:
    visible = {
        str(key): value
        for key, value in sorted(params.items())
        if str(key) != "entity_id" and value not in (None, "")
    }
    if not visible:
        return ""
    rendered = ", ".join(f"{key}={value}" for key, value in visible.items())
    return f" ({rendered})"
