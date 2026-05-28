"""LightingPatternModule — learns P(scene | room_id, house_state, hour_bucket)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ..base import HeimaLearningModule, InferenceContext, SnapshotHistoryStore
from ..signals import Importance, LightingSignal

_MIN_SUPPORT = 8
_CONFIDENCE_THRESHOLD = 0.65


@dataclass(frozen=True)
class _LightingPatternEntry:
    room_id: str
    house_state: str
    hour_bucket: int
    predicted_scene: str
    total: int
    count: int
    confidence: float


class LightingPatternModule(HeimaLearningModule):
    """Emits LightingSignal based on historical scene patterns per room/state/hour."""

    module_id = "lighting_pattern"

    def __init__(
        self,
        *,
        min_support: int = _MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        self._model: dict[tuple[str, str, int], _LightingPatternEntry] = {}
        self._ready = False
        self._analyzed_snapshots = 0

    async def analyze(self, store: SnapshotHistoryStore) -> None:
        """Compute P(scene | room_id, house_state, hour_bucket) from snapshot history."""
        counts: dict[tuple[str, str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        analyzed = 0

        for snapshot in store.snapshots():
            house_state = str(getattr(snapshot, "house_state", "") or "").strip()
            if not house_state:
                continue
            lighting_scenes = getattr(snapshot, "lighting_scenes", {})
            if not isinstance(lighting_scenes, dict) or not lighting_scenes:
                continue
            hour_bucket = int(getattr(snapshot, "minute_of_day", 0) or 0) // 60
            for room_id, scene in lighting_scenes.items():
                room = str(room_id or "").strip()
                scene_name = str(scene or "").strip()
                if not room or not scene_name:
                    continue
                counts[(room, house_state, hour_bucket)][scene_name] += 1
            analyzed += 1

        self._model = {}
        for key, scene_counts in counts.items():
            total = sum(scene_counts.values())
            predicted_scene = max(scene_counts, key=lambda scene: scene_counts[scene])
            count = scene_counts[predicted_scene]
            room_id, house_state, hour_bucket = key
            self._model[key] = _LightingPatternEntry(
                room_id=room_id,
                house_state=house_state,
                hour_bucket=hour_bucket,
                predicted_scene=predicted_scene,
                total=total,
                count=count,
                confidence=count / total if total > 0 else 0.0,
            )

        self._analyzed_snapshots = analyzed
        self._ready = True

    def infer(self, context: InferenceContext) -> list[LightingSignal]:
        """Emit one signal per modeled room for the current state/hour context."""
        if not self._ready:
            return []
        house_state = str(context.previous_house_state or "").strip()
        if not house_state:
            return []
        hour_bucket = int(context.minute_of_day) // 60
        signals: list[LightingSignal] = []
        for entry in sorted(
            self._model.values(),
            key=lambda item: (item.room_id, item.predicted_scene),
        ):
            if entry.house_state != house_state or entry.hour_bucket != hour_bucket:
                continue
            if entry.total < self._min_support:
                continue
            if entry.confidence < self._confidence_threshold:
                continue
            signals.append(
                LightingSignal(
                    source_id=self.module_id,
                    confidence=entry.confidence,
                    importance=Importance.SUGGEST,
                    ttl_s=600,
                    label=(
                        f"{entry.room_id} -> {entry.predicted_scene} "
                        f"state={entry.house_state} h={entry.hour_bucket}"
                    ),
                    room_id=entry.room_id,
                    predicted_scene=entry.predicted_scene,
                )
            )
        return signals

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "slot_count": len(self._model),
            "analyzed_snapshots": self._analyzed_snapshots,
            "min_support": self._min_support,
            "confidence_threshold": self._confidence_threshold,
        }
