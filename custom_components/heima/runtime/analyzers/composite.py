"""Reusable room-scoped composite pattern matcher utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from ..event_store import HeimaEvent


EventPredicate = Callable[[HeimaEvent], bool]


@dataclass(frozen=True)
class CompositeSignalSpec:
    """Single signal matcher used inside a composite room-scoped pattern."""

    name: str
    predicate: EventPredicate
    min_delta: float | None = None
    required: bool = False


@dataclass(frozen=True)
class CompositePatternSpec:
    """Definition of a composite room-scoped event pattern."""

    primary: CompositeSignalSpec
    corroborations: tuple[CompositeSignalSpec, ...] = ()
    followup: CompositeSignalSpec | None = None
    require_room_occupancy: bool = True
    correlation_window_s: int = 0
    followup_window_s: int = 0


@dataclass(frozen=True)
class CompositeEpisode:
    """One matched occurrence of a composite room-scoped pattern."""

    room_id: str
    ts: datetime
    primary_entity: str
    primary_delta: float
    corroboration_matches: dict[str, tuple[str, ...]]
    followup_entities: tuple[str, ...]


class RoomScopedCompositeMatcher:
    """Detect repeated room-scoped patterns from normalized Heima events."""

    def detect(self, *, room_id: str, events: list[HeimaEvent], spec: CompositePatternSpec) -> list[CompositeEpisode]:
        primary_events = [event for event in events if spec.primary.predicate(event)]
        corroboration_buckets = {
            signal.name: [event for event in events if signal.predicate(event)]
            for signal in spec.corroborations
        }
        followup_events = [
            event for event in events
            if spec.followup is not None and spec.followup.predicate(event)
        ]

        episodes: list[CompositeEpisode] = []
        for event in primary_events:
            ts = parse_event_ts(event)
            if ts is None:
                continue
            if spec.require_room_occupancy and room_id not in event.context.occupied_rooms:
                continue
            delta = numeric_delta(event)
            if delta is None:
                continue
            if spec.primary.min_delta is not None and delta < spec.primary.min_delta:
                continue

            corroboration_matches: dict[str, tuple[str, ...]] = {}
            missing_required = False
            for signal in spec.corroborations:
                matches = tuple(
                    sorted(
                        {
                            subject_entity_id(candidate)
                            for candidate in corroboration_buckets.get(signal.name, [])
                            if within_window(ts, parse_event_ts(candidate), spec.correlation_window_s)
                            and _delta_satisfies(candidate, signal.min_delta)
                            and subject_entity_id(candidate)
                        }
                    )
                )
                corroboration_matches[signal.name] = matches
                if signal.required and not matches:
                    missing_required = True
            if missing_required:
                continue

            followup_entities = tuple(
                sorted(
                    {
                        subject_entity_id(candidate)
                        for candidate in followup_events
                        if within_followup(ts, parse_event_ts(candidate), spec.followup_window_s)
                        and _delta_satisfies(candidate, spec.followup.min_delta if spec.followup else None)
                        and subject_entity_id(candidate)
                    }
                )
            )

            episodes.append(
                CompositeEpisode(
                    room_id=room_id,
                    ts=ts,
                    primary_entity=subject_entity_id(event),
                    primary_delta=delta,
                    corroboration_matches=corroboration_matches,
                    followup_entities=followup_entities,
                )
            )

        return episodes


def parse_event_ts(raw_event_or_ts: HeimaEvent | str | None) -> datetime | None:
    raw = raw_event_or_ts.ts if isinstance(raw_event_or_ts, HeimaEvent) else raw_event_or_ts
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def numeric_delta(event: HeimaEvent) -> float | None:
    try:
        old = float(event.data.get("old_state"))
        new = float(event.data.get("new_state"))
    except (TypeError, ValueError):
        return None
    return new - old


def subject_entity_id(event: HeimaEvent) -> str:
    return str(event.subject_id or event.data.get("entity_id") or "")


def within_window(origin: datetime, candidate: datetime | None, seconds: int) -> bool:
    if candidate is None:
        return False
    return abs((candidate - origin).total_seconds()) <= seconds


def within_followup(origin: datetime, candidate: datetime | None, seconds: int) -> bool:
    if candidate is None:
        return False
    delta = (candidate - origin).total_seconds()
    return 0 <= delta <= seconds


def _delta_satisfies(event: HeimaEvent, min_delta: float | None) -> bool:
    if min_delta is None:
        return True
    delta = numeric_delta(event)
    return delta is not None and delta >= min_delta
