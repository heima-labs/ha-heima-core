"""Shower activity detector."""

from __future__ import annotations

import time
from typing import Callable

from ..domains.activity_domain import ActivityDetection
from ..normalization import NormalizedObservation
from ..state_store import CanonicalState
from .power_media import _BaseActivityDetector, _coerce_float


class ShowerRunningDetector(_BaseActivityDetector):
    """Detect shower activity from bathroom humidity and positive rate of change."""

    activity_name = "shower_running"
    default_candidate_period_s = 60.0
    default_grace_period_s = 300.0

    def __init__(
        self,
        *,
        entity_id: str | None = None,
        room_id: str | None = None,
        humidity_threshold: float = 65.0,
        min_rate_per_min: float = 0.1,
        candidate_period_s: float | None = None,
        grace_period_s: float | None = None,
        now_provider: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            room_id=room_id,
            candidate_period_s=candidate_period_s,
            grace_period_s=grace_period_s,
        )
        self.humidity_threshold = float(humidity_threshold)
        self.min_rate_per_min = float(min_rate_per_min)
        self._now_provider = now_provider or time.monotonic
        self._last_humidity: float | None = None
        self._last_ts: float | None = None

    def detect(
        self, observation: NormalizedObservation, canonical_state: CanonicalState
    ) -> ActivityDetection | None:
        del canonical_state
        if not self._matches(observation):
            return None
        humidity = _coerce_float(
            observation.raw_state if observation.raw_state is not None else observation.state
        )
        if humidity is None:
            return None
        now = self._now_provider()
        previous_humidity = self._last_humidity
        previous_ts = self._last_ts
        self._last_humidity = humidity
        self._last_ts = now
        if previous_humidity is None or previous_ts is None:
            return None
        elapsed_s = max(0.0, now - previous_ts)
        if elapsed_s <= 0:
            return None
        rate_per_min = ((humidity - previous_humidity) / elapsed_s) * 60.0
        if humidity < self.humidity_threshold or rate_per_min < self.min_rate_per_min:
            return None
        return ActivityDetection(
            activity_name=self.activity_name,
            confidence=max(0.0, min(1.0, observation.confidence / 100)),
            room_id=self.room_id,
            context={
                "activity.entity_id": str(observation.source_entity_id or ""),
                "activity.reason": "humidity_rising",
                "activity.humidity": humidity,
                "activity.humidity_rate_per_min": rate_per_min,
            },
        )


__all__ = ["ShowerRunningDetector"]
