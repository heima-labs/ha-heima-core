"""RoomStateCorrelationModule — learns P(house_state | occupied_room_pattern)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ..base import HeimaLearningModule, InferenceContext, SnapshotHistoryStore
from ..signals import HouseStateSignal, Importance

_MIN_SUPPORT = 15
_CONFIDENCE_THRESHOLD = 0.60


@dataclass(frozen=True)
class _RoomStateEntry:
    occupied_pattern: frozenset[str]
    predicted_state: str
    total: int
    count: int
    confidence: float


class RoomStateCorrelationModule(HeimaLearningModule):
    """Emits HouseStateSignal from historical occupied-room patterns."""

    module_id = "room_state_correlation"

    def __init__(
        self,
        *,
        min_support: int = _MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        self._model: dict[frozenset[str], _RoomStateEntry] = {}
        self._ready = False
        self._analyzed_snapshots = 0

    async def analyze(self, store: SnapshotHistoryStore) -> None:
        """Compute P(house_state | occupied_room_pattern) from snapshot history."""
        counts: dict[frozenset[str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        analyzed = 0

        for snapshot in store.snapshots():
            house_state = str(getattr(snapshot, "house_state", "") or "").strip()
            if not house_state:
                continue
            occupied_pattern = _occupied_pattern(getattr(snapshot, "room_occupancy", {}))
            if not occupied_pattern:
                continue
            counts[occupied_pattern][house_state] += 1
            analyzed += 1

        self._model = {}
        for pattern, state_counts in counts.items():
            total = sum(state_counts.values())
            predicted_state = max(state_counts, key=lambda state: state_counts[state])
            count = state_counts[predicted_state]
            self._model[pattern] = _RoomStateEntry(
                occupied_pattern=pattern,
                predicted_state=predicted_state,
                total=total,
                count=count,
                confidence=count / total if total > 0 else 0.0,
            )

        self._analyzed_snapshots = analyzed
        self._ready = True

    def infer(self, context: InferenceContext) -> list[HouseStateSignal]:
        """Emit a signal for the current occupied-room pattern when supported."""
        if not self._ready:
            return []
        pattern = _occupied_pattern(context.room_occupancy)
        if not pattern:
            return []
        entry = self._model.get(pattern)
        if entry is None:
            return []
        if entry.total < self._min_support:
            return []
        if entry.confidence < self._confidence_threshold:
            return []
        return [
            HouseStateSignal(
                source_id=self.module_id,
                confidence=entry.confidence,
                importance=Importance.SUGGEST,
                ttl_s=600,
                label=f"{entry.predicted_state} rooms={','.join(sorted(entry.occupied_pattern))}",
                predicted_state=entry.predicted_state,
            )
        ]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "pattern_count": len(self._model),
            "analyzed_snapshots": self._analyzed_snapshots,
            "min_support": self._min_support,
            "confidence_threshold": self._confidence_threshold,
        }


def _occupied_pattern(room_occupancy: Any) -> frozenset[str]:
    if not isinstance(room_occupancy, dict):
        return frozenset()
    return frozenset(
        str(room_id).strip()
        for room_id, occupied in room_occupancy.items()
        if bool(occupied) and str(room_id).strip()
    )
