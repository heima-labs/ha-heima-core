"""ActivityInferenceModule — approved composite activity signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ...proposal_engine import ActivityProposal
from ..approval_store import activity_context_key
from ..base import HeimaLearningModule, InferenceContext
from ..signals import ActivitySignal, Importance

_MIN_SUPPORT = 10
_CONFIDENCE_THRESHOLD = 0.60


@dataclass(frozen=True)
class _ApprovedActivityPattern:
    activity_name: str
    primitive_pattern: frozenset[str]
    context_conditions: dict[str, Any]
    context_key: str


@dataclass(frozen=True)
class _ModelEntry:
    support: int
    total: int
    confidence: float


class ActivityInferenceModule(HeimaLearningModule):
    """Emits ActivitySignal for approved composite activity patterns only."""

    module_id = "activity_inference"

    def __init__(
        self,
        *,
        min_support: int = _MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        self._approved_patterns: dict[str, _ApprovedActivityPattern] = {}
        self._model: dict[str, _ModelEntry] = {}
        self._ready = False
        self._analyzed_snapshots = 0

    def sync_approved_proposals(self, proposals: Sequence[ActivityProposal]) -> None:
        """Replace the in-memory approved proposal snapshot used by sync inference."""
        approved: dict[str, _ApprovedActivityPattern] = {}
        for proposal in proposals:
            pattern = _normalized_pattern(proposal.primitive_pattern)
            if not proposal.activity_name or not pattern:
                continue
            context_key = activity_context_key(
                activity_name=proposal.activity_name,
                primitive_pattern=pattern,
                context_conditions=proposal.context_conditions,
            )
            approved[context_key] = _ApprovedActivityPattern(
                activity_name=_token(proposal.activity_name),
                primitive_pattern=pattern,
                context_conditions=dict(proposal.context_conditions),
                context_key=context_key,
            )
        self._approved_patterns = approved
        self._model = {
            key: entry for key, entry in self._model.items() if key in self._approved_patterns
        }

    async def analyze(self, store: object) -> None:
        """Compute support/confidence for approved composite activity proposals."""
        support: dict[str, int] = {key: 0 for key in self._approved_patterns}
        totals: dict[str, int] = {key: 0 for key in self._approved_patterns}
        analyzed = 0

        for snapshot in store.snapshots():  # type: ignore[union-attr]
            active_set = _normalized_pattern(getattr(snapshot, "detected_activities", ()))
            if not active_set:
                continue
            analyzed += 1
            for key, pattern in self._approved_patterns.items():
                if not pattern.primitive_pattern.issubset(active_set):
                    continue
                totals[key] += 1
                if _context_matches_snapshot(snapshot, pattern.context_conditions):
                    support[key] += 1

        self._model = {}
        for key, pattern_support in support.items():
            total = totals.get(key, 0)
            confidence = pattern_support / total if total > 0 else 0.0
            self._model[key] = _ModelEntry(
                support=pattern_support,
                total=total,
                confidence=confidence,
            )

        self._analyzed_snapshots = analyzed
        self._ready = True

    def infer(self, context: InferenceContext) -> list[ActivitySignal]:
        if not self._ready or not self._approved_patterns:
            return []

        current_set = _normalized_pattern(context.previous_activity_names)
        if not current_set:
            return []

        signals: list[ActivitySignal] = []
        for key, pattern in self._approved_patterns.items():
            if not pattern.primitive_pattern.issubset(current_set):
                continue
            if not _context_matches_now(context, pattern.context_conditions):
                continue
            entry = self._model.get(key)
            if entry is None:
                continue
            if entry.support < self._min_support:
                continue
            if entry.confidence < self._confidence_threshold:
                continue
            signals.append(
                ActivitySignal(
                    source_id=self.module_id,
                    confidence=entry.confidence,
                    importance=_importance(entry.confidence),
                    ttl_s=600,
                    label=pattern.activity_name,
                    activity_name=pattern.activity_name,
                    room_id=_room_id(pattern.context_conditions),
                    context={
                        "approval_context_key": pattern.context_key,
                        "primitive_pattern": sorted(pattern.primitive_pattern),
                        "support": entry.support,
                        "total": entry.total,
                    },
                )
            )

        return sorted(signals, key=lambda signal: (-signal.confidence, signal.activity_name))

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "approved_patterns": len(self._approved_patterns),
            "model_entries": len(self._model),
            "analyzed_snapshots": self._analyzed_snapshots,
            "min_support": self._min_support,
            "confidence_threshold": self._confidence_threshold,
        }


def _context_matches_snapshot(snapshot: Any, conditions: dict[str, Any]) -> bool:
    if not conditions:
        return True
    room_id = conditions.get("room_id")
    if room_id is not None:
        rooms = getattr(snapshot, "room_occupancy", {})
        if _token(room_id) not in {_token(room) for room, occupied in rooms.items() if occupied}:
            return False
    hour_range = conditions.get("hour_range")
    if hour_range is not None and not _hour_in_range(
        getattr(snapshot, "minute_of_day", 0), hour_range
    ):
        return False
    weekday_filter = conditions.get("weekday_filter")
    if weekday_filter is not None and not _weekday_matches(
        getattr(snapshot, "weekday", -1), weekday_filter
    ):
        return False
    return True


def _context_matches_now(context: InferenceContext, conditions: dict[str, Any]) -> bool:
    if not conditions:
        return True
    room_id = conditions.get("room_id")
    if room_id is not None:
        occupied_rooms = {
            _token(room) for room, occupied in context.room_occupancy.items() if occupied
        }
        if _token(room_id) not in occupied_rooms:
            return False
    hour_range = conditions.get("hour_range")
    if hour_range is not None and not _hour_in_range(context.minute_of_day, hour_range):
        return False
    weekday_filter = conditions.get("weekday_filter")
    if weekday_filter is not None and not _weekday_matches(context.weekday, weekday_filter):
        return False
    return True


def _hour_in_range(minute_of_day: int, raw: Any) -> bool:
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        return False
    try:
        start_hour = int(raw[0])
        end_hour = int(raw[1])
    except (TypeError, ValueError):
        return False
    hour = int(minute_of_day) // 60
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _weekday_matches(weekday: int, raw: Any) -> bool:
    if isinstance(raw, dict):
        raw = raw.get("days")
    if not isinstance(raw, list | tuple | set | frozenset):
        return False
    values = {_weekday_value(item) for item in raw}
    return int(weekday) in values


def _weekday_value(value: Any) -> int:
    weekday_names = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    token = _token(value)
    if token in weekday_names:
        return weekday_names[token]
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _room_id(conditions: dict[str, Any]) -> str | None:
    room_id = conditions.get("room_id")
    if room_id is None:
        return None
    token = _token(room_id)
    return token or None


def _importance(confidence: float) -> Importance:
    if confidence > 0.80:
        return Importance.ASSERT
    if confidence >= 0.60:
        return Importance.SUGGEST
    return Importance.OBSERVE


def _normalized_pattern(values: Any) -> frozenset[str]:
    if not isinstance(values, list | tuple | set | frozenset):
        return frozenset()
    return frozenset(_token(value) for value in values if _token(value))


def _token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")
