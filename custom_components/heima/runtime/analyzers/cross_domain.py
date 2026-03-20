"""Cross-domain pattern analyzers for room-scoped composite assist proposals."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..event_store import EventStore, HeimaEvent
from .base import ReactionProposal
from .composite import (
    CompositePatternSpec,
    CompositeSignalSpec,
    RoomScopedCompositeMatcher,
)
from .pattern_library import CompositeLearningPatternDefinition

_MIN_OCCURRENCES = 5
_MIN_WEEKS = 2
_HUMIDITY_RISE_THRESHOLD = 8.0
_TEMPERATURE_RISE_THRESHOLD = 0.8
_CORRELATION_WINDOW_S = 10 * 60
_FOLLOWUP_WINDOW_S = 15 * 60


class CrossDomainPatternAnalyzer:
    """Detect room-scoped humidity burst + occupancy + ventilation follow-up patterns."""

    def __init__(self) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._definition = _definition_by_pattern_id("room_signal_assist")

    @property
    def analyzer_id(self) -> str:
        return self._definition.analyzer_id

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        return await _analyze_definition(
            event_store=event_store,
            matcher=self._matcher,
            definition=self._definition,
        )


class RoomCoolingPatternAnalyzer:
    """Detect room-scoped temperature rise + cooling follow-up patterns."""

    def __init__(self) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._definition = _definition_by_pattern_id("room_cooling_assist")

    @property
    def analyzer_id(self) -> str:
        return self._definition.analyzer_id

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        return await _analyze_definition(
            event_store=event_store,
            matcher=self._matcher,
            definition=self._definition,
        )


class CompositePatternCatalogAnalyzer:
    """Run the declared composite pattern catalog through one shared analyzer path."""

    def __init__(
        self,
        *,
        catalog: tuple[CompositeLearningPatternDefinition, ...] | None = None,
    ) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._catalog = tuple(catalog or DEFAULT_COMPOSITE_PATTERN_CATALOG)

    @property
    def analyzer_id(self) -> str:
        return "CompositePatternCatalogAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        proposals: list[ReactionProposal] = []
        for definition in self._catalog:
            proposals.extend(
                await _analyze_definition(
                    event_store=event_store,
                    matcher=self._matcher,
                    definition=definition,
                )
            )
        return proposals


async def _analyze_definition(
    *,
    event_store: EventStore,
    matcher: RoomScopedCompositeMatcher,
    definition: CompositeLearningPatternDefinition,
) -> list[ReactionProposal]:
    raw = await event_store.async_query(event_type="state_change")
    events = [e for e in raw if isinstance(e, HeimaEvent) and e.room_id]
    if not events:
        return []

    by_room: dict[str, list[HeimaEvent]] = {}
    for event in events:
        by_room.setdefault(str(event.room_id), []).append(event)

    proposals: list[ReactionProposal] = []
    for room_id, room_events in by_room.items():
        room_events.sort(key=lambda e: e.ts)
        episodes = matcher.detect(room_id=room_id, events=room_events, spec=definition.matcher_spec)
        if len(episodes) < definition.min_occurrences or not _spans_min_weeks(
            episodes, min_weeks=definition.min_weeks
        ):
            continue

        confirmed = [ep for ep in episodes if ep.followup_entities]
        if len(confirmed) < definition.min_occurrences:
            continue

        suggested = definition.suggested_config_builder(room_id, confirmed)
        diagnostics = _build_default_diagnostics(
            room_id=room_id,
            definition=definition,
            episodes=episodes,
            confirmed=confirmed,
        )
        if definition.diagnostics_builder is not None:
            diagnostics.update(
                definition.diagnostics_builder(
                    room_id,
                    episodes,
                    confirmed,
                    definition.matcher_spec,
                )
            )
        suggested["learning_diagnostics"] = diagnostics
        corroborated = int(suggested.get("corroborated_episodes", 0))
        proposals.append(
            ReactionProposal(
                analyzer_id=definition.analyzer_id,
                reaction_type=definition.reaction_type,
                description=definition.description_builder(room_id, len(confirmed), corroborated),
                confidence=round(definition.confidence_builder(confirmed), 3),
                suggested_reaction_config=suggested,
                fingerprint=(
                    f"{definition.analyzer_id}|{definition.reaction_type}|{room_id}|"
                    f"{definition.fingerprint_key}"
                ),
            )
        )
    return proposals


def _is_humidity_event(event: HeimaEvent) -> bool:
    if event.data.get("device_class") == "humidity":
        return True
    entity_id = str(event.subject_id or event.data.get("entity_id") or "")
    return "humidity" in entity_id


def _is_temperature_event(event: HeimaEvent) -> bool:
    if event.data.get("device_class") == "temperature":
        return True
    entity_id = str(event.subject_id or event.data.get("entity_id") or "")
    return "temperature" in entity_id or "temp" in entity_id


def _is_activation_event(event: HeimaEvent) -> bool:
    entity_id = str(event.subject_id or event.data.get("entity_id") or "")
    domain = str(event.domain or "")
    if domain not in {"fan", "switch"} and not entity_id.startswith(("fan.", "switch.")):
        return False
    return str(event.data.get("new_state") or "") == "on"


def _is_cooling_followup_event(event: HeimaEvent) -> bool:
    entity_id = str(event.subject_id or event.data.get("entity_id") or "")
    domain = str(event.domain or "")
    new_state = str(event.data.get("new_state") or "").lower()
    if domain in {"fan", "switch"} or entity_id.startswith(("fan.", "switch.")):
        return new_state == "on"
    if domain == "climate" or entity_id.startswith("climate."):
        return new_state in {"cool", "cooling", "dry", "fan_only", "on"}
    return False


def _spans_min_weeks(episodes: list, *, min_weeks: int) -> bool:
    weeks: set[tuple[int, int]] = set()
    for episode in episodes:
        iso = episode.ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks) >= min_weeks


def _corroborated_ratio(episodes: list, key: str) -> float:
    if not episodes:
        return 0.0
    return sum(1 for ep in episodes if ep.corroboration_matches.get(key)) / len(episodes)


def _build_signal_assist_config(room_id: str, confirmed: list) -> dict[str, Any]:
    humidity_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    temperature_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for entity_id in ep.corroboration_matches.get("temperature", ())
            if entity_id
        }
    )
    followup_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for entity_id in ep.followup_entities
            if entity_id
        }
    )
    return {
        "reaction_class": "RoomSignalAssistReaction",
        "room_id": room_id,
        "trigger_signal_entities": humidity_entities,
        "temperature_signal_entities": temperature_entities,
        "humidity_rise_threshold": _HUMIDITY_RISE_THRESHOLD,
        "temperature_rise_threshold": _TEMPERATURE_RISE_THRESHOLD,
        "correlation_window_s": _CORRELATION_WINDOW_S,
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "steps": [],
        "episodes_observed": len(confirmed),
        "corroborated_episodes": sum(
            1 for ep in confirmed if ep.corroboration_matches.get("temperature")
        ),
        "observed_followup_entities": followup_entities,
    }


def _build_cooling_assist_config(room_id: str, confirmed: list) -> dict[str, Any]:
    temperature_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    humidity_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for entity_id in ep.corroboration_matches.get("humidity", ())
            if entity_id
        }
    )
    followup_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for entity_id in ep.followup_entities
            if entity_id
        }
    )
    corroborated_count = sum(1 for ep in confirmed if ep.corroboration_matches.get("humidity"))
    return {
        "reaction_class": "RoomSignalAssistReaction",
        "room_id": room_id,
        "trigger_signal_entities": temperature_entities,
        "primary_signal_entities": temperature_entities,
        "primary_rise_threshold": 1.5,
        "primary_signal_name": "temperature",
        "temperature_signal_entities": humidity_entities,
        "corroboration_signal_entities": humidity_entities,
        "corroboration_rise_threshold": 5.0,
        "corroboration_signal_name": "humidity",
        "correlation_window_s": _CORRELATION_WINDOW_S,
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "steps": [],
        "episodes_observed": len(confirmed),
        "corroborated_episodes": corroborated_count,
        "observed_followup_entities": followup_entities,
    }


def _build_default_diagnostics(
    *,
    room_id: str,
    definition: CompositeLearningPatternDefinition,
    episodes: list,
    confirmed: list,
) -> dict[str, Any]:
    corroboration_signal_names = [
        signal.name for signal in definition.matcher_spec.corroborations
    ]
    primary_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    corroboration_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for matches in ep.corroboration_matches.values()
            for entity_id in matches
            if entity_id
        }
    )
    followup_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for entity_id in ep.followup_entities
            if entity_id
        }
    )
    return {
        "pattern_id": definition.pattern_id,
        "room_id": room_id,
        "analyzer_id": definition.analyzer_id,
        "reaction_type": definition.reaction_type,
        "primary_signal": definition.matcher_spec.primary.name,
        "corroboration_signals": corroboration_signal_names,
        "followup_signal": (
            definition.matcher_spec.followup.name
            if definition.matcher_spec.followup is not None
            else None
        ),
        "require_room_occupancy": definition.matcher_spec.require_room_occupancy,
        "correlation_window_s": definition.matcher_spec.correlation_window_s,
        "followup_window_s": definition.matcher_spec.followup_window_s,
        "episodes_detected": len(episodes),
        "episodes_confirmed": len(confirmed),
        "weeks_observed": _episode_week_count(episodes),
        "corroborated_episodes": sum(
            1 for ep in confirmed if any(ep.corroboration_matches.values())
        ),
        "matched_primary_entities": primary_entities,
        "matched_corroboration_entities": corroboration_entities,
        "observed_followup_entities": followup_entities,
    }


def _describe(room_id: str, observed: int, corroborated: int) -> str:
    if corroborated:
        return (
            f"{room_id}: when occupancy is present and humidity rises rapidly, "
            f"you usually start ventilation within a few minutes "
            f"({observed} episodes, {corroborated} temperature-correlated)."
        )
    return (
        f"{room_id}: when occupancy is present and humidity rises rapidly, "
        f"you usually start ventilation within a few minutes "
        f"({observed} observed episodes)."
    )


def _describe_cooling(room_id: str, observed: int, corroborated: int) -> str:
    if corroborated:
        return (
            f"{room_id}: when occupancy is present and temperature rises quickly, "
            f"you usually start cooling within a few minutes "
            f"({observed} episodes, {corroborated} humidity-correlated)."
        )
    return (
        f"{room_id}: when occupancy is present and temperature rises quickly, "
        f"you usually start cooling within a few minutes "
        f"({observed} observed episodes)."
    )


_ROOM_SIGNAL_ASSIST_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_signal_assist",
    analyzer_id="CrossDomainPatternAnalyzer",
    reaction_type="room_signal_assist",
    fingerprint_key="humidity_burst",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="humidity",
            predicate=_is_humidity_event,
            min_delta=_HUMIDITY_RISE_THRESHOLD,
        ),
        corroborations=(
            CompositeSignalSpec(
                name="temperature",
                predicate=_is_temperature_event,
                min_delta=_TEMPERATURE_RISE_THRESHOLD,
                required=False,
            ),
        ),
        followup=CompositeSignalSpec(
            name="ventilation",
            predicate=_is_activation_event,
        ),
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe,
    suggested_config_builder=lambda room_id, confirmed: _build_signal_assist_config(room_id, confirmed),
    confidence_builder=lambda confirmed: min(
        0.95,
        0.45 + (0.07 * len(confirmed)) + (0.05 * _corroborated_ratio(confirmed, "temperature")),
    ),
)


_ROOM_COOLING_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_cooling_assist",
    analyzer_id="RoomCoolingPatternAnalyzer",
    reaction_type="room_cooling_assist",
    fingerprint_key="temperature_rise",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="temperature",
            predicate=_is_temperature_event,
            min_delta=1.5,
        ),
        corroborations=(
            CompositeSignalSpec(
                name="humidity",
                predicate=_is_humidity_event,
                min_delta=5.0,
                required=False,
            ),
        ),
        followup=CompositeSignalSpec(
            name="cooling",
            predicate=_is_cooling_followup_event,
        ),
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe_cooling,
    suggested_config_builder=lambda room_id, confirmed: _build_cooling_assist_config(room_id, confirmed),
    confidence_builder=lambda confirmed: min(
        0.95,
        0.42
        + (0.07 * len(confirmed))
        + (
            0.05
            * _ratio(
                sum(1 for ep in confirmed if ep.corroboration_matches.get("humidity")),
                len(confirmed),
            )
        ),
    ),
)


DEFAULT_COMPOSITE_PATTERN_CATALOG: tuple[CompositeLearningPatternDefinition, ...] = (
    _ROOM_SIGNAL_ASSIST_PATTERN,
    _ROOM_COOLING_PATTERN,
)


def _definition_by_pattern_id(pattern_id: str) -> CompositeLearningPatternDefinition:
    for definition in DEFAULT_COMPOSITE_PATTERN_CATALOG:
        if definition.pattern_id == pattern_id:
            return definition
    raise KeyError(pattern_id)


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return part / total


def _episode_week_count(episodes: list) -> int:
    weeks: set[tuple[int, int]] = set()
    for episode in episodes:
        iso = episode.ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks)
