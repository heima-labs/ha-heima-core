"""Analyzer contracts and proposal model for learning system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import uuid4

from ..event_store import EventStore


@dataclass
class ReactionProposal:
    """User-reviewable proposal produced by analyzers."""

    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    analyzer_id: str = ""
    reaction_type: str = ""
    description: str = ""
    confidence: float = 0.0
    origin: Literal["learned", "admin_authored"] = "learned"
    followup_kind: Literal["discovery", "tuning_suggestion"] = "discovery"
    status: Literal["pending", "accepted", "rejected"] = "pending"
    suggested_reaction_config: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_observed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    identity_key: str = ""
    fingerprint: str = ""  # if set, used by ProposalEngine instead of the computed fingerprint
    target_reaction_id: str = ""
    target_reaction_type: str = ""
    target_reaction_origin: str = ""
    target_template_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "analyzer_id": self.analyzer_id,
            "reaction_type": self.reaction_type,
            "description": self.description,
            "confidence": self.confidence,
            "origin": self.origin,
            "followup_kind": self.followup_kind,
            "status": self.status,
            "suggested_reaction_config": _safe_dict(self.suggested_reaction_config),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_observed_at": self.last_observed_at,
            "identity_key": self.identity_key,
            "fingerprint": self.fingerprint,
            "target_reaction_id": self.target_reaction_id,
            "target_reaction_type": self.target_reaction_type,
            "target_reaction_origin": self.target_reaction_origin,
            "target_template_id": self.target_template_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ReactionProposal":
        origin = str(raw.get("origin") or "learned")
        if origin not in {"learned", "admin_authored"}:
            origin = "learned"
        followup_kind = str(raw.get("followup_kind") or "discovery")
        if followup_kind not in {"discovery", "tuning_suggestion"}:
            followup_kind = "discovery"
        status = str(raw.get("status") or "pending")
        if status not in {"pending", "accepted", "rejected"}:
            status = "pending"
        return cls(
            proposal_id=str(raw.get("proposal_id") or str(uuid4())),
            analyzer_id=str(raw.get("analyzer_id") or ""),
            reaction_type=str(raw.get("reaction_type") or ""),
            description=str(raw.get("description") or ""),
            confidence=_safe_float(raw.get("confidence"), default=0.0),
            origin=origin,  # type: ignore[arg-type]
            followup_kind=followup_kind,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            suggested_reaction_config=_safe_dict(raw.get("suggested_reaction_config")),
            created_at=str(raw.get("created_at") or datetime.now(UTC).isoformat()),
            updated_at=str(raw.get("updated_at") or datetime.now(UTC).isoformat()),
            last_observed_at=str(
                raw.get("last_observed_at")
                or raw.get("updated_at")
                or raw.get("created_at")
                or datetime.now(UTC).isoformat()
            ),
            identity_key=str(raw.get("identity_key") or ""),
            fingerprint=str(raw.get("fingerprint") or ""),
            target_reaction_id=str(raw.get("target_reaction_id") or ""),
            target_reaction_type=str(raw.get("target_reaction_type") or ""),
            target_reaction_origin=str(raw.get("target_reaction_origin") or ""),
            target_template_id=str(raw.get("target_template_id") or ""),
        )


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


class IPatternAnalyzer(Protocol):
    """Analyzer protocol used by ProposalEngine."""

    @property
    def analyzer_id(self) -> str: ...

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]: ...
