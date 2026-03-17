"""Offline proposal engine for learning analyzers (P4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .analyzers.base import IPatternAnalyzer, ReactionProposal
from .event_store import EventStore


class ProposalEngine:
    """Run analyzers, deduplicate proposals and persist review state."""

    STORAGE_KEY = "heima_proposals"
    STORAGE_VERSION = 1

    def __init__(
        self,
        hass: HomeAssistant,
        event_store: EventStore,
        *,
        min_confidence: float = 0.4,
        sensor_writer: Callable[[int, dict[str, Any]], None] | None = None,
    ) -> None:
        self._hass = hass
        self._event_store = event_store
        self._min_confidence = min_confidence
        self._sensor_writer = sensor_writer
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._analyzers: list[IPatternAnalyzer] = []
        self._proposals: list[ReactionProposal] = []

    def register_analyzer(self, analyzer: IPatternAnalyzer) -> None:
        self._analyzers.append(analyzer)

    async def async_initialize(self) -> None:
        raw = await self._store.async_load()
        self._proposals = []
        if isinstance(raw, dict):
            data = raw.get("data")
            items = data.get("proposals") if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        self._proposals.append(ReactionProposal.from_dict(item))
        self._write_sensor()

    async def async_run(self) -> None:
        generated: list[ReactionProposal] = []
        for analyzer in self._analyzers:
            proposals = await analyzer.analyze(self._event_store)
            for proposal in proposals:
                if proposal.confidence >= self._min_confidence:
                    generated.append(proposal)

        merged = list(self._proposals)
        for candidate in generated:
            fingerprint = self._fingerprint(candidate)
            existing_idx = next(
                (
                    idx
                    for idx, current in enumerate(merged)
                    if self._fingerprint(current) == fingerprint
                ),
                None,
            )
            if existing_idx is None:
                merged.append(candidate)
                continue

            existing = merged[existing_idx]
            if existing.status in {"accepted", "rejected"}:
                continue
            merged[existing_idx] = replace(
                existing,
                confidence=candidate.confidence,
                description=candidate.description,
                suggested_reaction_config=dict(candidate.suggested_reaction_config),
                updated_at=datetime.now(UTC).isoformat(),
            )

        self._proposals = merged
        await self._store.async_save(self._serialize())
        self._write_sensor()

    async def async_accept_proposal(self, proposal_id: str) -> bool:
        return await self._set_status(proposal_id, "accepted")

    async def async_reject_proposal(self, proposal_id: str) -> bool:
        return await self._set_status(proposal_id, "rejected")

    def pending_proposals(self) -> list[ReactionProposal]:
        return [p for p in self._proposals if p.status == "pending"]

    async def async_shutdown(self) -> None:
        await self._store.async_save(self._serialize())

    async def async_clear(self) -> None:
        """Clear all stored proposals."""
        self._proposals = []
        await self._store.async_save(self._serialize())
        self._write_sensor()

    async def _set_status(self, proposal_id: str, status: str) -> bool:
        for idx, proposal in enumerate(self._proposals):
            if proposal.proposal_id != proposal_id:
                continue
            self._proposals[idx] = replace(
                proposal,
                status=status,  # type: ignore[arg-type]
                updated_at=datetime.now(UTC).isoformat(),
            )
            await self._store.async_save(self._serialize())
            self._write_sensor()
            return True
        return False

    def diagnostics(self) -> dict[str, Any]:
        return {
            "total": len(self._proposals),
            "pending": len(self.pending_proposals()),
            "proposals": [
                {
                    "id": p.proposal_id,
                    "type": p.reaction_type,
                    "analyzer": p.analyzer_id,
                    "description": p.description,
                    "confidence": round(p.confidence, 2),
                    "status": p.status,
                }
                for p in self._proposals
            ],
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"proposals": [p.as_dict() for p in self._proposals]}}

    def _write_sensor(self) -> None:
        if not self._sensor_writer:
            return
        pending = self.pending_proposals()
        attributes = {
            p.proposal_id: {
                "type": p.reaction_type,
                "description": p.description,
                "confidence": p.confidence,
                "status": p.status,
                "analyzer_id": p.analyzer_id,
            }
            for p in self._proposals
        }
        self._sensor_writer(len(pending), attributes)

    @staticmethod
    def _fingerprint(proposal: ReactionProposal) -> str:
        cfg = proposal.suggested_reaction_config
        weekday = cfg.get("weekday")
        house_state = cfg.get("house_state")
        return f"{proposal.analyzer_id}|{proposal.reaction_type}|{weekday}|{house_state}"
