"""Typed learning policy bundle built from learning config."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .pattern_library import CompositeLearningPatternDefinition


@dataclass(frozen=True)
class PresenceLearningPolicy:
    min_occurrences: int = 5
    min_weeks: int = 2


@dataclass(frozen=True)
class LightingLearningPolicy:
    min_occurrences: int = 5
    min_weeks: int = 2


@dataclass(frozen=True)
class CompositeLearningPolicy:
    min_occurrences: int = 5
    min_weeks: int = 2


@dataclass(frozen=True)
class SecurityPresenceSimulationLearningPolicy:
    min_occurrences: int = 4
    min_weeks: int = 2


@dataclass(frozen=True)
class HeatingLearningPolicy:
    preference_min_events: int = 10
    preference_min_weeks: int = 2
    eco_min_sessions: int = 3
    eco_min_weeks: int = 2

    @property
    def min_events(self) -> int:
        return self.preference_min_events

    @property
    def min_eco_sessions(self) -> int:
        return self.eco_min_sessions

    @property
    def min_weeks(self) -> int:
        return self.preference_min_weeks


@dataclass(frozen=True)
class LearningPolicyBundle:
    presence: PresenceLearningPolicy = PresenceLearningPolicy()
    lighting: LightingLearningPolicy = LightingLearningPolicy()
    composite_room_assist: CompositeLearningPolicy = CompositeLearningPolicy()
    security_presence_simulation: SecurityPresenceSimulationLearningPolicy = (
        SecurityPresenceSimulationLearningPolicy()
    )
    heating: HeatingLearningPolicy = HeatingLearningPolicy()


DEFAULT_LEARNING_POLICY_BUNDLE = LearningPolicyBundle()


def learning_policy_from_config(
    learning_config: dict[str, Any] | None,
) -> LearningPolicyBundle:
    """Build typed family policies from the raw learning config tree."""
    raw = dict(learning_config or {})
    return LearningPolicyBundle(
        presence=_presence_policy_from_raw(raw),
        lighting=_lighting_policy_from_raw(raw),
        composite_room_assist=_composite_policy_from_raw(raw),
        security_presence_simulation=_security_presence_policy_from_raw(raw),
        heating=_heating_policy_from_raw(raw),
    )


def composite_catalog_with_policy(
    catalog: tuple[CompositeLearningPatternDefinition, ...],
    policy: CompositeLearningPolicy,
) -> tuple[CompositeLearningPatternDefinition, ...]:
    """Return a catalog copy with uniform policy thresholds applied."""
    return tuple(
        replace(
            definition,
            min_occurrences=int(policy.min_occurrences),
            min_weeks=int(policy.min_weeks),
        )
        for definition in catalog
    )


def _presence_policy_from_raw(raw: dict[str, Any]) -> PresenceLearningPolicy:
    default = DEFAULT_LEARNING_POLICY_BUNDLE.presence
    family = _family_raw(raw, "presence")
    return PresenceLearningPolicy(
        min_occurrences=_coerce_positive_int(family.get("min_occurrences"), default.min_occurrences),
        min_weeks=_coerce_positive_int(family.get("min_weeks"), default.min_weeks),
    )


def _lighting_policy_from_raw(raw: dict[str, Any]) -> LightingLearningPolicy:
    default = DEFAULT_LEARNING_POLICY_BUNDLE.lighting
    family = _family_raw(raw, "lighting")
    return LightingLearningPolicy(
        min_occurrences=_coerce_positive_int(family.get("min_occurrences"), default.min_occurrences),
        min_weeks=_coerce_positive_int(family.get("min_weeks"), default.min_weeks),
    )


def _composite_policy_from_raw(raw: dict[str, Any]) -> CompositeLearningPolicy:
    default = DEFAULT_LEARNING_POLICY_BUNDLE.composite_room_assist
    family = _family_raw(raw, "composite_room_assist", aliases=("composite",))
    return CompositeLearningPolicy(
        min_occurrences=_coerce_positive_int(family.get("min_occurrences"), default.min_occurrences),
        min_weeks=_coerce_positive_int(family.get("min_weeks"), default.min_weeks),
    )


def _security_presence_policy_from_raw(
    raw: dict[str, Any],
) -> SecurityPresenceSimulationLearningPolicy:
    default = DEFAULT_LEARNING_POLICY_BUNDLE.security_presence_simulation
    family = _family_raw(raw, "security_presence_simulation")
    return SecurityPresenceSimulationLearningPolicy(
        min_occurrences=_coerce_positive_int(family.get("min_occurrences"), default.min_occurrences),
        min_weeks=_coerce_positive_int(family.get("min_weeks"), default.min_weeks),
    )


def _heating_policy_from_raw(raw: dict[str, Any]) -> HeatingLearningPolicy:
    default = DEFAULT_LEARNING_POLICY_BUNDLE.heating
    family = _family_raw(raw, "heating")
    fallback_min_weeks = _coerce_positive_int(family.get("min_weeks"), default.preference_min_weeks)
    return HeatingLearningPolicy(
        preference_min_events=_coerce_positive_int(
            family.get("preference_min_events"),
            _coerce_positive_int(family.get("min_events"), default.preference_min_events),
        ),
        preference_min_weeks=_coerce_positive_int(
            family.get("preference_min_weeks"),
            fallback_min_weeks,
        ),
        eco_min_sessions=_coerce_positive_int(
            family.get("eco_min_sessions"),
            _coerce_positive_int(family.get("min_eco_sessions"), default.eco_min_sessions),
        ),
        eco_min_weeks=_coerce_positive_int(
            family.get("eco_min_weeks"),
            fallback_min_weeks,
        ),
    )


def _family_raw(raw: dict[str, Any], key: str, *, aliases: tuple[str, ...] = ()) -> dict[str, Any]:
    for candidate in (key, *aliases):
        value = raw.get(candidate)
        if isinstance(value, dict):
            return value
    return {}


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return coerced if coerced > 0 else default
