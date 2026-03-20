"""Cross-domain pattern analyzer (v1) for room-scoped signal assist proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..event_store import EventStore, HeimaEvent
from .base import ReactionProposal

_MIN_OCCURRENCES = 5
_MIN_WEEKS = 2
_HUMIDITY_RISE_THRESHOLD = 8.0
_TEMPERATURE_RISE_THRESHOLD = 0.8
_CORRELATION_WINDOW_S = 10 * 60
_FOLLOWUP_WINDOW_S = 15 * 60


@dataclass(frozen=True)
class _Episode:
    room_id: str
    ts: datetime
    humidity_entity: str
    humidity_delta: float
    corroborated: bool
    followed_by_fan: bool


class CrossDomainPatternAnalyzer:
    """Detect room-scoped humidity burst + occupancy + ventilation follow-up patterns."""

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
            episodes = self._detect_episodes(room_id, room_events)
            if len(episodes) < _MIN_OCCURRENCES:
                continue
            if not _spans_min_weeks(episodes):
                continue

            confirmed = [ep for ep in episodes if ep.followed_by_fan]
            if len(confirmed) < _MIN_OCCURRENCES:
                continue

            confidence = min(0.95, 0.45 + (0.07 * len(confirmed)) + (0.05 * _corroborated_ratio(confirmed)))
            humidity_entities = sorted({ep.humidity_entity for ep in confirmed})
            suggested: dict[str, Any] = {
                "reaction_class": "RoomSignalAssistReaction",
                "room_id": room_id,
                "trigger_signal_entities": humidity_entities,
                "humidity_rise_threshold": _HUMIDITY_RISE_THRESHOLD,
                "temperature_rise_threshold": _TEMPERATURE_RISE_THRESHOLD,
                "correlation_window_s": _CORRELATION_WINDOW_S,
                "followup_window_s": _FOLLOWUP_WINDOW_S,
                "steps": [],
                "episodes_observed": len(confirmed),
                "corroborated_episodes": sum(1 for ep in confirmed if ep.corroborated),
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

    def _detect_episodes(self, room_id: str, events: list[HeimaEvent]) -> list[_Episode]:
        humidity_events = [e for e in events if _is_humidity_event(e)]
        temp_events = [e for e in events if _is_temperature_event(e)]
        fan_events = [e for e in events if _is_activation_event(e)]
        episodes: list[_Episode] = []
        for event in humidity_events:
            ts = _parse_ts(event.ts)
            if ts is None:
                continue
            if room_id not in event.context.occupied_rooms:
                continue
            delta = _numeric_delta(event)
            if delta is None or delta < _HUMIDITY_RISE_THRESHOLD:
                continue
            corroborated = any(
                _within_window(ts, _parse_ts(candidate.ts), _CORRELATION_WINDOW_S)
                and (_numeric_delta(candidate) or 0.0) >= _TEMPERATURE_RISE_THRESHOLD
                for candidate in temp_events
            )
            followed_by_fan = any(
                _within_followup(ts, _parse_ts(candidate.ts), _FOLLOWUP_WINDOW_S)
                for candidate in fan_events
            )
            episodes.append(
                _Episode(
                    room_id=room_id,
                    ts=ts,
                    humidity_entity=str(event.subject_id or event.data.get("entity_id") or ""),
                    humidity_delta=delta,
                    corroborated=corroborated,
                    followed_by_fan=followed_by_fan,
                )
            )
        return episodes


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _numeric_delta(event: HeimaEvent) -> float | None:
    try:
        old = float(event.data.get("old_state"))
        new = float(event.data.get("new_state"))
    except (TypeError, ValueError):
        return None
    return new - old


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


def _within_window(origin: datetime, candidate: datetime | None, seconds: int) -> bool:
    if candidate is None:
        return False
    delta = abs((candidate - origin).total_seconds())
    return delta <= seconds


def _within_followup(origin: datetime, candidate: datetime | None, seconds: int) -> bool:
    if candidate is None:
        return False
    delta = (candidate - origin).total_seconds()
    return 0 <= delta <= seconds


def _spans_min_weeks(episodes: list[_Episode]) -> bool:
    weeks: set[tuple[int, int]] = set()
    for episode in episodes:
        iso = episode.ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks) >= _MIN_WEEKS


def _corroborated_ratio(episodes: list[_Episode]) -> float:
    if not episodes:
        return 0.0
    return sum(1 for ep in episodes if ep.corroborated) / len(episodes)


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
