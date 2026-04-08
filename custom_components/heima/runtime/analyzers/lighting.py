"""Lighting pattern analyzer (P9) — entity-level detection + scene candidate grouping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..event_store import EventStore, HeimaEvent
from .base import ReactionProposal
from .learning_diagnostics import build_learning_diagnostics
from .policy import LightingLearningPolicy

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MIN_OCCURRENCES = 5
_MIN_WEEKS = 2
_SCENE_GROUP_WINDOW_MIN = 15  # max gap between entity scheduled_mins to merge into one scene
_MIN_ATTR_SAMPLES = _MIN_OCCURRENCES // 2  # min non-None values to trust an aggregated attribute
_MAX_IQR_MIN_FOR_MINIMAL_EVIDENCE = 30


@dataclass
class _EntityPattern:
    entity_id: str
    action: str
    weekday: int
    room_id: str
    scheduled_min: int
    confidence: float
    observations_count: int
    weeks_observed: int
    iqr_min: int
    brightness: int | None
    color_temp_kelvin: int | None
    rgb_color: list[int] | None

    def as_entity_step(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "action": self.action,
            "brightness": self.brightness,
            "color_temp_kelvin": self.color_temp_kelvin,
            "rgb_color": self.rgb_color,
        }


@dataclass
class LightingPatternAnalyzer:
    """Detect recurring lighting configurations per (room, weekday) from stored events.

    Three-phase algorithm:
      1. Entity-level pattern detection: per (entity_id, action, weekday)
      2. Scene candidate grouping: entities in same room with similar scheduled_min
      3. One ReactionProposal per scene candidate
    """

    min_weeks: int = _MIN_WEEKS
    min_occurrences: int = _MIN_OCCURRENCES
    policy: LightingLearningPolicy | None = None

    def __post_init__(self) -> None:
        if self.policy is None:
            return
        self.min_weeks = int(self.policy.min_weeks)
        self.min_occurrences = int(self.policy.min_occurrences)

    @property
    def analyzer_id(self) -> str:
        return "LightingPatternAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        raw = await event_store.async_query(event_type="lighting")
        events: list[HeimaEvent] = [
            e for e in raw if isinstance(e, HeimaEvent) and e.source == "user"
        ]
        if not events:
            return []

        # ------------------------------------------------------------------
        # Phase 1 — entity-level pattern detection
        # ------------------------------------------------------------------
        entity_groups: dict[tuple[str, str, int], list[HeimaEvent]] = {}
        for e in events:
            entity_id = e.data.get("entity_id", "")
            action = e.data.get("action", "")
            weekday = e.context.weekday
            if not entity_id or action not in ("on", "off"):
                continue
            entity_groups.setdefault((entity_id, action, weekday), []).append(e)

        patterns: list[_EntityPattern] = []
        for (entity_id, action, weekday), group in entity_groups.items():
            if len(group) < self.min_occurrences:
                continue
            if not _spans_min_weeks(group, self.min_weeks):
                continue

            room_id = group[0].data.get("room_id", "")
            if not room_id:
                continue

            samples = sorted(e.context.minute_of_day for e in group)
            n = len(samples)
            median = samples[n // 2]
            iqr = samples[(3 * n) // 4] - samples[n // 4]
            weeks_observed = _weeks_observed(group)
            if _is_minimal_evidence_group(
                len(group), weeks_observed, iqr, self.min_weeks, self.min_occurrences
            ):
                continue
            base_confidence = max(0.3, 1.0 - iqr / 120.0)
            evidence_factor = min(1.0, len(group) / 8.0)
            weeks_factor = min(1.0, weeks_observed / 3.0)
            confidence = round(
                max(
                    0.3,
                    base_confidence * (0.85 + 0.15 * evidence_factor) * (0.9 + 0.1 * weeks_factor),
                ),
                3,
            )

            brightness = _median_int([e.data.get("brightness") for e in group])
            color_temp = _median_int([e.data.get("color_temp_kelvin") for e in group])
            rgb = _mode_rgb([e.data.get("rgb_color") for e in group])

            patterns.append(
                _EntityPattern(
                    entity_id=entity_id,
                    action=action,
                    weekday=weekday,
                    room_id=room_id,
                    scheduled_min=median,
                    confidence=float(confidence),
                    observations_count=len(group),
                    weeks_observed=weeks_observed,
                    iqr_min=iqr,
                    brightness=brightness if action == "on" else None,
                    color_temp_kelvin=color_temp if action == "on" else None,
                    rgb_color=rgb if action == "on" else None,
                )
            )

        if not patterns:
            return []

        # ------------------------------------------------------------------
        # Phase 2 — scene candidate grouping: (room_id, weekday) → clusters
        # ------------------------------------------------------------------
        room_weekday: dict[tuple[str, int], list[_EntityPattern]] = {}
        for p in patterns:
            room_weekday.setdefault((p.room_id, p.weekday), []).append(p)

        proposals: list[ReactionProposal] = []
        for (room_id, weekday), room_patterns in room_weekday.items():
            sorted_patterns = sorted(room_patterns, key=lambda p: p.scheduled_min)

            # Gap-based clustering
            clusters: list[list[_EntityPattern]] = [[sorted_patterns[0]]]
            for p in sorted_patterns[1:]:
                if p.scheduled_min - clusters[-1][-1].scheduled_min <= _SCENE_GROUP_WINDOW_MIN:
                    clusters[-1].append(p)
                else:
                    clusters.append([p])

            # ------------------------------------------------------------------
            # Phase 3 — one proposal per cluster
            # ------------------------------------------------------------------
            for cluster in clusters:
                cluster_mins = [p.scheduled_min for p in cluster]
                n = len(cluster_mins)
                scheduled_min = sorted(cluster_mins)[n // 2]
                normalized_cluster = _normalize_cluster_patterns(
                    cluster, scheduled_min=scheduled_min
                )
                confidence = sum(p.confidence for p in normalized_cluster) / len(normalized_cluster)
                entity_steps = [p.as_entity_step() for p in normalized_cluster]
                window_half_min = _cluster_window_half_min(normalized_cluster)

                # Lifecycle identity uses a coarser 30-minute bucket to avoid proposal churn.
                fp_min = (scheduled_min // 30) * 30
                fingerprint = (
                    f"{self.analyzer_id}|lighting_scene_schedule|{room_id}|{weekday}|{fp_min}"
                )

                proposals.append(
                    ReactionProposal(
                        analyzer_id=self.analyzer_id,
                        reaction_type="lighting_scene_schedule",
                        description=_describe(room_id, weekday, scheduled_min, entity_steps),
                        confidence=round(confidence, 3),
                        suggested_reaction_config={
                            "reaction_class": "LightingScheduleReaction",
                            "room_id": room_id,
                            "weekday": weekday,
                            "scheduled_min": scheduled_min,
                            "window_half_min": window_half_min,
                            "house_state_filter": None,
                            "entity_steps": entity_steps,
                            "learning_diagnostics": build_learning_diagnostics(
                                pattern_id="lighting_scene_schedule",
                                analyzer_id=self.analyzer_id,
                                reaction_type="lighting_scene_schedule",
                                plugin_family="lighting",
                                room_id=room_id,
                                weekday=weekday,
                                cluster_entities=sorted(
                                    step.get("entity_id", "")
                                    for step in entity_steps
                                    if step.get("entity_id")
                                ),
                                observations_count=sum(
                                    pattern.observations_count for pattern in normalized_cluster
                                ),
                                weeks_observed=min(
                                    pattern.weeks_observed for pattern in normalized_cluster
                                ),
                                iqr_min=max(pattern.iqr_min for pattern in normalized_cluster),
                                scheduled_min=scheduled_min,
                                entity_steps_count=len(entity_steps),
                            ),
                        },
                        fingerprint=fingerprint,
                    )
                )

        return proposals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spans_min_weeks(events: list[HeimaEvent], min_weeks: int = _MIN_WEEKS) -> bool:
    return _weeks_observed(events) >= min_weeks


def _is_minimal_evidence_group(
    observations_count: int,
    weeks_observed: int,
    iqr_min: int,
    min_weeks: int = _MIN_WEEKS,
    min_occurrences: int = _MIN_OCCURRENCES,
) -> bool:
    return (
        observations_count <= min_occurrences
        and weeks_observed <= min_weeks
        and iqr_min > _MAX_IQR_MIN_FOR_MINIMAL_EVIDENCE
    )


def _weeks_observed(events: list[HeimaEvent]) -> int:
    weeks: set[tuple[int, int]] = set()
    for e in events:
        try:
            dt = datetime.fromisoformat(e.ts).astimezone(UTC)
            iso = dt.isocalendar()
            weeks.add((iso.year, iso.week))
        except (ValueError, TypeError):
            pass
    return len(weeks)


def _median_int(values: list) -> int | None:
    nums = [int(v) for v in values if v is not None]
    if len(nums) < _MIN_ATTR_SAMPLES:
        return None
    nums.sort()
    return nums[len(nums) // 2]


def _mode_rgb(values: list) -> list[int] | None:
    candidates = [tuple(v) for v in values if isinstance(v, (list, tuple)) and len(v) == 3]
    if len(candidates) < _MIN_ATTR_SAMPLES:
        return None
    counts: dict[tuple, int] = {}
    for c in candidates:
        counts[c] = counts.get(c, 0) + 1
    mode = max(counts, key=lambda k: counts[k])
    return list(mode)


def _hhmm(minute_of_day: int) -> str:
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def _normalize_cluster_patterns(
    cluster: list[_EntityPattern], *, scheduled_min: int
) -> list[_EntityPattern]:
    """Collapse duplicate entity candidates inside a scene and order them deterministically."""
    by_entity: dict[str, list[_EntityPattern]] = {}
    for pattern in cluster:
        by_entity.setdefault(pattern.entity_id, []).append(pattern)

    normalized: list[_EntityPattern] = []
    for entity_id, patterns in by_entity.items():
        winner = min(
            patterns,
            key=lambda p: (
                abs(p.scheduled_min - scheduled_min),
                -p.observations_count,
                -p.confidence,
                p.action,
                p.entity_id,
            ),
        )
        normalized.append(winner)

    normalized.sort(key=lambda p: (p.entity_id, p.action, p.scheduled_min))
    return normalized


def _describe(room_id: str, weekday: int, scheduled_min: int, entity_steps: list[dict]) -> str:
    parts = []
    for s in entity_steps:
        name = s["entity_id"].split(".")[-1]
        if s["action"] == "on":
            attrs = []
            if s.get("brightness") is not None:
                attrs.append(f"{s['brightness']}bri")
            if s.get("color_temp_kelvin") is not None:
                attrs.append(f"{s['color_temp_kelvin']}K")
            suffix = f" ({', '.join(attrs)})" if attrs else ""
            parts.append(f"{name} on{suffix}")
        else:
            parts.append(f"{name} off")
    return f"{room_id}: {_WEEKDAY_NAMES[weekday]} ~{_hhmm(scheduled_min)} — " + ", ".join(parts)


def _cluster_window_half_min(cluster: list[_EntityPattern]) -> int:
    max_iqr = max((int(p.iqr_min) for p in cluster), default=0)
    if max_iqr <= 5:
        return 5
    if max_iqr <= 15:
        return 10
    return 15
