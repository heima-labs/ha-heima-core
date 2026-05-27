"""HouseStateInferenceModule — approved learned house-state context signals."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ....const import HOUSE_STATES_LEARNED_CONTEXT_ELIGIBLE
from ..approval_store import (
    HOUSE_STATE_PROPOSAL_TYPE,
    house_state_context_key,
    house_state_context_snapshot,
)
from ..base import HeimaLearningModule, InferenceContext, SnapshotHistoryStore
from ..signals import HouseStateSignal, Importance

_MIN_SUPPORT = 3
_CONFIDENCE_THRESHOLD = 0.60
_PROPOSABLE_HOUSE_STATES = frozenset(HOUSE_STATES_LEARNED_CONTEXT_ELIGIBLE)


@dataclass(frozen=True)
class _ModelEntry:
    weekday: int
    hour_bucket: int
    rooms: tuple[str, ...]
    anyone_home: bool
    predicted_state: str
    total: int
    count: int
    confidence: float
    context_key: str
    context_snapshot: dict[str, Any]


@dataclass(frozen=True)
class LearnedHouseStateCandidate:
    """Proposal-first learned house-state context candidate."""

    proposal_type: str
    context_key: str
    context_snapshot: dict[str, Any]
    predicted_state: str
    support: int
    total: int
    confidence: float


class HouseStateInferenceModule(HeimaLearningModule):
    """Learns house-state probabilities and emits only approved context signals."""

    module_id = "house_state_inference"

    def __init__(
        self,
        *,
        min_support: int = _MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        self._model: dict[tuple[int, int, tuple[str, ...], bool], _ModelEntry] = {}
        self._approved_context_keys: set[str] = set()
        self._rejected_context_keys: set[str] = set()
        self._ready = False
        self._analyzed_snapshots = 0

    def sync_approval_state(self, approved: set[str], rejected: set[str]) -> None:
        """Replace the in-memory approval snapshot used by sync inference."""
        self._approved_context_keys = _normalized_keys(approved)
        self._rejected_context_keys = _normalized_keys(rejected)

    async def analyze(self, store: SnapshotHistoryStore) -> None:
        """Compute P(house_state | weekday, hour_bucket, occupied_rooms, anyone_home)."""
        counts: dict[tuple[int, int, tuple[str, ...], bool], dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        analyzed = 0

        for snapshot in store.snapshots():
            if not snapshot.house_state:
                continue
            key = _slot_key(
                weekday=snapshot.weekday,
                minute_of_day=snapshot.minute_of_day,
                room_occupancy=snapshot.room_occupancy,
                anyone_home=snapshot.anyone_home,
            )
            counts[key][str(snapshot.house_state)] += 1
            analyzed += 1

        self._model = {}
        for key, state_counts in counts.items():
            total = sum(state_counts.values())
            predicted_state = max(state_counts, key=lambda state: state_counts[state])
            count = state_counts[predicted_state]
            confidence = count / total if total > 0 else 0.0
            weekday, hour_bucket, rooms, anyone_home = key
            context_key = house_state_context_key(
                weekday=weekday,
                hour_bucket=hour_bucket,
                rooms=rooms,
                anyone_home=anyone_home,
                predicted_state=predicted_state,
                learning_context={},
            )
            self._model[key] = _ModelEntry(
                weekday=weekday,
                hour_bucket=hour_bucket,
                rooms=rooms,
                anyone_home=anyone_home,
                predicted_state=predicted_state,
                total=total,
                count=count,
                confidence=confidence,
                context_key=context_key,
                context_snapshot=house_state_context_snapshot(
                    weekday=weekday,
                    hour_bucket=hour_bucket,
                    rooms=rooms,
                    anyone_home=anyone_home,
                    predicted_state=predicted_state,
                    learning_context={},
                ),
            )

        self._analyzed_snapshots = analyzed
        self._ready = True

    def infer(self, context: InferenceContext) -> list[HouseStateSignal]:
        if not self._ready:
            return []

        key = _slot_key(
            weekday=context.weekday,
            minute_of_day=context.minute_of_day,
            room_occupancy=context.room_occupancy,
            anyone_home=context.anyone_home,
        )
        entry = self._model.get(key)
        if entry is None:
            return []
        if entry.total < self._min_support:
            return []
        if entry.confidence < self._confidence_threshold:
            return []
        if entry.context_key not in self._approved_context_keys:
            return []

        return [
            HouseStateSignal(
                source_id=self.module_id,
                confidence=entry.confidence,
                importance=_importance(entry.confidence),
                ttl_s=600,
                label=(
                    f"{entry.predicted_state} wd={context.weekday} h={context.minute_of_day // 60}"
                ),
                predicted_state=entry.predicted_state,
            )
        ]

    def generate_candidates(self) -> list[LearnedHouseStateCandidate]:
        if not self._ready:
            return []

        candidates: list[LearnedHouseStateCandidate] = []
        for entry in self._model.values():
            if entry.predicted_state not in _PROPOSABLE_HOUSE_STATES:
                continue
            if entry.total < self._min_support:
                continue
            if entry.confidence < self._confidence_threshold:
                continue
            if entry.context_key in self._approved_context_keys:
                continue
            if entry.context_key in self._rejected_context_keys:
                continue
            candidates.append(
                LearnedHouseStateCandidate(
                    proposal_type=HOUSE_STATE_PROPOSAL_TYPE,
                    context_key=entry.context_key,
                    context_snapshot=dict(entry.context_snapshot),
                    predicted_state=entry.predicted_state,
                    support=entry.count,
                    total=entry.total,
                    confidence=entry.confidence,
                )
            )
        return sorted(candidates, key=lambda candidate: candidate.context_key)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "slot_count": len(self._model),
            "approved_context_keys": len(self._approved_context_keys),
            "rejected_context_keys": len(self._rejected_context_keys),
            "analyzed_snapshots": self._analyzed_snapshots,
            "min_support": self._min_support,
            "confidence_threshold": self._confidence_threshold,
        }


def _slot_key(
    *,
    weekday: int,
    minute_of_day: int,
    room_occupancy: dict[str, bool],
    anyone_home: bool,
) -> tuple[int, int, tuple[str, ...], bool]:
    return (
        int(weekday),
        int(minute_of_day) // 60,
        tuple(sorted(str(room_id) for room_id, occupied in room_occupancy.items() if occupied)),
        bool(anyone_home),
    )


def _importance(confidence: float) -> Importance:
    if confidence > 0.80:
        return Importance.ASSERT
    if confidence >= 0.60:
        return Importance.SUGGEST
    return Importance.OBSERVE


def _normalized_keys(keys: set[str]) -> set[str]:
    return {str(key).strip() for key in keys if str(key).strip()}
