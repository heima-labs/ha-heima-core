"""SignalRouter — groups, filters expired, and sorts inference signals by type."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from .signals import InferenceSignal

_LOG = logging.getLogger(__name__)


class SignalRouter:
    """Routes inference signals to per-type buckets for domain consumption.

    Accepts (signal, emit_time) pairs. Expired signals (age > ttl_s) are dropped.
    Each bucket is sorted by confidence descending, tie-broken by most conservative Importance.
    Logs WARNING when ≥ 2 signals in the same bucket exceed confidence 0.60 with different
    predicted values.
    """

    def route(
        self,
        signals: list[tuple[InferenceSignal, datetime]],
        now: datetime,
    ) -> dict[type, list[InferenceSignal]]:
        """Return fresh, sorted signal buckets grouped by signal subclass type."""
        buckets: dict[type, list[InferenceSignal]] = defaultdict(list)

        for signal, emit_time in signals:
            age_s = (now - emit_time).total_seconds()
            if age_s > signal.ttl_s:
                continue
            buckets[type(signal)].append(signal)

        result: dict[type, list[InferenceSignal]] = {}
        for signal_type, bucket in buckets.items():
            sorted_bucket = sorted(bucket, key=lambda s: (-s.confidence, s.importance.value))
            self._check_conflicts(signal_type, sorted_bucket)
            result[signal_type] = sorted_bucket

        return result

    @staticmethod
    def _predicted_value(signal: InferenceSignal) -> Any:
        for attr in (
            "predicted_state",
            "predicted_setpoint",
            "predicted_scene",
            "activity_name",
            "predicted_occupied",
        ):
            if hasattr(signal, attr):
                return getattr(signal, attr)
        return None

    def _check_conflicts(self, signal_type: type, signals: list[InferenceSignal]) -> None:
        high_conf = [s for s in signals if s.confidence >= 0.60]
        if len(high_conf) < 2:
            return
        predicted_values = {
            self._predicted_value(s) for s in high_conf if self._predicted_value(s) is not None
        }
        if len(predicted_values) >= 2:
            _LOG.warning(
                "SignalRouter: conflicting %s signals with confidence >= 0.60: %s",
                signal_type.__name__,
                [
                    (s.source_id, round(s.confidence, 3), self._predicted_value(s))
                    for s in high_conf
                ],
            )
