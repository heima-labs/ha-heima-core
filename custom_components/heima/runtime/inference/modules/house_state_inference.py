"""HouseStateInferenceModule — approved learned house-state context signals."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ....const import HOUSE_STATES_LEARNED_CONTEXT_ELIGIBLE
from ...room_context import RoomDeviceContext, deserialize_room_device_context
from ..approval_store import (
    HOUSE_STATE_PROPOSAL_TYPE,
    house_state_context_key,
    house_state_context_snapshot,
)
from ..base import HeimaLearningModule, InferenceContext, SnapshotHistoryStore
from ..signals import HouseStateSignal, Importance

_MIN_SUPPORT = 3
_RICH_MIN_SUPPORT = 15
_MINIMAL_MIN_SUPPORT = 5
_CONFIDENCE_THRESHOLD = 0.60
_PROPOSABLE_HOUSE_STATES = frozenset(HOUSE_STATES_LEARNED_CONTEXT_ELIGIBLE)
_TIERS = ("rich", "coarse", "minimal")

RoomContextSignature = frozenset[tuple[str, bool, bool]]


@dataclass(frozen=True)
class _ModelEntry:
    tier: str
    weekday: int
    hour_bucket: int
    rooms: tuple[str, ...]
    anyone_home: bool
    room_context_signature: RoomContextSignature | None
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
        rich_min_support: int = _RICH_MIN_SUPPORT,
        minimal_min_support: int = _MINIMAL_MIN_SUPPORT,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
    ) -> None:
        self._min_support = max(1, int(min_support))
        self._rich_min_support = max(1, int(rich_min_support))
        self._minimal_min_support = max(1, int(minimal_min_support))
        self._confidence_threshold = max(0.0, min(float(confidence_threshold), 1.0))
        self._models: dict[str, dict[Any, _ModelEntry]] = {tier: {} for tier in _TIERS}
        self._model: dict[tuple[int, int, tuple[str, ...], bool], _ModelEntry] = self._models[
            "coarse"
        ]
        self._approved_context_keys: set[str] = set()
        self._rejected_context_keys: set[str] = set()
        self._ready = False
        self._analyzed_snapshots = 0
        self._model_first_snapshot_ts: str | None = None
        self._model_last_snapshot_ts: str | None = None
        self._infer_attempts_by_tier: dict[str, int] = {tier: 0 for tier in _TIERS}
        self._infer_hits_by_tier: dict[str, int] = {tier: 0 for tier in _TIERS}

    def sync_approval_state(self, approved: set[str], rejected: set[str]) -> None:
        """Replace the in-memory approval snapshot used by sync inference."""
        self._approved_context_keys = _normalized_keys(approved)
        self._rejected_context_keys = _normalized_keys(rejected)

    async def analyze(self, store: SnapshotHistoryStore) -> None:
        """Compute tiered house-state probabilities from snapshot history."""
        counts_by_tier: dict[str, dict[Any, dict[str, int]]] = {
            tier: defaultdict(lambda: defaultdict(int)) for tier in _TIERS
        }
        analyzed = 0
        first_ts: str | None = None
        last_ts: str | None = None

        for snapshot in store.snapshots():
            if not snapshot.house_state:
                continue
            snapshot_ts = str(getattr(snapshot, "ts", "") or "")
            if snapshot_ts:
                first_ts = snapshot_ts if first_ts is None else min(first_ts, snapshot_ts)
                last_ts = snapshot_ts if last_ts is None else max(last_ts, snapshot_ts)
            coarse_key = _coarse_slot_key(
                weekday=snapshot.weekday,
                minute_of_day=snapshot.minute_of_day,
                room_occupancy=snapshot.room_occupancy,
                anyone_home=snapshot.anyone_home,
            )
            counts_by_tier["coarse"][coarse_key][str(snapshot.house_state)] += 1
            minimal_key = _minimal_slot_key(
                weekday=snapshot.weekday,
                minute_of_day=snapshot.minute_of_day,
                anyone_home=snapshot.anyone_home,
            )
            counts_by_tier["minimal"][minimal_key][str(snapshot.house_state)] += 1

            room_context = deserialize_room_device_context(
                getattr(snapshot, "room_device_context", {}) or {}
            )
            rich_signature = _room_context_signature(
                room_device_context=room_context,
                room_occupancy=snapshot.room_occupancy,
            )
            if rich_signature:
                rich_key = _rich_slot_key(
                    weekday=snapshot.weekday,
                    minute_of_day=snapshot.minute_of_day,
                    room_context_signature=rich_signature,
                )
                counts_by_tier["rich"][rich_key][str(snapshot.house_state)] += 1
            analyzed += 1

        self._models = {
            tier: _build_model_for_tier(tier=tier, counts=counts_by_tier[tier]) for tier in _TIERS
        }
        self._model = self._models["coarse"]

        self._analyzed_snapshots = analyzed
        self._model_first_snapshot_ts = first_ts
        self._model_last_snapshot_ts = last_ts
        self._ready = True

    def infer(self, context: InferenceContext) -> list[HouseStateSignal]:
        if not self._ready:
            return []

        entry = self._select_entry(context)
        if entry is None:
            return []

        self._infer_hits_by_tier[entry.tier] += 1

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
                context={"tier": entry.tier},
            )
        ]

    def generate_candidates(self) -> list[LearnedHouseStateCandidate]:
        if not self._ready:
            return []

        candidates: list[LearnedHouseStateCandidate] = []
        for tier in _TIERS:
            for entry in self._models[tier].values():
                if entry.predicted_state not in _PROPOSABLE_HOUSE_STATES:
                    continue
                if entry.total < self._min_support_for_tier(tier):
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
        tier_diagnostics = {
            tier: {
                "slot_count": len(self._models[tier]),
                "min_support": self._min_support_for_tier(tier),
                "infer_attempts": self._infer_attempts_by_tier[tier],
                "infer_hits": self._infer_hits_by_tier[tier],
                "hit_rate": (
                    self._infer_hits_by_tier[tier] / self._infer_attempts_by_tier[tier]
                    if self._infer_attempts_by_tier[tier] > 0
                    else 0.0
                ),
            }
            for tier in _TIERS
        }
        return {
            "module_id": self.module_id,
            "ready": self._ready,
            "slot_count": len(self._model),
            "tiers": tier_diagnostics,
            "approved_context_keys": len(self._approved_context_keys),
            "rejected_context_keys": len(self._rejected_context_keys),
            "analyzed_snapshots": self._analyzed_snapshots,
            "model_first_snapshot_ts": self._model_first_snapshot_ts,
            "model_last_snapshot_ts": self._model_last_snapshot_ts,
            "model_total_snapshots": self._analyzed_snapshots,
            "approved_model_entries": self._approved_model_entries_diagnostics(),
            "min_support": self._min_support,
            "rich_min_support": self._rich_min_support,
            "minimal_min_support": self._minimal_min_support,
            "confidence_threshold": self._confidence_threshold,
        }

    def _approved_model_entries_diagnostics(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for tier in _TIERS:
            for entry in self._models[tier].values():
                if entry.context_key not in self._approved_context_keys:
                    continue
                entries.append(
                    {
                        "tier": entry.tier,
                        "context_key": entry.context_key,
                        "context_snapshot": dict(entry.context_snapshot),
                        "predicted_state": entry.predicted_state,
                        "count": entry.count,
                        "total": entry.total,
                        "confidence": entry.confidence,
                    }
                )
        return sorted(entries, key=lambda item: str(item.get("context_key") or ""))

    def _select_entry(self, context: InferenceContext) -> _ModelEntry | None:
        keys = _context_keys(context)
        for tier in _TIERS:
            key = keys.get(tier)
            if key is None:
                continue
            self._infer_attempts_by_tier[tier] += 1
            entry = self._models[tier].get(key)
            if entry is None:
                continue
            if entry.total < self._min_support_for_tier(tier):
                continue
            if entry.confidence < self._confidence_threshold:
                continue
            if entry.context_key not in self._approved_context_keys:
                continue
            return entry
        return None

    def _min_support_for_tier(self, tier: str) -> int:
        if tier == "rich":
            return self._rich_min_support
        if tier == "minimal":
            return self._minimal_min_support
        return self._min_support


def _coarse_slot_key(
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


def _minimal_slot_key(
    *,
    weekday: int,
    minute_of_day: int,
    anyone_home: bool,
) -> tuple[int, int, bool]:
    return (
        int(weekday),
        int(minute_of_day) // 60,
        bool(anyone_home),
    )


def _rich_slot_key(
    *,
    weekday: int,
    minute_of_day: int,
    room_context_signature: RoomContextSignature,
) -> tuple[int, int, RoomContextSignature]:
    return (
        int(weekday),
        int(minute_of_day) // 60,
        room_context_signature,
    )


def _context_keys(context: InferenceContext) -> dict[str, Any]:
    keys: dict[str, Any] = {
        "coarse": _coarse_slot_key(
            weekday=context.weekday,
            minute_of_day=context.minute_of_day,
            room_occupancy=context.room_occupancy,
            anyone_home=context.anyone_home,
        ),
        "minimal": _minimal_slot_key(
            weekday=context.weekday,
            minute_of_day=context.minute_of_day,
            anyone_home=context.anyone_home,
        ),
    }
    rich_signature = _room_context_signature(
        room_device_context=context.room_device_context,
        room_occupancy=context.room_occupancy,
    )
    if rich_signature:
        keys["rich"] = _rich_slot_key(
            weekday=context.weekday,
            minute_of_day=context.minute_of_day,
            room_context_signature=rich_signature,
        )
    return keys


def _build_model_for_tier(
    *, tier: str, counts: dict[Any, dict[str, int]]
) -> dict[Any, _ModelEntry]:
    model: dict[Any, _ModelEntry] = {}
    for key, state_counts in counts.items():
        total = sum(state_counts.values())
        predicted_state = max(state_counts, key=lambda state: state_counts[state])
        count = state_counts[predicted_state]
        confidence = count / total if total > 0 else 0.0
        weekday, hour_bucket, rooms, anyone_home, signature = _entry_context_parts(tier, key)
        learning_context = _learning_context_for_tier(tier, signature)
        context_key = house_state_context_key(
            weekday=weekday,
            hour_bucket=hour_bucket,
            rooms=rooms,
            anyone_home=anyone_home,
            predicted_state=predicted_state,
            learning_context=learning_context,
        )
        model[key] = _ModelEntry(
            tier=tier,
            weekday=weekday,
            hour_bucket=hour_bucket,
            rooms=rooms,
            anyone_home=anyone_home,
            room_context_signature=signature,
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
                learning_context=learning_context,
            ),
        )
    return model


def _entry_context_parts(
    tier: str,
    key: Any,
) -> tuple[int, int, tuple[str, ...], bool, RoomContextSignature | None]:
    if tier == "rich":
        weekday, hour_bucket, signature = key
        return int(weekday), int(hour_bucket), _rooms_from_signature(signature), True, signature
    if tier == "minimal":
        weekday, hour_bucket, anyone_home = key
        return int(weekday), int(hour_bucket), (), bool(anyone_home), None
    weekday, hour_bucket, rooms, anyone_home = key
    return int(weekday), int(hour_bucket), tuple(rooms), bool(anyone_home), None


def _learning_context_for_tier(
    tier: str,
    signature: RoomContextSignature | None,
) -> dict[str, Any]:
    if tier == "rich" and signature:
        return {
            "module": "house_state_inference_rich",
            "room_context_pattern": [
                {
                    "room_id": room_id,
                    "media_on": media_on,
                    "work_activity": work_activity,
                }
                for room_id, media_on, work_activity in sorted(signature)
            ],
        }
    if tier == "minimal":
        return {"module": "house_state_inference_minimal"}
    return {}


def _room_context_signature(
    *,
    room_device_context: dict[str, RoomDeviceContext],
    room_occupancy: dict[str, bool],
) -> RoomContextSignature:
    items: list[tuple[str, bool, bool]] = []
    for room_id, occupied in sorted(room_occupancy.items()):
        if not occupied:
            continue
        ctx = room_device_context.get(str(room_id))
        if ctx is None:
            continue
        items.append((str(room_id), bool(ctx.media_on), bool(ctx.work_activity)))
    return frozenset(items)


def _rooms_from_signature(signature: RoomContextSignature) -> tuple[str, ...]:
    return tuple(sorted(room_id for room_id, _media_on, _work_activity in signature))


def _importance(confidence: float) -> Importance:
    if confidence > 0.80:
        return Importance.ASSERT
    if confidence >= 0.60:
        return Importance.SUGGEST
    return Importance.OBSERVE


def _normalized_keys(keys: set[str]) -> set[str]:
    return {str(key).strip() for key in keys if str(key).strip()}
