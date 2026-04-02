"""Offline proposal engine for learning analyzers (P4)."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .analyzers.base import IPatternAnalyzer, ReactionProposal
from .analyzers.registry import LearningPluginRegistry, create_builtin_learning_plugin_registry
from .event_store import EventStore

_LOGGER = logging.getLogger(__name__)


class ProposalEngine:
    """Run analyzers, deduplicate proposals and persist review state."""

    STORAGE_KEY = "heima_proposals"
    STORAGE_VERSION = 1
    DEFAULT_STALE_AFTER = timedelta(days=14)
    DEFAULT_PRUNE_PENDING_STALE_AFTER = timedelta(days=45)

    def __init__(
        self,
        hass: HomeAssistant,
        event_store: EventStore,
        *,
        learning_plugin_registry: LearningPluginRegistry | None = None,
        min_confidence: float = 0.4,
        stale_after: timedelta | None = None,
        prune_pending_stale_after: timedelta | None = None,
        sensor_writer: Callable[[int, dict[str, Any]], None] | None = None,
    ) -> None:
        self._hass = hass
        self._event_store = event_store
        self._min_confidence = min_confidence
        self._stale_after = stale_after or self.DEFAULT_STALE_AFTER
        self._prune_pending_stale_after = (
            prune_pending_stale_after or self.DEFAULT_PRUNE_PENDING_STALE_AFTER
        )
        self._sensor_writer = sensor_writer
        self._learning_plugin_registry = (
            learning_plugin_registry or create_builtin_learning_plugin_registry()
        )
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._analyzers: list[IPatternAnalyzer] = []
        self._proposals: list[ReactionProposal] = []
        self._load_errors = 0
        self._last_load_proposal_count = 0
        self._last_analyzer_failures = 0
        self._last_analyzer_output_errors = 0

    def register_analyzer(self, analyzer: IPatternAnalyzer) -> None:
        self._analyzers.append(analyzer)

    def set_analyzers(self, analyzers: list[IPatternAnalyzer] | tuple[IPatternAnalyzer, ...]) -> None:
        self._analyzers = list(analyzers)

    def set_learning_plugin_registry(self, registry: LearningPluginRegistry) -> None:
        self._learning_plugin_registry = registry

    async def async_initialize(self) -> None:
        raw = await self._store.async_load()
        self._proposals = []
        self._load_errors = 0
        if isinstance(raw, dict):
            data = raw.get("data")
            items = data.get("proposals") if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        self._load_errors += 1
                        continue
                    proposal = self._proposal_from_storage(item)
                    if proposal is None:
                        self._load_errors += 1
                        continue
                    self._proposals.append(proposal)
        self._last_load_proposal_count = len(self._proposals)
        self._write_sensor()

    async def async_run(self) -> None:
        generated: list[ReactionProposal] = []
        self._last_analyzer_failures = 0
        self._last_analyzer_output_errors = 0
        for analyzer in self._analyzers:
            try:
                proposals = await analyzer.analyze(self._event_store)
            except Exception:  # noqa: BLE001
                self._last_analyzer_failures += 1
                _LOGGER.exception("Learning analyzer '%s' failed during analyze()", analyzer.analyzer_id)
                continue
            if not isinstance(proposals, list):
                try:
                    proposals = list(proposals)
                except TypeError:
                    self._last_analyzer_output_errors += 1
                    continue
            for proposal in proposals:
                if not isinstance(proposal, ReactionProposal):
                    self._last_analyzer_output_errors += 1
                    continue
                if proposal.confidence >= self._min_confidence:
                    generated.append(proposal)

        merged = list(self._proposals)
        for candidate in generated:
            now = datetime.now(UTC).isoformat()
            identity_key = self._identity_key(candidate)
            followup_slot_key = self._followup_slot_key(candidate)
            matching = [
                (idx, current)
                for idx, current in enumerate(merged)
                if self._identity_key(current) == identity_key
            ]
            pending_match = next(
                ((idx, current) for idx, current in matching if current.status == "pending"),
                None,
            )
            if pending_match is not None:
                existing_idx, existing = pending_match
                merged[existing_idx] = replace(
                    existing,
                    confidence=candidate.confidence,
                    description=candidate.description,
                    suggested_reaction_config=dict(candidate.suggested_reaction_config),
                    updated_at=now,
                    last_observed_at=now,
                    identity_key=identity_key,
                    followup_kind=candidate.followup_kind,
                    target_reaction_id=candidate.target_reaction_id,
                    target_reaction_class=candidate.target_reaction_class,
                    target_reaction_origin=candidate.target_reaction_origin,
                    target_template_id=candidate.target_template_id,
                )
                continue

            accepted_match = next(
                ((idx, current) for idx, current in matching if current.status == "accepted"),
                None,
            )
            if accepted_match is None and followup_slot_key:
                accepted_match = self._fallback_followup_match(
                    merged,
                    candidate,
                    followup_slot_key=followup_slot_key,
                )
            if accepted_match is None and not matching:
                merged.append(
                    replace(
                        candidate,
                        identity_key=identity_key,
                        last_observed_at=now,
                    )
                )
                continue

            if accepted_match is not None:
                _, accepted = accepted_match
                if self._should_suppress_followup(candidate, accepted):
                    continue
                merged.append(
                    replace(
                        candidate,
                        identity_key=identity_key,
                        last_observed_at=now,
                        followup_kind="tuning_suggestion",
                        target_reaction_class=(
                            candidate.target_reaction_class
                            or str(
                                _safe_dict(accepted.suggested_reaction_config).get("reaction_class") or ""
                            )
                        ),
                        target_reaction_origin=(
                            candidate.target_reaction_origin or accepted.origin
                        ),
                        target_template_id=(
                            candidate.target_template_id
                            or str(
                                _safe_dict(accepted.suggested_reaction_config).get(
                                    "admin_authored_template_id"
                                )
                                or ""
                            )
                        ),
                    )
                )
                continue

            # Rejected history remains frozen unless explicitly resubmitted by the user.
            continue

        pruned = self._prune_stale_pending(merged)
        self._proposals = pruned
        await self._store.async_save(self._serialize())
        self._write_sensor()

    async def async_accept_proposal(self, proposal_id: str) -> bool:
        return await self._set_status(proposal_id, "accepted")

    async def async_reject_proposal(self, proposal_id: str) -> bool:
        return await self._set_status(proposal_id, "rejected")

    async def async_submit_proposal(self, proposal: ReactionProposal) -> str:
        """Insert or refresh one externally-authored proposal into the shared store."""
        now = datetime.now(UTC).isoformat()
        identity_key = self._identity_key(proposal)
        existing_idx = next(
            (
                idx
                for idx, current in enumerate(self._proposals)
                if self._identity_key(current) == identity_key
            ),
            None,
        )
        if existing_idx is None:
            submitted = replace(
                proposal,
                identity_key=identity_key,
                last_observed_at=proposal.last_observed_at or now,
            )
            self._proposals.append(submitted)
            await self._store.async_save(self._serialize())
            self._write_sensor()
            return submitted.proposal_id

        existing = self._proposals[existing_idx]
        if existing.status != "pending":
            return existing.proposal_id

        updated = replace(
            existing,
            analyzer_id=proposal.analyzer_id,
            reaction_type=proposal.reaction_type,
            description=proposal.description,
            confidence=proposal.confidence,
            origin=proposal.origin,
            suggested_reaction_config=dict(proposal.suggested_reaction_config),
            updated_at=now,
            last_observed_at=proposal.last_observed_at or now,
            identity_key=identity_key,
        )
        self._proposals[existing_idx] = updated
        await self._store.async_save(self._serialize())
        self._write_sensor()
        return updated.proposal_id

    def pending_proposals(self) -> list[ReactionProposal]:
        return self._sort_proposals(
            [p for p in self._proposals if p.status == "pending"]
        )

    def proposal_by_identity_key(self, identity_key: str) -> ReactionProposal | None:
        target = identity_key.strip()
        if not target:
            return None
        for proposal in self._proposals:
            if self._identity_key(proposal) == target:
                return proposal
        return None

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
            "loaded_proposals": self._last_load_proposal_count,
            "load_errors": self._load_errors,
            "analyzer_failures": self._last_analyzer_failures,
            "analyzer_output_errors": self._last_analyzer_output_errors,
            "pending": len(self.pending_proposals()),
            "pending_stale": sum(
                1 for proposal in ordered if proposal.status == "pending" and self._is_stale(proposal)
            ),
            "stale_after_s": int(self._stale_after.total_seconds()),
            "prune_pending_stale_after_s": int(self._prune_pending_stale_after.total_seconds()),
            "proposals": [
                {
                    "id": p.proposal_id,
                    "type": p.reaction_type,
                    "analyzer": p.analyzer_id,
                    "description": p.description,
                    "confidence": round(p.confidence, 2),
                    "origin": p.origin,
                    "followup_kind": p.followup_kind,
                    "status": p.status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "last_observed_at": p.last_observed_at,
                    "identity_key": self._identity_key(p),
                    "fingerprint": self._fingerprint(p),
                    "target_reaction_id": p.target_reaction_id,
                    "target_reaction_class": p.target_reaction_class,
                    "target_reaction_origin": p.target_reaction_origin,
                    "target_template_id": p.target_template_id,
                    "is_stale": self._is_stale(p),
                    "stale_reason": self._stale_reason(p),
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
                "origin": p.origin,
                "followup_kind": p.followup_kind,
                "status": p.status,
                "analyzer_id": p.analyzer_id,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "last_observed_at": p.last_observed_at,
                "identity_key": self._identity_key(p),
                "fingerprint": self._fingerprint(p),
                "target_reaction_id": p.target_reaction_id,
                "target_reaction_class": p.target_reaction_class,
                "target_reaction_origin": p.target_reaction_origin,
                "target_template_id": p.target_template_id,
                "is_stale": self._is_stale(p),
                "stale_reason": self._stale_reason(p),
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
        cfg = _safe_dict(proposal.suggested_reaction_config)
        weekday = cfg.get("weekday")
        house_state = cfg.get("house_state")
        return f"{proposal.analyzer_id}|{proposal.reaction_type}|{weekday}|{house_state}"

    def _identity_key(self, proposal: ReactionProposal) -> str:
        if proposal.identity_key:
            return proposal.identity_key

        hooks = self._learning_plugin_registry.lifecycle_hooks_for(proposal.reaction_type)
        if hooks is not None:
            return hooks.identity_key(proposal)
        if proposal.fingerprint:
            return proposal.fingerprint
        return self._fingerprint(proposal)

    def _followup_slot_key(self, proposal: ReactionProposal) -> str:
        hooks = self._learning_plugin_registry.lifecycle_hooks_for(proposal.reaction_type)
        if hooks is not None and hooks.followup_slot_key is not None:
            return hooks.followup_slot_key(proposal)
        return self._identity_key(proposal)

    def _fallback_followup_match(
        self,
        proposals: list[ReactionProposal],
        candidate: ReactionProposal,
        *,
        followup_slot_key: str,
    ) -> tuple[int, ReactionProposal] | None:
        hooks = self._learning_plugin_registry.lifecycle_hooks_for(candidate.reaction_type)
        if hooks is None or hooks.fallback_followup_match is None:
            return None
        return hooks.fallback_followup_match(proposals, candidate, followup_slot_key)

    def _should_suppress_followup(
        self,
        candidate: ReactionProposal,
        accepted: ReactionProposal,
    ) -> bool:
        hooks = self._learning_plugin_registry.lifecycle_hooks_for(candidate.reaction_type)
        if hooks is None or hooks.should_suppress_followup is None:
            return False
        return hooks.should_suppress_followup(candidate, accepted)

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

    def _is_stale(self, proposal: ReactionProposal) -> bool:
        if proposal.status != "pending":
            return False
        last_observed_at = self._parse_ts(proposal.last_observed_at)
        if last_observed_at is None:
            return True
        return (datetime.now(UTC) - last_observed_at) > self._stale_after

    def _stale_reason(self, proposal: ReactionProposal) -> str | None:
        if proposal.status != "pending":
            return None
        last_observed_at = self._parse_ts(proposal.last_observed_at)
        if last_observed_at is None:
            return "missing_last_observed_at"
        age = datetime.now(UTC) - last_observed_at
        if age > self._stale_after:
            return (
                "not_observed_recently:"
                f"age_s={int(age.total_seconds())}:"
                f"threshold_s={int(self._stale_after.total_seconds())}"
            )
        return None

    def _prune_stale_pending(self, proposals: list[ReactionProposal]) -> list[ReactionProposal]:
        retained: list[ReactionProposal] = []
        now = datetime.now(UTC)
        for proposal in proposals:
            if proposal.status != "pending":
                retained.append(proposal)
                continue
            last_observed_at = self._parse_ts(proposal.last_observed_at)
            if last_observed_at is None:
                retained.append(proposal)
                continue
            age = now - last_observed_at
            if age > self._prune_pending_stale_after:
                continue
            retained.append(proposal)
        return retained

    @staticmethod
    def _proposal_from_storage(raw: dict[str, Any]) -> ReactionProposal | None:
        proposal = ReactionProposal.from_dict(raw)
        if not proposal.reaction_type:
            return None
        if not proposal.analyzer_id:
            return None
        return proposal

    @staticmethod
    def _parse_ts(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _proposal_config_summary(proposal: ReactionProposal) -> dict[str, Any]:
        cfg = _safe_dict(proposal.suggested_reaction_config)
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
        cfg = _safe_dict(proposal.suggested_reaction_config)
        diagnostics = cfg.get("learning_diagnostics")
        if not isinstance(diagnostics, dict):
            return {}
        keys = (
            "pattern_id",
            "analyzer_id",
            "reaction_type",
            "plugin_family",
            "room_id",
            "house_state",
            "weekday",
            "scheduled_min",
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
            "cluster_entities",
            "entity_steps_count",
            "correlated_signal_keys",
            "primary_signal",
            "corroboration_signals",
            "followup_signal",
            "matched_primary_entities",
            "matched_corroboration_entities",
            "observed_followup_entities",
        )
        return {
            key: diagnostics[key]
            for key in keys
            if key in diagnostics and diagnostics[key] not in (None, "", [])
        }


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
