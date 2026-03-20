"""Cross-domain pattern analyzer (v1) for room-scoped signal assist proposals."""

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
        self._pattern = CompositePatternSpec(
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
        )

    @property
    def analyzer_id(self) -> str:
        return "CrossDomainPatternAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
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
            episodes = self._matcher.detect(room_id=room_id, events=room_events, spec=self._pattern)
            if len(episodes) < _MIN_OCCURRENCES:
                continue
            if not _spans_min_weeks(episodes):
                continue

            confirmed = [ep for ep in episodes if ep.followup_entities]
            if len(confirmed) < _MIN_OCCURRENCES:
                continue

            confidence = min(0.95, 0.45 + (0.07 * len(confirmed)) + (0.05 * _corroborated_ratio(confirmed)))
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
            suggested: dict[str, Any] = {
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
            fingerprint = f"{self.analyzer_id}|room_signal_assist|{room_id}|humidity_burst"
            proposals.append(
                ReactionProposal(
                    analyzer_id=self.analyzer_id,
                    reaction_type="room_signal_assist",
                    description=_describe(room_id, len(confirmed), suggested["corroborated_episodes"]),
                    confidence=round(confidence, 3),
                    suggested_reaction_config=suggested,
                    fingerprint=fingerprint,
                )
            )
        return proposals


class RoomCoolingPatternAnalyzer:
    """Detect room-scoped temperature rise + cooling follow-up patterns."""

    def __init__(self) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._pattern = CompositePatternSpec(
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
        )

    @property
    def analyzer_id(self) -> str:
        return "RoomCoolingPatternAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
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
            episodes = self._matcher.detect(room_id=room_id, events=room_events, spec=self._pattern)
            if len(episodes) < _MIN_OCCURRENCES or not _spans_min_weeks(episodes):
                continue

            confirmed = [ep for ep in episodes if ep.followup_entities]
            if len(confirmed) < _MIN_OCCURRENCES:
                continue

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
            corroborated_count = sum(
                1 for ep in confirmed if ep.corroboration_matches.get("humidity")
            )
            confidence = min(0.95, 0.42 + (0.07 * len(confirmed)) + (0.05 * _ratio(corroborated_count, len(confirmed))))
            suggested: dict[str, Any] = {
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
            fingerprint = f"{self.analyzer_id}|room_cooling_assist|{room_id}|temperature_rise"
            proposals.append(
                ReactionProposal(
                    analyzer_id=self.analyzer_id,
                    reaction_type="room_cooling_assist",
                    description=_describe_cooling(room_id, len(confirmed), corroborated_count),
                    confidence=round(confidence, 3),
                    suggested_reaction_config=suggested,
                    fingerprint=fingerprint,
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


def _spans_min_weeks(episodes: list) -> bool:
    weeks: set[tuple[int, int]] = set()
    for episode in episodes:
        iso = episode.ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks) >= _MIN_WEEKS


def _corroborated_ratio(episodes: list) -> float:
    if not episodes:
        return 0.0
    return (
        sum(1 for ep in episodes if ep.corroboration_matches.get("temperature")) / len(episodes)
    )


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return part / total
