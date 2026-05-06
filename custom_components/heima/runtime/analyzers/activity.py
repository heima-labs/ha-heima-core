"""Composite activity discovery analyzer."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import combinations
from typing import Any

from ..inference import HouseSnapshot, SnapshotStore
from ..plugin_contracts import BehaviorFinding
from ..proposal_engine import ActivityProposal

MIN_COOCCURRENCES = 10
MIN_DISTINCT_DAYS = 3
MIN_PATTERN_SIZE = 2
MAX_PATTERN_SIZE = 2
DOMINANCE_THRESHOLD = 0.60
MAX_REPRESENTATIVE_TS = 5


@dataclass
class _PatternStats:
    occurrence_count: int = 0
    distinct_days: set[str] = field(default_factory=set)
    representative_ts: list[str] = field(default_factory=list)
    room_counts: Counter[str] = field(default_factory=Counter)
    hour_counts: Counter[int] = field(default_factory=Counter)


class ActivityAnalyzer:
    """Discover composite activity candidates from persisted activity snapshots."""

    analyzer_id = "ActivityAnalyzer"

    def __init__(
        self,
        snapshot_store: SnapshotStore,
        *,
        min_cooccurrences: int = MIN_COOCCURRENCES,
        min_distinct_days: int = MIN_DISTINCT_DAYS,
        max_pattern_size: int = MAX_PATTERN_SIZE,
    ) -> None:
        self._snapshot_store = snapshot_store
        self._min_cooccurrences = max(1, int(min_cooccurrences))
        self._min_distinct_days = max(1, int(min_distinct_days))
        self._max_pattern_size = max(MIN_PATTERN_SIZE, int(max_pattern_size))

    async def analyze(
        self,
        event_store: Any,  # noqa: ARG002
        snapshot_store: Any | None = None,  # noqa: ARG002
    ) -> list[BehaviorFinding]:
        """Return activity findings using the injected SnapshotStore."""
        stats = self._collect_stats(self._snapshot_store.snapshots())
        findings: list[BehaviorFinding] = []
        for pattern, pattern_stats in sorted(stats.items()):
            if pattern_stats.occurrence_count < self._min_cooccurrences:
                continue
            if len(pattern_stats.distinct_days) < self._min_distinct_days:
                continue
            proposal = ActivityProposal(
                activity_name="_".join(pattern),
                primitive_pattern=frozenset(pattern),
                context_conditions=_dominant_context_conditions(pattern_stats),
                occurrence_count=pattern_stats.occurrence_count,
                confidence=1.0,
                representative_ts=list(pattern_stats.representative_ts),
            )
            findings.append(
                BehaviorFinding(
                    kind="activity",
                    analyzer_id=self.analyzer_id,
                    description=(
                        f"Composite activity '{proposal.activity_name}' observed "
                        f"{proposal.occurrence_count} times across "
                        f"{len(pattern_stats.distinct_days)} days."
                    ),
                    confidence=proposal.confidence,
                    payload=proposal,
                )
            )
        return findings

    def _collect_stats(
        self,
        snapshots: list[HouseSnapshot] | tuple[HouseSnapshot, ...],
    ) -> dict[tuple[str, ...], _PatternStats]:
        stats: dict[tuple[str, ...], _PatternStats] = defaultdict(_PatternStats)
        for snapshot in snapshots:
            activities = tuple(
                sorted({_token(item) for item in snapshot.detected_activities if _token(item)})
            )
            if len(activities) < MIN_PATTERN_SIZE:
                continue
            max_size = min(self._max_pattern_size, len(activities))
            for size in range(MIN_PATTERN_SIZE, max_size + 1):
                for pattern in combinations(activities, size):
                    entry = stats[tuple(pattern)]
                    entry.occurrence_count += 1
                    day_key = _day_key(snapshot.ts)
                    if day_key:
                        entry.distinct_days.add(day_key)
                    if len(entry.representative_ts) < MAX_REPRESENTATIVE_TS:
                        entry.representative_ts.append(snapshot.ts)
                    for room_id, occupied in snapshot.room_occupancy.items():
                        if occupied:
                            entry.room_counts[_token(room_id)] += 1
                    entry.hour_counts[int(snapshot.minute_of_day) // 60] += 1
        return dict(stats)


def _dominant_context_conditions(stats: _PatternStats) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    room_id = _dominant_item(stats.room_counts, stats.occurrence_count)
    if room_id is not None:
        conditions["room_id"] = room_id
    hour = _dominant_item(stats.hour_counts, stats.occurrence_count)
    if hour is not None:
        conditions["hour_range"] = [int(hour), int(hour) + 1]
    return conditions


def _dominant_item(counts: Counter[Any], total: int) -> Any | None:
    if total <= 0 or not counts:
        return None
    item, count = counts.most_common(1)[0]
    if count / total >= DOMINANCE_THRESHOLD:
        return item
    return None


def _day_key(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).date().isoformat()


def _token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")
