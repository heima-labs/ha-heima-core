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
        return self._sort_proposals(
            [p for p in self._proposals if p.status == "pending"]
        )

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
        ordered = self._sort_proposals(self._proposals)
        return {
            "total": len(ordered),
            "pending": len(self.pending_proposals()),
            "proposals": [
                {
                    "id": p.proposal_id,
                    "type": p.reaction_type,
                    "analyzer": p.analyzer_id,
                    "description": p.description,
                    "confidence": round(p.confidence, 2),
                    "status": p.status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "fingerprint": self._fingerprint(p),
                    "config_summary": self._proposal_config_summary(p),
                    "explainability": self._proposal_explainability(p),
                }
                for p in ordered
            ],
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"proposals": [p.as_dict() for p in self._proposals]}}

    def _write_sensor(self) -> None:
        if not self._sensor_writer:
            return
        pending = self.pending_proposals()
        ordered = self._sort_proposals(self._proposals)
        attributes = {
            p.proposal_id: {
                "type": p.reaction_type,
                "description": p.description,
                "confidence": p.confidence,
                "status": p.status,
                "analyzer_id": p.analyzer_id,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "fingerprint": self._fingerprint(p),
                "config_summary": self._proposal_config_summary(p),
                "explainability": self._proposal_explainability(p),
            }
            for p in ordered
        }
        self._sensor_writer(len(pending), attributes)

    @staticmethod
    def _fingerprint(proposal: ReactionProposal) -> str:
        if proposal.fingerprint:
            return proposal.fingerprint
        cfg = proposal.suggested_reaction_config
        weekday = cfg.get("weekday")
        house_state = cfg.get("house_state")
        return f"{proposal.analyzer_id}|{proposal.reaction_type}|{weekday}|{house_state}"

    @staticmethod
    def _sort_proposals(proposals: list[ReactionProposal]) -> list[ReactionProposal]:
        status_rank = {"pending": 0, "accepted": 1, "rejected": 2}

        def _ts(value: str) -> datetime:
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                return datetime.min.replace(tzinfo=UTC)

        return sorted(
            proposals,
            key=lambda p: (
                status_rank.get(p.status, 99),
                -float(p.confidence),
                -_ts(p.updated_at).timestamp(),
                -_ts(p.created_at).timestamp(),
                p.analyzer_id,
                p.reaction_type,
                p.proposal_id,
            ),
        )

    @staticmethod
    def _proposal_config_summary(proposal: ReactionProposal) -> dict[str, Any]:
        cfg = dict(proposal.suggested_reaction_config or {})
        summary = {
            "reaction_class": cfg.get("reaction_class"),
            "room_id": cfg.get("room_id"),
            "house_state": cfg.get("house_state"),
            "weekday": cfg.get("weekday"),
            "scheduled_min": cfg.get("scheduled_min"),
            "episodes_observed": cfg.get("episodes_observed"),
            "corroborated_episodes": cfg.get("corroborated_episodes"),
        }
        entity_steps = cfg.get("entity_steps")
        if isinstance(entity_steps, list):
            summary["entity_steps_count"] = len(entity_steps)
        steps = cfg.get("steps")
        if isinstance(steps, list):
            summary["steps_count"] = len(steps)
        return {k: v for k, v in summary.items() if v not in (None, "", [])}

    @staticmethod
    def _proposal_explainability(proposal: ReactionProposal) -> dict[str, Any]:
        diagnostics = proposal.suggested_reaction_config.get("learning_diagnostics")
        if not isinstance(diagnostics, dict):
            return {}
        keys = (
            "pattern_id",
            "observations_count",
            "episodes_detected",
            "episodes_confirmed",
            "episodes_observed",
            "corroborated_episodes",
            "weeks_observed",
            "iqr_min",
            "spread_c",
            "median_arrival_min",
            "median_target_temperature",
            "eco_sessions_observed",
            "matched_primary_entities",
            "matched_corroboration_entities",
            "observed_followup_entities",
        )
        return {
            key: diagnostics[key]
            for key in keys
            if key in diagnostics and diagnostics[key] not in (None, "", [])
        }
