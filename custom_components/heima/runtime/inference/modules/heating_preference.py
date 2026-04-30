"""HeatingPreferenceModule — learns preferred_setpoint[house_state]."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..base import HeimaLearningModule, InferenceContext
from ..signals import HeatingSignal, Importance

_MIN_SUPPORT = 10


class HeatingPreferenceModule(HeimaLearningModule):
    """Emits HeatingSignal with the mean preferred setpoint for the current house state."""

    module_id = "heating_preference"

    def __init__(self) -> None:
        # house_state -> (mean_setpoint, count)
        self._model: dict[str, tuple[float, int]] = {}
        self._ready = False

    async def analyze(self, store: object) -> None:
        """Compute mean setpoint per house_state from snapshot history."""
        buckets: dict[str, list[float]] = defaultdict(list)
        for snapshot in store.snapshots():  # type: ignore[union-attr]
            if snapshot.heating_setpoint is not None and snapshot.house_state:
                buckets[snapshot.house_state].append(snapshot.heating_setpoint)

        self._model = {state: (sum(vals) / len(vals), len(vals)) for state, vals in buckets.items()}
        self._ready = True

    def infer(self, context: InferenceContext) -> list[HeatingSignal]:
        if not self._ready:
            return []
        entry = self._model.get(context.previous_house_state)
        if entry is None:
            return []
        mean_setpoint, support = entry
        if support < _MIN_SUPPORT:
            return []
        confidence = min(1.0, support / _MIN_SUPPORT)
        if confidence < 0.40:
            return []
        return [
            HeatingSignal(
                source_id=self.module_id,
                confidence=confidence,
                importance=_importance(confidence),
                ttl_s=600,
                label=f"setpoint={mean_setpoint:.1f} for {context.previous_house_state}",
                predicted_setpoint=mean_setpoint,
                house_state_context=context.previous_house_state,
            )
        ]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "state_count": len(self._model),
        }


def _importance(confidence: float) -> Importance:
    if confidence > 0.80:
        return Importance.ASSERT
    if confidence >= 0.60:
        return Importance.SUGGEST
    return Importance.OBSERVE
