"""Persistent approval store for inference-gated proposals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

ApprovalActor = Literal["resident", "installer"]
ApprovalDecision = Literal["approved", "rejected"]
HOUSE_STATE_PROPOSAL_TYPE = "house_state_learned_context"


@dataclass(frozen=True)
class ApprovalRecord:
    """Persistable approval decision with product-role provenance."""

    proposal_id: str
    proposal_type: str
    decision: ApprovalDecision
    approved_by: ApprovalActor
    context_key: str
    context_snapshot: dict[str, Any]
    approved_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["context_snapshot"] = dict(self.context_snapshot)
        raw["metadata"] = dict(self.metadata)
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ApprovalRecord | None":
        try:
            proposal_id = str(raw["proposal_id"])
            proposal_type = str(raw["proposal_type"])
            context_key = str(raw["context_key"])
        except (KeyError, TypeError, ValueError):
            return None
        if not proposal_id or not proposal_type or not context_key:
            return None

        decision = str(raw.get("decision") or "")
        if decision not in {"approved", "rejected"}:
            return None

        approved_by = str(raw.get("approved_by") or "")
        if approved_by not in {"resident", "installer"}:
            return None

        context_snapshot = raw.get("context_snapshot")
        if not isinstance(context_snapshot, dict) or not context_snapshot:
            return None

        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            decision=decision,  # type: ignore[arg-type]
            approved_by=approved_by,  # type: ignore[arg-type]
            context_key=context_key,
            context_snapshot=dict(context_snapshot),
            approved_at=str(raw.get("approved_at") or datetime.now(UTC).isoformat()),
            metadata=dict(metadata),
        )


class ApprovalStore:
    """Durable approval registry for inference permission decisions."""

    STORAGE_KEY = "heima_inference_approvals"
    STORAGE_VERSION = 1
    _SAVE_DELAY_S = 30

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._records: dict[tuple[str, str], ApprovalRecord] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load persisted approval records, ignoring malformed entries."""
        raw = await self._store.async_load()
        records_raw = []
        if isinstance(raw, dict):
            data = raw.get("data")
            if isinstance(data, dict):
                records_raw = data.get("records", [])

        self._records.clear()
        if isinstance(records_raw, list):
            for item in records_raw:
                if not isinstance(item, dict):
                    continue
                record = ApprovalRecord.from_dict(item)
                if record is not None:
                    self._records[self._record_key(record.context_key, record.proposal_type)] = (
                        record
                    )

        self._loaded = True
        self._schedule_save()

    async def async_record(self, record: ApprovalRecord) -> None:
        """Insert or replace one approval decision."""
        if not self._loaded:
            await self.async_load()
        self._records[self._record_key(record.context_key, record.proposal_type)] = record
        self._schedule_save()

    async def async_clear(self) -> None:
        """Clear all approval records."""
        self._records.clear()
        self._schedule_save()

    async def async_flush(self) -> None:
        """Immediately flush approval records to HA storage."""
        await self._store.async_save(self._serialize())

    def decision_for(self, context_key: str, proposal_type: str) -> ApprovalRecord | None:
        """Return the current approval decision for a context/proposal pair."""
        return self._records.get(self._record_key(context_key, proposal_type))

    def approved_records(self) -> tuple[ApprovalRecord, ...]:
        """Return approved records in deterministic order."""
        return tuple(
            sorted(
                (record for record in self._records.values() if record.decision == "approved"),
                key=lambda item: (item.proposal_type, item.context_key),
            )
        )

    def records(self) -> tuple[ApprovalRecord, ...]:
        """Return all records in deterministic order."""
        return tuple(
            sorted(self._records.values(), key=lambda item: (item.proposal_type, item.context_key))
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return approval-store diagnostics."""
        approved = sum(1 for record in self._records.values() if record.decision == "approved")
        rejected = sum(1 for record in self._records.values() if record.decision == "rejected")
        return {
            "storage_key": self.STORAGE_KEY,
            "total_records": len(self._records),
            "approved_records": approved,
            "rejected_records": rejected,
            "records": [record.as_dict() for record in self.records()],
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"records": [record.as_dict() for record in self.records()]}}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, self._SAVE_DELAY_S)

    @staticmethod
    def _record_key(context_key: str, proposal_type: str) -> tuple[str, str]:
        return (str(context_key).strip(), str(proposal_type).strip())


def house_state_context_key(
    *,
    weekday: int,
    hour_bucket: int,
    rooms: list[str] | tuple[str, ...] | set[str],
    anyone_home: bool,
    predicted_state: str,
    learning_context: dict[str, Any] | None = None,
) -> str:
    """Build the stable approval key for a learned house-state context."""
    normalized_rooms = _canonical_rooms(rooms)
    context = canonicalize_learning_context(learning_context or {})
    context_token = _context_hash(context)
    return (
        f"weekday:{int(weekday)}:"
        f"hour_bucket:{int(hour_bucket)}:"
        f"rooms:{','.join(normalized_rooms) if normalized_rooms else 'none'}:"
        f"anyone_home:{1 if anyone_home else 0}:"
        f"ctx:{context_token}:"
        f"state:{_token(predicted_state)}"
    )


def house_state_context_snapshot(
    *,
    weekday: int,
    hour_bucket: int,
    rooms: list[str] | tuple[str, ...] | set[str],
    anyone_home: bool,
    predicted_state: str,
    learning_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a human-readable snapshot matching a house-state context key."""
    return {
        "weekday": int(weekday),
        "hour_bucket": int(hour_bucket),
        "rooms": list(_canonical_rooms(rooms)),
        "anyone_home": bool(anyone_home),
        "predicted_state": _token(predicted_state),
        "learning_context": canonicalize_learning_context(learning_context or {}),
    }


def canonicalize_learning_context(raw: dict[str, Any]) -> dict[str, str]:
    """Canonicalize the fixed H1 learning-context vocabulary."""
    allowed_prefixes = ("activity.", "occupancy.", "presence.")
    result: dict[str, str] = {}
    for key, value in raw.items():
        normalized_key = str(key).strip()
        if not normalized_key.startswith(allowed_prefixes):
            continue
        if value is None:
            continue
        result[normalized_key] = _token(value)
    return dict(sorted(result.items()))


def _canonical_rooms(rooms: list[str] | tuple[str, ...] | set[str]) -> tuple[str, ...]:
    return tuple(sorted({_token(room) for room in rooms if _token(room)}))


def _context_hash(context: dict[str, str]) -> str:
    if not context:
        return "none"
    raw = json.dumps(context, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _token(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_")


__all__ = [
    "ApprovalActor",
    "ApprovalDecision",
    "ApprovalRecord",
    "ApprovalStore",
    "HOUSE_STATE_PROPOSAL_TYPE",
    "canonicalize_learning_context",
    "house_state_context_key",
    "house_state_context_snapshot",
]
