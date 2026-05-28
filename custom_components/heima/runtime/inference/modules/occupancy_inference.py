"""OccupancyInferenceModule — learns P(room_occupied | room, weekday, hour, home)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ..base import HeimaLearningModule, InferenceContext, SnapshotHistoryStore
from ..signals import Importance, OccupancySignal

_MIN_SUPPORT = 10
_CONFIDENCE_THRESHOLD = 0.70


@dataclass(frozen=True)
class _OccupancyEntry:
    room_id: str
    weekday: int
    hour_bucket: int
    anyone_home: bool
    predicted_occupied: bool
    total: int
    count: int
    confidence: float


class OccupancyInferenceModule(HeimaLearningModule):
    """Emits OccupancySignal for sensorless rooms only."""

    module_id = "occupancy_inference"

    def __init__(
        self,
        *,
        min_support: int = _MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        self._sensorless_rooms: set[str] = set()
        self._model: dict[tuple[str, int, int, bool], _OccupancyEntry] = {}
        self._ready = False
        self._analyzed_snapshots = 0

    def sync_sensorless_rooms(self, room_ids: set[str]) -> None:
        """Replace the sensorless room allow-list used during inference."""
        self._sensorless_rooms = {
            str(room_id).strip()
            for room_id in room_ids
            if str(room_id).strip()
        }

    async def analyze(self, store: SnapshotHistoryStore) -> None:
        """Compute occupancy probabilities from snapshot history."""
        self._model = {}
        if not self._sensorless_rooms:
            self._analyzed_snapshots = 0
            self._ready = True
            return

        counts: dict[tuple[str, int, int, bool], dict[bool, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        analyzed = 0

        for snapshot in store.snapshots():
            room_occupancy = getattr(snapshot, "room_occupancy", {})
            if not isinstance(room_occupancy, dict):
                continue
            weekday = int(getattr(snapshot, "weekday", 0) or 0)
            hour_bucket = int(getattr(snapshot, "minute_of_day", 0) or 0) // 60
            anyone_home = bool(getattr(snapshot, "anyone_home", False))
            for room_id in sorted(self._sensorless_rooms):
                occupied = bool(room_occupancy.get(room_id, False))
                counts[(room_id, weekday, hour_bucket, anyone_home)][occupied] += 1
            analyzed += 1

        for key, occupancy_counts in counts.items():
            total = sum(occupancy_counts.values())
            predicted_occupied = max(
                occupancy_counts,
                key=lambda occupied: occupancy_counts[occupied],
            )
            count = occupancy_counts[predicted_occupied]
            room_id, weekday, hour_bucket, anyone_home = key
            probability = count / total if total > 0 else 0.0
            confidence = probability * min(1.0, total / self._min_support)
            self._model[key] = _OccupancyEntry(
                room_id=room_id,
                weekday=weekday,
                hour_bucket=hour_bucket,
                anyone_home=anyone_home,
                predicted_occupied=predicted_occupied,
                total=total,
                count=count,
                confidence=confidence,
            )

        self._analyzed_snapshots = analyzed
        self._ready = True

    def infer(self, context: InferenceContext) -> list[OccupancySignal]:
        """Emit one signal per configured sensorless room for the current context."""
        if not self._ready or not self._sensorless_rooms:
            return []
        weekday = int(context.weekday)
        hour_bucket = int(context.minute_of_day) // 60
        anyone_home = any(bool(value) for value in context.room_occupancy.values())
        signals: list[OccupancySignal] = []
        for room_id in sorted(self._sensorless_rooms):
            entry = self._model.get((room_id, weekday, hour_bucket, anyone_home))
            if entry is None:
                continue
            if entry.total < self._min_support:
                continue
            if entry.confidence < self._confidence_threshold:
                continue
            signals.append(
                OccupancySignal(
                    source_id=self.module_id,
                    confidence=entry.confidence,
                    importance=Importance.SUGGEST,
                    ttl_s=300,
                    label=(
                        f"{entry.room_id} occupied={entry.predicted_occupied} "
                        f"wd={entry.weekday} h={entry.hour_bucket} home={entry.anyone_home}"
                    ),
                    room_id=entry.room_id,
                    predicted_occupied=entry.predicted_occupied,
                )
            )
        return signals

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "slot_count": len(self._model),
            "sensorless_rooms": sorted(self._sensorless_rooms),
            "analyzed_snapshots": self._analyzed_snapshots,
            "min_support": self._min_support,
            "confidence_threshold": self._confidence_threshold,
        }
