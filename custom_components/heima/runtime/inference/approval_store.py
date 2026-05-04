"""Approval record contracts for inference-gated proposals."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

ApprovalActor = Literal["resident", "installer"]
ApprovalDecision = Literal["approved", "rejected"]


@dataclass(frozen=True)
class ApprovalRecord:
    """Persistable approval decision with product-role provenance."""

    proposal_id: str
    proposal_type: str
    decision: ApprovalDecision
    approved_by: ApprovalActor
    approved_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    context_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["metadata"] = dict(self.metadata)
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ApprovalRecord | None":
        try:
            proposal_id = str(raw["proposal_id"])
            proposal_type = str(raw["proposal_type"])
        except (KeyError, TypeError, ValueError):
            return None

        decision = str(raw.get("decision") or "")
        if decision not in {"approved", "rejected"}:
            return None

        approved_by = str(raw.get("approved_by") or "")
        if approved_by not in {"resident", "installer"}:
            return None

        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            decision=decision,  # type: ignore[arg-type]
            approved_by=approved_by,  # type: ignore[arg-type]
            approved_at=str(raw.get("approved_at") or datetime.now(UTC).isoformat()),
            context_key=str(raw.get("context_key") or ""),
            metadata=dict(metadata),
        )


class ApprovalStore:
    """Reserved Phase H store contract for inference approval decisions."""

    STORAGE_KEY = "heima_inference_approvals"
    STORAGE_VERSION = 1


__all__ = [
    "ApprovalActor",
    "ApprovalDecision",
    "ApprovalRecord",
    "ApprovalStore",
]
