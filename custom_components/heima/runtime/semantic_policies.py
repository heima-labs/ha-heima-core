"""Stateless semantic policy suggestions derived from configured topology."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..const import OPT_HEATING, OPT_LIGHTING_ROOMS, OPT_ROOMS, OPT_SECURITY
from .analyzers.base import ReactionProposal
from .reactions.alarm_policy import normalize_alarm_state_action_config

_ANALYZER_ID = "semantic_policy_suggestions"


@dataclass(frozen=True)
class SemanticRule:
    """Pure semantic rule that may produce an admin-authored reaction proposal."""

    rule_id: str
    description: str

    def evaluate(self, options: dict[str, Any]) -> ReactionProposal | None:
        """Return a pre-filled proposal when the configured topology is complete."""
        evaluator = _RULE_EVALUATORS.get(self.rule_id)
        if evaluator is None:
            return None
        return evaluator(self, options)


BUILTIN_SEMANTIC_RULES: tuple[SemanticRule, ...] = (
    SemanticRule(
        rule_id="alarm_away_lights_off",
        description="Turn configured lights off when the alarm is armed away.",
    ),
    SemanticRule(
        rule_id="alarm_triggered_lights_on",
        description="Turn configured lights on when the alarm is triggered.",
    ),
    SemanticRule(
        rule_id="alarm_away_climate_off",
        description="Turn configured thermostats off when the alarm is armed away.",
    ),
    SemanticRule(
        rule_id="alarm_night_climate_sleep",
        description="Set configured thermostats to sleep preset when the alarm is armed night.",
    ),
    SemanticRule(
        rule_id="alarm_night_camera_privacy",
        description="Enable camera privacy when alarm is armed night (except guest/vacation states).",
    ),
)


def _lights_off(rule: SemanticRule, options: dict[str, Any]) -> ReactionProposal | None:
    return _light_policy_proposal(
        rule,
        options,
        alarm_state="armed_away",
        action="light.turn_off",
    )


def _lights_on(rule: SemanticRule, options: dict[str, Any]) -> ReactionProposal | None:
    return _light_policy_proposal(
        rule,
        options,
        alarm_state="triggered",
        action="light.turn_on",
    )


def _climate_off(rule: SemanticRule, options: dict[str, Any]) -> ReactionProposal | None:
    return _climate_policy_proposal(
        rule,
        options,
        alarm_state="armed_away",
        action="climate.set_hvac_mode",
        params={"hvac_mode": "off"},
    )


def _climate_sleep(rule: SemanticRule, options: dict[str, Any]) -> ReactionProposal | None:
    return _climate_policy_proposal(
        rule,
        options,
        alarm_state="armed_night",
        action="climate.set_preset_mode",
        params={"preset_mode": "sleep"},
    )


def _camera_privacy_proposal(rule: SemanticRule, options: dict[str, Any]) -> ReactionProposal | None:
    if not _alarm_entity(options):
        return None
    privacy_entities = _configured_camera_entity_entities(options, field="privacy_entity", domain="switch")
    if not privacy_entities:
        return None
    return _proposal(
        rule,
        alarm_state="armed_night",
        steps=[{"domain": "switch", "target": e, "action": "switch.turn_on"} for e in privacy_entities],
        skip_house_states=["guest", "vacation"],
    )


_RULE_EVALUATORS: dict[str, Callable[[SemanticRule, dict[str, Any]], ReactionProposal | None]] = {
    "alarm_away_lights_off": _lights_off,
    "alarm_triggered_lights_on": _lights_on,
    "alarm_away_climate_off": _climate_off,
    "alarm_night_climate_sleep": _climate_sleep,
    "alarm_night_camera_privacy": _camera_privacy_proposal,
}


def _light_policy_proposal(
    rule: SemanticRule,
    options: dict[str, Any],
    *,
    alarm_state: str,
    action: str,
) -> ReactionProposal | None:
    if not _alarm_entity(options):
        return None
    light_entities = _configured_light_entities(options)
    if not light_entities:
        return None
    steps = [
        {
            "domain": "light",
            "target": entity_id,
            "action": action,
            "params": {"entity_id": entity_id},
        }
        for entity_id in light_entities
    ]
    return _proposal(rule, alarm_state=alarm_state, steps=steps)


def _climate_policy_proposal(
    rule: SemanticRule,
    options: dict[str, Any],
    *,
    alarm_state: str,
    action: str,
    params: dict[str, Any],
) -> ReactionProposal | None:
    if not _alarm_entity(options):
        return None
    climate_entities = _configured_climate_entities(options)
    if not climate_entities:
        return None
    steps = [
        {
            "domain": "climate",
            "target": entity_id,
            "action": action,
            "params": {"entity_id": entity_id, **params},
        }
        for entity_id in climate_entities
    ]
    return _proposal(rule, alarm_state=alarm_state, steps=steps)


def _proposal(
    rule: SemanticRule,
    *,
    alarm_state: str,
    steps: list[dict[str, Any]],
    skip_house_states: list[str] | None = None,
) -> ReactionProposal:
    config: dict[str, Any] = {
        "reaction_type": "alarm_state_action",
        "alarm_states": [alarm_state],
        "steps": steps,
    }
    if skip_house_states:
        config["skip_house_states"] = skip_house_states
    return ReactionProposal(
        analyzer_id=_ANALYZER_ID,
        reaction_type="alarm_state_action",
        description=rule.description,
        confidence=1.0,
        origin="admin_authored",
        identity_key=rule.rule_id,
        suggested_reaction_config=normalize_alarm_state_action_config(config),
    )


def _alarm_entity(options: dict[str, Any]) -> str:
    security = options.get(OPT_SECURITY)
    if not isinstance(security, dict):
        return ""
    return str(security.get("security_state_entity") or "").strip()


def _configured_climate_entities(options: dict[str, Any]) -> list[str]:
    heating = options.get(OPT_HEATING)
    if not isinstance(heating, dict):
        return []
    return _unique_entities([heating.get("climate_entity")], domain="climate")


def _configured_light_entities(options: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in (OPT_ROOMS, OPT_LIGHTING_ROOMS):
        for item in _dict_items(options.get(key)):
            values.extend(_raw_light_entity_values(item))
    return _unique_entities(values, domain="light")


def _raw_light_entity_values(item: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for key in (
        "light_entities",
        "lighting_entities",
        "configured_light_entities",
        "suggested_lighting_entities",
    ):
        raw = item.get(key)
        if isinstance(raw, dict):
            values.extend(raw.keys())
        elif isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif raw:
            values.append(raw)
    return values


def _dict_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _unique_entities(values: list[Any], *, domain: str) -> list[str]:
    entities: list[str] = []
    seen: set[str] = set()
    prefix = f"{domain}."
    for value in values:
        entity_id = str(value or "").strip()
        if not entity_id.startswith(prefix) or entity_id in seen:
            continue
        seen.add(entity_id)
        entities.append(entity_id)
    return entities


def _configured_camera_entity_entities(
    options: dict[str, Any],
    field: str,
    domain: str,
) -> list[str]:
    """Extract entity IDs from camera_evidence_sources for a specific field.
    
    Args:
        options: The full configuration options
        field: The field name to extract (e.g., "privacy_entity", "light_entity")
        domain: The expected domain prefix (e.g., "switch", "light")
    
    Returns:
        List of entity IDs that match the domain prefix
    """
    security = options.get(OPT_SECURITY)
    if not isinstance(security, dict):
        return []
    sources = security.get("camera_evidence_sources", [])
    entities: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        entity = source.get(field)
        if entity and isinstance(entity, str):
            entities.append(entity.strip())
    return _unique_entities(entities, domain=domain)
