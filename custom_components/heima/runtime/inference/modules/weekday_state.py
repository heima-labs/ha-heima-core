"""WeekdayStateModule — learns P(house_state | weekday, hour_bucket)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..base import HeimaLearningModule, InferenceContext, SnapshotHistoryStore
from ..signals import HouseStateSignal, Importance

_MIN_SUPPORT = 10
_CONFIDENCE_THRESHOLD = 0.40


class WeekdayStateModule(HeimaLearningModule):
    """Emits HouseStateSignal based on historical state patterns per weekday/hour slot."""

    module_id = "weekday_state"

    def __init__(
        self,
        *,
        min_support: int = _MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        # (weekday, hour_bucket) -> (best_state, total, probability)
        self._slots: dict[tuple[int, int], tuple[str, int, float]] = {}
        self._ready = False

    async def analyze(self, store: SnapshotHistoryStore) -> None:
        """Compute P(house_state | weekday, hour_bucket) from snapshot history."""
        counts: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for snapshot in store.snapshots():
            if not snapshot.house_state:
                continue
            key = (snapshot.weekday, snapshot.minute_of_day // 60)
            counts[key][snapshot.house_state] += 1

        self._slots = {}
        for key, state_counts in counts.items():
            total = sum(state_counts.values())
            best_state = max(state_counts, key=lambda s: state_counts[s])
            self._slots[key] = (best_state, total, state_counts[best_state] / total)

        self._ready = True

    def infer(self, context: InferenceContext) -> list[HouseStateSignal]:
        if not self._ready:
            return []
        slot = self._slots.get((context.weekday, context.minute_of_day // 60))
        if slot is None:
            return []
        best_state, total, probability = slot
        if total < self._min_support:
            return []
        confidence = probability * min(1.0, total / self._min_support)
        if confidence < self._confidence_threshold:
            return []
        return [
            HouseStateSignal(
                source_id=self.module_id,
                confidence=confidence,
                importance=Importance.OBSERVE,
                ttl_s=600,
                label=f"{best_state} wd={context.weekday} h={context.minute_of_day // 60}",
                predicted_state=best_state,
            )
        ]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "slot_count": len(self._slots),
            "min_support": self._min_support,
            "confidence_threshold": self._confidence_threshold,
        }
