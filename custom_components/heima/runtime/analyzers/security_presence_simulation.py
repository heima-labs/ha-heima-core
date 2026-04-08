"""Learned proposal bootstrap for the security presence simulation family."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..event_store import EventStore
from .base import ReactionProposal
from .learning_diagnostics import build_learning_diagnostics
from .policy import SecurityPresenceSimulationLearningPolicy

_MIN_OCCURRENCES = 4
_MIN_WEEKS = 2
_MIN_EVENING_MIN = 16 * 60
_MAX_EVENING_MIN = 23 * 60 + 30
_CLUSTER_WINDOW_MIN = 20
_MAX_SOURCE_PROFILES = 8


@dataclass
class _EntityPattern:
    entity_id: str
    room_id: str
    weekday: int
    action: str
    scheduled_min: int
    observations_count: int
    weeks_observed: int
    last_observed_at: str
    brightness: int | None
    color_temp_kelvin: int | None
    rgb_color: list[int] | None

    def as_entity_step(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "action": self.action,
            "brightness": self.brightness if self.action == "on" else None,
            "color_temp_kelvin": self.color_temp_kelvin if self.action == "on" else None,
            "rgb_color": self.rgb_color if self.action == "on" else None,
        }


@dataclass
class SecurityPresenceSimulationAnalyzer:
    """Emit one bounded learned proposal for vacation presence simulation."""

    analyzer_id: str = "SecurityPresenceSimulationAnalyzer"
    min_weeks: int = _MIN_WEEKS
    min_occurrences: int = _MIN_OCCURRENCES
    policy: SecurityPresenceSimulationLearningPolicy | None = None

    def __post_init__(self) -> None:
        if self.policy is None:
            return
        self.min_weeks = int(self.policy.min_weeks)
        self.min_occurrences = int(self.policy.min_occurrences)

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        raw = await event_store.async_query(event_type="lighting")
        events = [event for event in raw if _is_security_presence_source_event(event)]
        if not events:
            return []

        patterns = _build_entity_patterns(events, self.min_weeks, self.min_occurrences)
        if not patterns:
            return []

        source_profiles = _build_source_profiles(patterns)
        if not _has_sufficient_profile_mix(source_profiles):
            return []

        limited_profiles = source_profiles[:_MAX_SOURCE_PROFILES]
        rooms = sorted(
            {
                str(item.get("room_id") or "").strip()
                for item in limited_profiles
                if str(item.get("room_id") or "").strip()
            }
        )
        entities = sorted(
            {
                str(step.get("entity_id") or "").strip()
                for item in limited_profiles
                for step in item.get("entity_steps", [])
                if str(step.get("entity_id") or "").strip()
            }
        )
        weekdays = sorted({int(item.get("weekday") or 0) for item in limited_profiles})
        action_kinds = sorted(
            {
                str(item.get("action_kind") or "").strip()
                for item in limited_profiles
                if str(item.get("action_kind") or "").strip()
            }
        )
        weeks_observed = min(int(item.get("weeks_observed") or 0) for item in limited_profiles)
        updated_at = max(str(item.get("updated_at") or "") for item in limited_profiles)
        confidence = _proposal_confidence(
            profile_count=len(limited_profiles),
            room_count=len(rooms),
            weeks_observed=weeks_observed,
            action_kinds=action_kinds,
        )
        room_label = ", ".join(rooms[:3])
        if len(rooms) > 3:
            room_label = f"{room_label}, +{len(rooms) - 3}"
        description = (
            f"Simulazione presenza vacation da {room_label}"
            if room_label
            else "Simulazione presenza vacation"
        )

        return [
            ReactionProposal(
                analyzer_id=self.analyzer_id,
                reaction_type="vacation_presence_simulation",
                description=description,
                confidence=confidence,
                suggested_reaction_config={
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "dynamic_policy": True,
                    "requires_dark_outside": True,
                    "skip_if_presence_detected": True,
                    "simulation_aggressiveness": _simulation_aggressiveness(limited_profiles),
                    "allowed_rooms": rooms,
                    "allowed_entities": entities,
                    "learned_source_profiles": limited_profiles,
                    "learned_source_profile_kind": "event_store_evening_lighting",
                    "learning_diagnostics": build_learning_diagnostics(
                        pattern_id="vacation_presence_simulation",
                        analyzer_id=self.analyzer_id,
                        reaction_type="vacation_presence_simulation",
                        plugin_family="security_presence_simulation",
                        source_profile_count=len(limited_profiles),
                        room_count=len(rooms),
                        rooms=rooms,
                        entity_count=len(entities),
                        weekdays=weekdays,
                        action_kinds=action_kinds,
                        weeks_observed=weeks_observed,
                        excluded_vacation=True,
                    ),
                },
                last_observed_at=updated_at,
                updated_at=updated_at,
                fingerprint=f"{self.analyzer_id}|vacation_presence_simulation|scope=home",
            )
        ]


def _is_security_presence_source_event(event: Any) -> bool:
    if getattr(event, "event_type", "") != "lighting":
        return False
    if getattr(event, "source", None) != "user":
        return False
    ctx = getattr(event, "context", None)
    if ctx is None:
        return False
    if str(getattr(ctx, "house_state", "") or "").strip() == "vacation":
        return False
    if int(getattr(ctx, "occupants_count", 0) or 0) <= 0:
        return False
    minute = int(getattr(ctx, "minute_of_day", 0) or 0)
    if minute < _MIN_EVENING_MIN or minute > _MAX_EVENING_MIN:
        return False
    data = dict(getattr(event, "data", {}) or {})
    entity_id = str(data.get("entity_id") or "").strip()
    room_id = str(data.get("room_id") or "").strip()
    action = str(data.get("action") or "").strip()
    return bool(entity_id and room_id and action in {"on", "off"})


def _build_entity_patterns(
    events: list[Any],
    min_weeks: int = _MIN_WEEKS,
    min_occurrences: int = _MIN_OCCURRENCES,
) -> list[_EntityPattern]:
    grouped: dict[tuple[str, str, str, int], list[Any]] = {}
    for event in events:
        data = dict(getattr(event, "data", {}) or {})
        room_id = str(data.get("room_id") or "").strip()
        entity_id = str(data.get("entity_id") or "").strip()
        action = str(data.get("action") or "").strip()
        weekday = int(getattr(getattr(event, "context", None), "weekday", 0) or 0)
        grouped.setdefault((room_id, entity_id, action, weekday), []).append(event)

    patterns: list[_EntityPattern] = []
    for (room_id, entity_id, action, weekday), group in grouped.items():
        if len(group) < min_occurrences:
            continue
        weeks_observed = _weeks_observed(group)
        if weeks_observed < min_weeks:
            continue
        minutes = sorted(int(event.context.minute_of_day) for event in group)
        median_min = minutes[len(minutes) // 2]
        last_observed_at = max(str(event.ts) for event in group)
        brightness = _median_int([dict(event.data).get("brightness") for event in group])
        color_temp = _median_int([dict(event.data).get("color_temp_kelvin") for event in group])
        rgb_color = _mode_rgb([dict(event.data).get("rgb_color") for event in group])
        patterns.append(
            _EntityPattern(
                entity_id=entity_id,
                room_id=room_id,
                weekday=weekday,
                action=action,
                scheduled_min=median_min,
                observations_count=len(group),
                weeks_observed=weeks_observed,
                last_observed_at=last_observed_at,
                brightness=brightness,
                color_temp_kelvin=color_temp,
                rgb_color=rgb_color,
            )
        )
    return patterns


def _build_source_profiles(patterns: list[_EntityPattern]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[_EntityPattern]] = {}
    for pattern in patterns:
        grouped.setdefault((pattern.room_id, pattern.weekday, pattern.action), []).append(pattern)

    profiles: list[dict[str, Any]] = []
    for (room_id, weekday, action), items in grouped.items():
        ordered = sorted(items, key=lambda item: item.scheduled_min)
        clusters: list[list[_EntityPattern]] = [[ordered[0]]]
        for item in ordered[1:]:
            if item.scheduled_min - clusters[-1][-1].scheduled_min <= _CLUSTER_WINDOW_MIN:
                clusters[-1].append(item)
            else:
                clusters.append([item])

        for cluster in clusters:
            cluster_mins = sorted(item.scheduled_min for item in cluster)
            scheduled_min = cluster_mins[len(cluster_mins) // 2]
            normalized = _normalize_cluster(cluster)
            updated_at = max(item.last_observed_at for item in normalized)
            observations_count = sum(item.observations_count for item in normalized)
            weeks_observed = min(item.weeks_observed for item in normalized)
            bucket = (scheduled_min // 30) * 30
            profiles.append(
                {
                    "reaction_id": f"learned:{room_id}:{weekday}:{bucket}:{action}",
                    "room_id": room_id,
                    "weekday": weekday,
                    "scheduled_min": scheduled_min,
                    "entity_steps": [item.as_entity_step() for item in normalized],
                    "action_kind": action,
                    "created_at": updated_at,
                    "updated_at": updated_at,
                    "observations_count": observations_count,
                    "weeks_observed": weeks_observed,
                }
            )

    return sorted(
        profiles,
        key=lambda item: (
            -int(item.get("weeks_observed") or 0),
            -int(item.get("observations_count") or 0),
            int(item.get("scheduled_min") or 0),
            str(item.get("reaction_id") or ""),
        ),
    )


def _normalize_cluster(cluster: list[_EntityPattern]) -> list[_EntityPattern]:
    by_entity: dict[str, list[_EntityPattern]] = {}
    for pattern in cluster:
        by_entity.setdefault(pattern.entity_id, []).append(pattern)

    normalized: list[_EntityPattern] = []
    for entity_id, patterns in by_entity.items():
        winner = max(
            patterns,
            key=lambda item: (item.observations_count, item.weeks_observed, item.last_observed_at),
        )
        normalized.append(winner)

    normalized.sort(key=lambda item: (item.entity_id, item.action, item.scheduled_min))
    return normalized


def _has_sufficient_profile_mix(source_profiles: list[dict[str, Any]]) -> bool:
    if len(source_profiles) < 2:
        return False
    rooms = {
        str(item.get("room_id") or "").strip()
        for item in source_profiles
        if str(item.get("room_id") or "").strip()
    }
    actions = {
        str(item.get("action_kind") or "").strip()
        for item in source_profiles
        if str(item.get("action_kind") or "").strip()
    }
    return len(rooms) >= 2 or actions == {"on", "off"}


def _proposal_confidence(
    *,
    profile_count: int,
    room_count: int,
    weeks_observed: int,
    action_kinds: list[str],
) -> float:
    confidence = 0.62
    confidence += min(0.12, profile_count * 0.02)
    confidence += min(0.08, room_count * 0.03)
    confidence += min(0.08, max(0, weeks_observed - 1) * 0.03)
    if {"on", "off"}.issubset(set(action_kinds)):
        confidence += 0.05
    return round(min(0.9, confidence), 3)


def _simulation_aggressiveness(source_profiles: list[dict[str, Any]]) -> str:
    room_count = len(
        {
            str(item.get("room_id") or "").strip()
            for item in source_profiles
            if str(item.get("room_id") or "").strip()
        }
    )
    if len(source_profiles) >= 6 and room_count >= 3:
        return "high"
    if len(source_profiles) <= 2:
        return "low"
    return "medium"


def _weeks_observed(events: list[Any]) -> int:
    weeks: set[tuple[int, int]] = set()
    for event in events:
        try:
            dt = datetime.fromisoformat(str(event.ts)).astimezone(UTC)
        except (TypeError, ValueError):
            continue
        iso = dt.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks)


def _median_int(values: list[Any]) -> int | None:
    nums = [int(value) for value in values if value is not None]
    if not nums:
        return None
    nums.sort()
    return nums[len(nums) // 2]


def _mode_rgb(values: list[Any]) -> list[int] | None:
    candidates = [
        tuple(value) for value in values if isinstance(value, (list, tuple)) and len(value) == 3
    ]
    if not candidates:
        return None
    counts: dict[tuple[int, int, int], int] = {}
    for candidate in candidates:
        counts[candidate] = counts.get(candidate, 0) + 1
    return list(max(counts, key=counts.get))
