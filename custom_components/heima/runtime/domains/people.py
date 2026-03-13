"""PeopleDomain: named + anonymous presence computation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from ...const import OPT_PEOPLE_ANON, OPT_PEOPLE_NAMED
from ..normalization.config import (
    GROUP_PRESENCE_STRATEGY_CONTRACT,
    build_signal_set_strategy_cfg_for_contract,
)
from ..normalization.service import InputNormalizer
from ..state_store import CanonicalState
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PeopleResult:
    """Result of PeopleDomain.compute()."""

    home_people: list[str]       # slugs of named people who are home
    anon_home: bool
    anon_confidence: int
    anon_source: str
    anon_weight: int
    anyone_home: bool
    people_count: int
    people_home_list: list[str]


class PeopleDomain:
    """Computes named and anonymous presence."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._group_presence_trace: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        """Callerd on options reload."""
        self._group_presence_trace = {}

    @property
    def group_presence_trace(self) -> dict[str, dict[str, Any]]:
        return self._group_presence_trace

    def diagnostics(self) -> dict[str, Any]:
        return {
            "group_trace": dict(self._group_presence_trace),
        }

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    def compute(
        self,
        options: dict[str, Any],
        state: CanonicalState,
        events: EventsDomain,
    ) -> PeopleResult:
        named_people = options.get(OPT_PEOPLE_NAMED, [])
        home_people: list[str] = []

        for person in named_people:
            slug = person.get("slug")
            if not slug:
                continue
            is_home, source, confidence = self._compute_named_person_presence(
                person, state
            )
            prev_is_home = state.get_binary(f"heima_person_{slug}_home")
            state.set_binary(f"heima_person_{slug}_home", is_home)
            state.set_sensor(f"heima_person_{slug}_source", source)
            state.set_sensor(f"heima_person_{slug}_confidence", confidence)
            events.queue_people_transition_event(
                slug=slug,
                prev_is_home=prev_is_home,
                is_home=is_home,
                source=source,
                confidence=confidence,
            )
            if is_home:
                home_people.append(slug)

        anon_cfg = options.get(OPT_PEOPLE_ANON, {})
        anon_home = False
        anon_confidence = 0
        anon_source = "disabled"
        anon_weight = 0

        if anon_cfg.get("enabled"):
            anon_sources = list(anon_cfg.get("sources", []))
            required = int(anon_cfg.get("required", 1))
            anon_fused, active_count = self._compute_group_presence(
                anon_sources,
                required,
                strategy=str(anon_cfg.get("group_strategy", "quorum") or "quorum"),
                weight_threshold=anon_cfg.get("weight_threshold"),
                source_weights=anon_cfg.get("source_weights"),
                trace_key="anonymous",
            )
            anon_home = anon_fused.state == "on"
            anon_confidence = int(anon_fused.confidence)
            anon_source = ",".join(anon_sources) if anon_sources else "none"
            anon_weight = int(anon_cfg.get("anonymous_count_weight", 1)) if anon_home else 0
            prev_anon_home = state.get_binary("heima_anonymous_presence")
            state.set_binary("heima_anonymous_presence", anon_home)
            state.set_sensor("heima_anonymous_presence_confidence", anon_confidence)
            state.set_sensor("heima_anonymous_presence_source", anon_source)
            events.queue_anonymous_transition_event(
                prev_is_on=prev_anon_home,
                is_on=anon_home,
                source=anon_source,
                confidence=anon_confidence,
                weight=int(anon_cfg.get("anonymous_count_weight", 1)),
            )
            _LOGGER.debug("Anonymous presence active_count=%s", active_count)

        anyone_home = bool(home_people) or anon_home
        people_count = len(home_people) + anon_weight
        people_home_list = home_people + (["anonymous"] if anon_home else [])

        return PeopleResult(
            home_people=home_people,
            anon_home=anon_home,
            anon_confidence=anon_confidence,
            anon_source=anon_source,
            anon_weight=anon_weight,
            anyone_home=anyone_home,
            people_count=people_count,
            people_home_list=people_home_list,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_named_person_presence(
        self, person_cfg: dict[str, Any], state: CanonicalState
    ) -> tuple[bool, str, int]:
        slug = str(person_cfg.get("slug", ""))
        override = state.get_select(f"heima_person_{slug}_override")
        if override == "force_home":
            return True, "manual", 100
        if override == "force_away":
            return False, "manual", 100

        method = person_cfg.get("presence_method", "ha_person")
        if method == "ha_person":
            entity_id = person_cfg.get("person_entity")
            is_home = self._normalizer.presence(entity_id).state == "on"
            return is_home, "ha_person", 100 if is_home else 0

        if method == "quorum":
            sources = list(person_cfg.get("sources", []))
            required = int(person_cfg.get("required", 1))
            trace_key = f"person:{slug}" if slug else "person:unknown"
            fused, active_count = self._compute_group_presence(
                sources,
                required,
                strategy=str(person_cfg.get("group_strategy", "quorum") or "quorum"),
                weight_threshold=person_cfg.get("weight_threshold"),
                source_weights=person_cfg.get("source_weights"),
                trace_key=trace_key,
            )
            is_home = fused.state == "on"
            confidence = int(fused.confidence)
            return is_home, "quorum", confidence

        return False, "manual", 0

    def _compute_group_presence(
        self,
        sources: list[str],
        required: int,
        *,
        strategy: str = "quorum",
        weight_threshold: Any = None,
        source_weights: Any = None,
        trace_key: str | None = None,
    ) -> tuple[Any, int]:
        observations = [self._normalizer.presence(entity_id) for entity_id in sources]
        active_count = sum(1 for obs in observations if obs.state == "on")
        group_strategy = str(strategy or "quorum")
        strategy_cfg = build_signal_set_strategy_cfg_for_contract(
            contract=GROUP_PRESENCE_STRATEGY_CONTRACT,
            strategy=group_strategy,
            required=int(required),
            weight_threshold=weight_threshold,
            source_weights=source_weights,
            fallback_state="off",
        )
        fused = self._normalizer.derive(
            kind="presence",
            inputs=observations,
            strategy_cfg=strategy_cfg,
            context={"source": "group_presence"},
        )
        if trace_key:
            self._group_presence_trace[trace_key] = {
                "source_observations": [obs.as_dict() for obs in observations],
                "fused_observation": fused.as_dict(),
                "plugin_id": fused.plugin_id,
                "group_strategy": group_strategy,
                "required": int(required),
                "weight_threshold": (
                    float(weight_threshold)
                    if group_strategy == "weighted_quorum"
                    and weight_threshold not in (None, "")
                    else None
                ),
                "configured_source_weights": (
                    dict(source_weights)
                    if group_strategy == "weighted_quorum"
                    and isinstance(source_weights, dict)
                    else {}
                ),
                "active_count": active_count,
                "used_plugin_fallback": fused.reason == "plugin_error_fallback",
            }
        return fused, active_count
