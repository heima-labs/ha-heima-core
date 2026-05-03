"""Primitive power and media activity detectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domains.activity_domain import ActivityDetection
from ..normalization import NormalizedObservation
from ..state_store import CanonicalState

_ON_STATES = {"on", "running", "active", "playing", "paused"}


@dataclass(frozen=True)
class _Binding:
    entity_id: str
    room_id: str | None = None

    @classmethod
    def from_entity(cls, entity_id: str | None, room_id: str | None = None) -> "_Binding | None":
        clean = str(entity_id or "").strip()
        if not clean:
            return None
        return cls(entity_id=clean, room_id=room_id)


class _BaseActivityDetector:
    activity_name = ""
    default_candidate_period_s = 0.0
    default_grace_period_s = 0.0

    def __init__(
        self,
        *,
        entity_id: str | None = None,
        room_id: str | None = None,
        candidate_period_s: float | None = None,
        grace_period_s: float | None = None,
    ) -> None:
        self._binding = _Binding.from_entity(entity_id, room_id)
        self._candidate_period_s = (
            self.default_candidate_period_s
            if candidate_period_s is None
            else float(candidate_period_s)
        )
        self._grace_period_s = (
            self.default_grace_period_s if grace_period_s is None else float(grace_period_s)
        )

    @property
    def room_id(self) -> str | None:
        return self._binding.room_id if self._binding is not None else None

    @property
    def entity_id(self) -> str | None:
        return self._binding.entity_id if self._binding is not None else None

    @property
    def candidate_period_s(self) -> float:
        return self._candidate_period_s

    @property
    def grace_period_s(self) -> float:
        return self._grace_period_s

    def _matches(self, observation: NormalizedObservation) -> bool:
        return (
            self._binding is not None
            and observation.available
            and not observation.stale
            and observation.source_entity_id == self._binding.entity_id
        )

    def _detection(self, observation: NormalizedObservation, *, reason: str) -> ActivityDetection:
        return ActivityDetection(
            activity_name=self.activity_name,
            confidence=max(0.0, min(1.0, observation.confidence / 100)),
            room_id=self.room_id,
            context={
                "activity.entity_id": str(observation.source_entity_id or ""),
                "activity.reason": reason,
            },
        )


class _PowerThresholdDetector(_BaseActivityDetector):
    default_threshold_w = 0.0

    def __init__(
        self,
        *,
        entity_id: str | None = None,
        room_id: str | None = None,
        threshold_w: float | None = None,
        candidate_period_s: float | None = None,
        grace_period_s: float | None = None,
    ) -> None:
        super().__init__(
            entity_id=entity_id,
            room_id=room_id,
            candidate_period_s=candidate_period_s,
            grace_period_s=grace_period_s,
        )
        self.threshold_w = self.default_threshold_w if threshold_w is None else float(threshold_w)

    def detect(
        self, observation: NormalizedObservation, canonical_state: CanonicalState
    ) -> ActivityDetection | None:
        del canonical_state
        if not self._matches(observation):
            return None
        power = _coerce_float(
            observation.raw_state if observation.raw_state is not None else observation.state
        )
        if power is None or power < self.threshold_w:
            return None
        return self._detection(observation, reason=f"power_gte_{self.threshold_w:g}w")


class StoveOnDetector(_PowerThresholdDetector):
    """Detect stove usage from a configured power sensor."""

    activity_name = "stove_on"
    default_threshold_w = 200.0
    default_candidate_period_s = 5.0
    default_grace_period_s = 30.0


class OvenOnDetector(_PowerThresholdDetector):
    """Detect oven usage from a configured power sensor."""

    activity_name = "oven_on"
    default_threshold_w = 500.0
    default_candidate_period_s = 10.0
    default_grace_period_s = 120.0


class PcActiveDetector(_PowerThresholdDetector):
    """Detect PC activity from a configured power sensor."""

    activity_name = "pc_active"
    default_threshold_w = 50.0
    default_candidate_period_s = 30.0
    default_grace_period_s = 60.0


class _ApplianceDetector(_PowerThresholdDetector):
    def detect(
        self, observation: NormalizedObservation, canonical_state: CanonicalState
    ) -> ActivityDetection | None:
        del canonical_state
        if not self._matches(observation):
            return None
        state = str(observation.state or "").strip().lower()
        if state in _ON_STATES:
            return self._detection(observation, reason="state_on")
        power = _coerce_float(
            observation.raw_state if observation.raw_state is not None else observation.state
        )
        if power is not None and power >= self.threshold_w:
            return self._detection(observation, reason=f"power_gte_{self.threshold_w:g}w")
        return None


class WashingMachineDetector(_ApplianceDetector):
    """Detect washing machine activity from power or on/running state."""

    activity_name = "washing_machine_running"
    default_threshold_w = 200.0
    default_candidate_period_s = 60.0
    default_grace_period_s = 300.0


class DishwasherDetector(_ApplianceDetector):
    """Detect dishwasher activity from power or on/running state."""

    activity_name = "dishwasher_running"
    default_threshold_w = 200.0
    default_candidate_period_s = 60.0
    default_grace_period_s = 300.0


class TvActiveDetector(_PowerThresholdDetector):
    """Detect TV activity from media-player state or power."""

    activity_name = "tv_active"
    default_threshold_w = 20.0
    default_candidate_period_s = 10.0
    default_grace_period_s = 120.0

    def detect(
        self, observation: NormalizedObservation, canonical_state: CanonicalState
    ) -> ActivityDetection | None:
        del canonical_state
        if not self._matches(observation):
            return None
        state = str(observation.state or "").strip().lower()
        if state in {"playing", "paused"}:
            return self._detection(observation, reason="media_active")
        power = _coerce_float(
            observation.raw_state if observation.raw_state is not None else observation.state
        )
        if power is not None and power > self.threshold_w:
            return self._detection(observation, reason=f"power_gt_{self.threshold_w:g}w")
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
