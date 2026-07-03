"""Offline proposal engine for learning analyzers (P4)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .analyzers.base import (
    LIFECYCLE_SUGGESTION_FOLLOWUP_KINDS,
    PROPOSAL_LIFECYCLE_SUGGESTION_TYPE,
    ReactionProposal,
)
from .analyzers.lifecycle import ProposalReviewGrouping
from .analyzers.registry import LearningPluginRegistry, create_builtin_learning_plugin_registry
from .event_store import EventStore
from .inference.approval_store import (
    ACTIVITY_PROPOSAL_TYPE,
    HOUSE_STATE_PROPOSAL_TYPE,
    house_state_context_key,
)
from .plugin_contracts import BehaviorFinding, IBehaviorAnalyzer
from .proposal_lifecycle_store import ProposalLifecycleRecord, ProposalLifecycleStore
from .proposal_review_bundles import ProposalReviewBundleView, build_temporal_review_bundles
from .reactions import resolve_reaction_type

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AcceptedRuleLifecyclePolicy:
    """Internal policy for monitored accepted-rule lifecycle evidence."""

    required_observations: int = 3
    retirement_multiplier: int = 2
    maintenance_threshold: int = 2
    rolling_window_limit: int = 12

    @property
    def replacement_threshold(self) -> int:
        return self.required_observations

    @property
    def retirement_threshold(self) -> int:
        return self.required_observations * self.retirement_multiplier


@dataclass
class ActivityProposal:
    """User-reviewable composite activity proposal."""

    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    proposal_type: str = ACTIVITY_PROPOSAL_TYPE
    activity_name: str = ""
    primitive_pattern: frozenset[str] = field(default_factory=frozenset)
    context_conditions: dict[str, Any] = field(default_factory=dict)
    occurrence_count: int = 0
    confidence: float = 0.0
    representative_ts: list[str] = field(default_factory=list)
    bootstrap: bool = False
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_observed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    identity_key: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposal_model": "activity",
            "proposal_id": self.proposal_id,
            "proposal_type": self.proposal_type,
            "activity_name": self.activity_name,
            "primitive_pattern": sorted(self.primitive_pattern),
            "context_conditions": _safe_dict(self.context_conditions),
            "occurrence_count": int(self.occurrence_count),
            "confidence": self.confidence,
            "representative_ts": [str(ts) for ts in self.representative_ts],
            "bootstrap": bool(self.bootstrap),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_observed_at": self.last_observed_at,
            "identity_key": self.identity_key,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ActivityProposal | None":
        proposal_type = str(raw.get("proposal_type") or "")
        if proposal_type != ACTIVITY_PROPOSAL_TYPE:
            return None
        activity_name = _token(raw.get("activity_name"))
        primitive_pattern = frozenset(
            _token(item) for item in raw.get("primitive_pattern", []) if _token(item)
        )
        if not activity_name or not primitive_pattern:
            return None
        status = str(raw.get("status") or "pending")
        if status not in {"pending", "accepted", "rejected"}:
            status = "pending"
        representative_ts = raw.get("representative_ts", [])
        if not isinstance(representative_ts, list):
            representative_ts = []
        return cls(
            proposal_id=str(raw.get("proposal_id") or str(uuid4())),
            proposal_type=proposal_type,
            activity_name=activity_name,
            primitive_pattern=primitive_pattern,
            context_conditions=_safe_dict(raw.get("context_conditions")),
            occurrence_count=max(0, int(_safe_float(raw.get("occurrence_count"), default=0.0))),
            confidence=_safe_float(raw.get("confidence"), default=0.0),
            representative_ts=[str(ts) for ts in representative_ts],
            bootstrap=bool(raw.get("bootstrap", False)),
            status=status,
            created_at=str(raw.get("created_at") or datetime.now(UTC).isoformat()),
            updated_at=str(raw.get("updated_at") or datetime.now(UTC).isoformat()),
            last_observed_at=str(
                raw.get("last_observed_at")
                or raw.get("updated_at")
                or raw.get("created_at")
                or datetime.now(UTC).isoformat()
            ),
            identity_key=str(raw.get("identity_key") or ""),
        )


ProposalItem = ReactionProposal | ActivityProposal


@dataclass(frozen=True)
class _ReviewGroupDerivedState:
    visible_pending_ids: frozenset[str]
    group_key_by_id: dict[str, str]
    role_by_id: dict[str, str]
    suppressed_ids: frozenset[str]
    groups: dict[str, list[str]]


class ProposalEngine:
    """Run analyzers, deduplicate proposals and persist review state."""

    STORAGE_KEY = "heima_proposals"
    STORAGE_VERSION = 1
    DEFAULT_STALE_AFTER = timedelta(days=14)
    DEFAULT_PRUNE_PENDING_STALE_AFTER = timedelta(days=45)
    SENSOR_ITEMS_LIMIT = 20

    def __init__(
        self,
        hass: HomeAssistant,
        event_store: EventStore,
        *,
        learning_plugin_registry: LearningPluginRegistry | None = None,
        configured_reactions_provider: Callable[[], dict[str, Any]] | None = None,
        min_confidence: float = 0.4,
        stale_after: timedelta | None = None,
        prune_pending_stale_after: timedelta | None = None,
        sensor_writer: Callable[[int, dict[str, Any]], None] | None = None,
        lifecycle_store: ProposalLifecycleStore | None = None,
        lifecycle_policy: AcceptedRuleLifecyclePolicy | None = None,
    ) -> None:
        self._hass = hass
        self._event_store = event_store
        self._min_confidence = min_confidence
        self._stale_after = stale_after or self.DEFAULT_STALE_AFTER
        self._prune_pending_stale_after = (
            prune_pending_stale_after or self.DEFAULT_PRUNE_PENDING_STALE_AFTER
        )
        self._sensor_writer = sensor_writer
        self._lifecycle_store = lifecycle_store
        self._lifecycle_policy = lifecycle_policy or AcceptedRuleLifecyclePolicy()
        self._configured_reactions_provider = configured_reactions_provider
        self._learning_plugin_registry = (
            learning_plugin_registry or create_builtin_learning_plugin_registry()
        )
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._analyzers: list[IBehaviorAnalyzer] = []
        self._proposals: list[ProposalItem] = []
        self._load_errors = 0
        self._last_load_proposal_count = 0
        self._last_analyzer_failures = 0
        self._last_analyzer_output_errors = 0

    def register_analyzer(self, analyzer: IBehaviorAnalyzer) -> None:
        self._analyzers.append(analyzer)

    def set_analyzers(
        self, analyzers: list[IBehaviorAnalyzer] | tuple[IBehaviorAnalyzer, ...]
    ) -> None:
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
        if self._lifecycle_store is not None:
            await self._lifecycle_store.async_load()
            await self._sync_accepted_lifecycle_records()
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
                _LOGGER.exception(
                    "Learning analyzer '%s' failed during analyze()", analyzer.analyzer_id
                )
                continue
            if not isinstance(proposals, list):
                try:
                    proposals = list(proposals)
                except TypeError:
                    self._last_analyzer_output_errors += 1
                    continue
            for raw_proposal in proposals:
                proposal = self._proposal_from_analyzer_output(raw_proposal)
                if isinstance(proposal, ActivityProposal):
                    if proposal.confidence >= self._min_confidence:
                        await self.async_submit_proposal(proposal)
                    continue
                if (
                    isinstance(proposal, ReactionProposal)
                    and proposal.confidence >= self._min_confidence
                ):
                    generated.append(proposal)
                    continue
                self._last_analyzer_output_errors += 1

        merged = list(self._proposals)
        for candidate in generated:
            reaction_proposals = [p for p in merged if isinstance(p, ReactionProposal)]
            normalized_candidate = self._normalize_generated_candidate(
                candidate, reaction_proposals
            )
            if normalized_candidate is None:
                continue
            now = datetime.now(UTC).isoformat()
            identity_key = self._identity_key(normalized_candidate)
            followup_slot_key = self._followup_slot_key(normalized_candidate)
            matching = [
                (idx, current)
                for idx, current in enumerate(merged)
                if isinstance(current, ReactionProposal)
                and self._identity_key(current) == identity_key
            ]
            accepted_matches = [
                (idx, current) for idx, current in matching if current.status == "accepted"
            ]
            if self._configured_reaction_suppresses_candidate(normalized_candidate):
                merged = [
                    current
                    for current in merged
                    if not (
                        current.status == "pending" and self._identity_key(current) == identity_key
                    )
                ]
                continue

            suppressing_accepted_match = next(
                (
                    (idx, current)
                    for idx, current in accepted_matches
                    if self._should_suppress_followup(normalized_candidate, current)
                ),
                None,
            )
            if suppressing_accepted_match is not None:
                merged = [
                    current
                    for current in merged
                    if not (
                        current.status == "pending" and self._identity_key(current) == identity_key
                    )
                ]
                continue

            pending_match = next(
                ((idx, current) for idx, current in matching if current.status == "pending"),
                None,
            )
            if pending_match is not None:
                existing_idx, existing = pending_match
                merged[existing_idx] = replace(
                    existing,
                    confidence=normalized_candidate.confidence,
                    description=normalized_candidate.description,
                    suggested_reaction_config=_safe_dict(
                        normalized_candidate.suggested_reaction_config
                    ),
                    updated_at=now,
                    last_observed_at=now,
                    identity_key=identity_key,
                    followup_kind=normalized_candidate.followup_kind,
                    target_reaction_id=normalized_candidate.target_reaction_id,
                    target_reaction_type=normalized_candidate.target_reaction_type,
                    target_reaction_origin=normalized_candidate.target_reaction_origin,
                    target_template_id=normalized_candidate.target_template_id,
                    improves_reaction_type=normalized_candidate.improves_reaction_type,
                    improvement_reason=normalized_candidate.improvement_reason,
                )
                continue

            accepted_match = _latest_proposal_match(accepted_matches)
            if accepted_match is None and followup_slot_key:
                accepted_match = self._fallback_followup_match(
                    [p for p in merged if isinstance(p, ReactionProposal)],
                    normalized_candidate,
                    followup_slot_key=followup_slot_key,
                )
            if accepted_match is None and not matching:
                merged.append(
                    replace(
                        normalized_candidate,
                        identity_key=identity_key,
                        last_observed_at=now,
                    )
                )
                continue

            if accepted_match is not None:
                _, accepted = accepted_match
                merged.append(
                    replace(
                        normalized_candidate,
                        identity_key=identity_key,
                        last_observed_at=now,
                        followup_kind="tuning_suggestion",
                        target_reaction_type=(
                            normalized_candidate.target_reaction_type
                            or resolve_reaction_type(_safe_dict(accepted.suggested_reaction_config))
                            or accepted.reaction_type
                        ),
                        target_reaction_origin=(
                            normalized_candidate.target_reaction_origin or accepted.origin
                        ),
                        target_template_id=(
                            normalized_candidate.target_template_id
                            or str(
                                _safe_dict(accepted.suggested_reaction_config).get(
                                    "admin_authored_template_id"
                                )
                                or ""
                            )
                        ),
                        improves_reaction_type=normalized_candidate.improves_reaction_type,
                        improvement_reason=normalized_candidate.improvement_reason,
                    )
                )
                continue

            # Rejected history remains frozen unless explicitly resubmitted by the user.
            continue

        pruned = self._prune_stale_pending(merged)
        self._proposals = pruned
        await self._store.async_save(self._serialize())
        self._write_sensor()

    @staticmethod
    def _proposal_from_analyzer_output(value: object) -> ProposalItem | None:
        if not isinstance(value, BehaviorFinding):
            return None
        if value.kind == "pattern" and isinstance(value.payload, ReactionProposal):
            return value.payload
        if value.kind == "activity" and isinstance(value.payload, ActivityProposal):
            return value.payload
        return None

    def _normalize_generated_candidate(
        self,
        candidate: ReactionProposal,
        proposals: list[ReactionProposal],
    ) -> ReactionProposal | None:
        registry = self._learning_plugin_registry
        if registry is None:
            return candidate
        if candidate.followup_kind == "improvement":
            return candidate
        if not any(
            descriptor.target_reaction_type == candidate.reaction_type
            for descriptor in registry.improvement_descriptors()
        ):
            return candidate
        source = self._source_for_improvement_candidate(candidate, proposals)
        if source is None:
            return None
        descriptor = registry.improvement_descriptor_for(
            target_reaction_type=candidate.reaction_type,
            source_reaction_type=str(source.get("reaction_type") or ""),
            improvement_reason=candidate.improvement_reason,
        )
        if descriptor is None:
            return candidate
        source_cfg = _safe_dict(source.get("cfg"))
        return replace(
            candidate,
            followup_kind="improvement",
            target_reaction_id=str(source.get("target_id") or ""),
            target_reaction_type=str(source.get("reaction_type") or ""),
            target_reaction_origin=str(source.get("origin") or ""),
            target_template_id=str(
                source_cfg.get("source_template_id")
                or source_cfg.get("admin_authored_template_id")
                or ""
            ),
            improves_reaction_type=str(source.get("reaction_type") or ""),
            improvement_reason=candidate.improvement_reason or descriptor.improvement_reason,
        )

    def _source_for_improvement_candidate(
        self,
        candidate: ReactionProposal,
        proposals: list[ReactionProposal],
    ) -> dict[str, Any] | None:
        registry = self._learning_plugin_registry
        if registry is None:
            return None
        cfg = _safe_dict(candidate.suggested_reaction_config)
        room_id = str(cfg.get("room_id") or "").strip()
        primary_signal_name = str(cfg.get("primary_signal_name") or "").strip()
        if not room_id:
            return None
        configured = self._configured_source_for_improvement_candidate(
            candidate,
            room_id=room_id,
            primary_signal_name=primary_signal_name,
        )
        if configured is not None:
            return configured
        accepted = self._accepted_source_for_improvement_candidate(
            candidate, proposals, room_id=room_id, primary_signal_name=primary_signal_name
        )
        if accepted is None:
            return None
        accepted_cfg = _safe_dict(accepted.suggested_reaction_config)
        return {
            "target_id": accepted.proposal_id,
            "reaction_type": accepted.reaction_type,
            "origin": accepted.origin,
            "cfg": accepted_cfg,
        }

    def _accepted_source_for_improvement_candidate(
        self,
        candidate: ReactionProposal,
        proposals: list[ReactionProposal],
        *,
        room_id: str,
        primary_signal_name: str,
    ) -> ReactionProposal | None:
        registry = self._learning_plugin_registry
        if registry is None:
            return None
        for proposal in proposals:
            if proposal.status != "accepted":
                continue
            descriptor = registry.improvement_descriptor_for(
                target_reaction_type=candidate.reaction_type,
                source_reaction_type=proposal.reaction_type,
                improvement_reason=candidate.improvement_reason,
            )
            if descriptor is None:
                continue
            source_cfg = _safe_dict(proposal.suggested_reaction_config)
            if str(source_cfg.get("room_id") or "").strip() != room_id:
                continue
            if primary_signal_name and (
                str(source_cfg.get("primary_signal_name") or "").strip() != primary_signal_name
            ):
                continue
            return proposal
        return None

    def _configured_source_for_improvement_candidate(
        self,
        candidate: ReactionProposal,
        *,
        room_id: str,
        primary_signal_name: str,
    ) -> dict[str, Any] | None:
        registry = self._learning_plugin_registry
        if registry is None or self._configured_reactions_provider is None:
            return None
        configured = self._configured_reactions_provider()
        if not isinstance(configured, dict):
            return None
        for reaction_id, raw in configured.items():
            reaction_cfg = _safe_dict(raw)
            reaction_type = resolve_reaction_type(reaction_cfg)
            descriptor = registry.improvement_descriptor_for(
                target_reaction_type=candidate.reaction_type,
                source_reaction_type=reaction_type,
                improvement_reason=candidate.improvement_reason,
            )
            if descriptor is None:
                continue
            if str(reaction_cfg.get("room_id") or "").strip() != room_id:
                continue
            if primary_signal_name and (
                str(reaction_cfg.get("primary_signal_name") or "").strip() != primary_signal_name
            ):
                continue
            return {
                "target_id": str(reaction_id),
                "reaction_type": reaction_type,
                "origin": str(reaction_cfg.get("origin") or ""),
                "cfg": reaction_cfg,
            }
        return None

    def _configured_reaction_suppresses_candidate(self, candidate: ReactionProposal) -> bool:
        if self._configured_reactions_provider is None:
            return False
        configured = self._configured_reactions_provider()
        if not isinstance(configured, dict):
            return False
        for raw in configured.values():
            reaction_cfg = _safe_dict(raw)
            if not reaction_cfg:
                continue
            if self._configured_reaction_cfg_suppresses_candidate(candidate, reaction_cfg):
                return True
        return False

    def _configured_reaction_cfg_suppresses_candidate(
        self,
        candidate: ReactionProposal,
        reaction_cfg: dict[str, Any],
    ) -> bool:
        reaction_type = resolve_reaction_type(reaction_cfg)
        if not reaction_type:
            return False
        if reaction_type == candidate.reaction_type:
            accepted_proxy = replace(
                candidate,
                status="accepted",
                suggested_reaction_config=reaction_cfg,
            )
            return self._should_suppress_followup(candidate, accepted_proxy)
        return False

    async def async_accept_proposal(self, proposal_id: str) -> bool:
        return await self._set_status(proposal_id, "accepted")

    async def async_reject_proposal(self, proposal_id: str) -> bool:
        return await self._set_status(proposal_id, "rejected")

    async def async_apply_lifecycle_suggestion(self, proposal_id: str) -> bool:
        """Accept and apply lifecycle-state effects for a review suggestion."""
        proposal = self.proposal_by_id(proposal_id)
        if not isinstance(proposal, ReactionProposal):
            return False
        if proposal.followup_kind not in LIFECYCLE_SUGGESTION_FOLLOWUP_KINDS:
            return False
        if self._lifecycle_store is None:
            return await self.async_accept_proposal(proposal_id)

        cfg = _safe_dict(proposal.suggested_reaction_config)
        target_proposal_id = str(cfg.get("target_proposal_id") or "").strip()
        record = self._lifecycle_store.record_by_proposal_id(target_proposal_id)
        if record is None:
            return False

        if proposal.status == "rejected":
            return False
        if proposal.status != "accepted" and not await self.async_accept_proposal(proposal_id):
            return False

        now = datetime.now(UTC).isoformat()
        if proposal.followup_kind == "replacement_suggestion":
            await self._async_apply_replacement_to_source_proposal(
                record=record,
                suggestion=proposal,
                applied_at=now,
            )
        updated = _applied_lifecycle_record(
            record=record,
            suggestion_id=proposal.proposal_id,
            suggestion_kind=proposal.followup_kind,
            applied_at=now,
        )
        await self._lifecycle_store.async_replace_record(updated)
        return True

    async def _async_apply_replacement_to_source_proposal(
        self,
        *,
        record: ProposalLifecycleRecord,
        suggestion: ReactionProposal,
        applied_at: str,
    ) -> None:
        """Update the accepted source proposal with the reviewed replacement context."""
        cfg = _safe_dict(suggestion.suggested_reaction_config)
        proposed_context = _safe_dict(cfg.get("proposed_context_snapshot"))
        replacement_cfg = _replacement_house_state_config(record=record, cfg=cfg)
        if not replacement_cfg:
            return

        for idx, current in enumerate(self._proposals):
            if current.proposal_id != record.proposal_id:
                continue
            if not isinstance(current, ReactionProposal):
                return
            if current.status != "accepted" or current.reaction_type != HOUSE_STATE_PROPOSAL_TYPE:
                return

            source_cfg = _safe_dict(current.suggested_reaction_config)
            source_cfg.update(replacement_cfg)
            self._proposals[idx] = replace(
                current,
                description=_replacement_house_state_description(
                    current.description,
                    proposed_context,
                ),
                suggested_reaction_config=source_cfg,
                identity_key=f"{HOUSE_STATE_PROPOSAL_TYPE}:{replacement_cfg['context_key']}",
                updated_at=applied_at,
                last_observed_at=applied_at,
            )
            await self._store.async_save(self._serialize())
            self._write_sensor()
            return

    async def async_boost_confidence(self, reaction_id: str, delta: float) -> None:
        """Boost confidence of the accepted proposal targeting reaction_id."""
        target = str(reaction_id or "").strip()
        if not target:
            return
        now = datetime.now(UTC).isoformat()
        boost = max(float(delta), 0.0)
        for idx, proposal in enumerate(self._proposals):
            if (
                isinstance(proposal, ReactionProposal)
                and proposal.target_reaction_id == target
                and proposal.status == "accepted"
            ):
                self._proposals[idx] = replace(
                    proposal,
                    confidence=min(1.0, proposal.confidence + boost),
                    updated_at=now,
                )
                await self._store.async_save(self._serialize())
                self._write_sensor()
                return

    async def async_submit_proposal(self, proposal: ProposalItem) -> str:
        """Insert or refresh one externally-authored proposal into the shared store."""
        if isinstance(proposal, ActivityProposal):
            return await self._async_submit_activity_proposal(proposal)

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
                suggested_reaction_config=_safe_dict(proposal.suggested_reaction_config),
                identity_key=identity_key,
                last_observed_at=proposal.last_observed_at or now,
            )
            self._proposals.append(submitted)
            await self._store.async_save(self._serialize())
            self._write_sensor()
            return submitted.proposal_id

        existing = self._proposals[existing_idx]
        if isinstance(existing, ActivityProposal):
            return existing.proposal_id
        if existing.status != "pending":
            return existing.proposal_id

        updated = replace(
            existing,
            analyzer_id=proposal.analyzer_id,
            reaction_type=proposal.reaction_type,
            description=proposal.description,
            confidence=proposal.confidence,
            origin=proposal.origin,
            suggested_reaction_config=_safe_dict(proposal.suggested_reaction_config),
            updated_at=now,
            last_observed_at=proposal.last_observed_at or now,
            identity_key=identity_key,
            followup_kind=proposal.followup_kind,
            target_reaction_id=proposal.target_reaction_id,
            target_reaction_type=proposal.target_reaction_type,
            target_reaction_origin=proposal.target_reaction_origin,
            target_template_id=proposal.target_template_id,
            improves_reaction_type=proposal.improves_reaction_type,
            improvement_reason=proposal.improvement_reason,
        )
        self._proposals[existing_idx] = updated
        await self._store.async_save(self._serialize())
        self._write_sensor()
        return updated.proposal_id

    async def _async_submit_activity_proposal(self, proposal: ActivityProposal) -> str:
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
                context_conditions=_safe_dict(proposal.context_conditions),
                identity_key=identity_key,
                last_observed_at=proposal.last_observed_at or now,
            )
            self._proposals.append(submitted)
            await self._store.async_save(self._serialize())
            self._write_sensor()
            return submitted.proposal_id

        existing = self._proposals[existing_idx]
        if not isinstance(existing, ActivityProposal):
            return existing.proposal_id
        if existing.status != "pending":
            return existing.proposal_id

        updated = replace(
            existing,
            activity_name=proposal.activity_name,
            primitive_pattern=frozenset(proposal.primitive_pattern),
            context_conditions=_safe_dict(proposal.context_conditions),
            occurrence_count=proposal.occurrence_count,
            confidence=proposal.confidence,
            representative_ts=list(proposal.representative_ts),
            bootstrap=proposal.bootstrap,
            updated_at=now,
            last_observed_at=proposal.last_observed_at or now,
            identity_key=identity_key,
        )
        self._proposals[existing_idx] = updated
        await self._store.async_save(self._serialize())
        self._write_sensor()
        return updated.proposal_id

    def pending_proposals(self) -> list[ProposalItem]:
        return self._sort_proposals(self._visible_pending_proposals())

    def accepted_proposals(self) -> list[ProposalItem]:
        return self._sort_proposals([p for p in self._proposals if p.status == "accepted"])

    def proposal_by_identity_key(self, identity_key: str) -> ProposalItem | None:
        target = identity_key.strip()
        if not target:
            return None
        for proposal in self._proposals:
            if self._identity_key(proposal) == target:
                return proposal
        return None

    def proposal_by_id(self, proposal_id: str) -> ProposalItem | None:
        """Return one proposal by stable proposal id."""
        target = str(proposal_id or "").strip()
        if not target:
            return None
        for proposal in self._proposals:
            if proposal.proposal_id == target:
                return proposal
        return None

    async def async_shutdown(self) -> None:
        await self._store.async_save(self._serialize())

    async def async_clear(self) -> None:
        """Clear all stored proposals."""
        self._proposals = []
        await self._store.async_save(self._serialize())
        self._write_sensor()

    async def async_withdraw(self, identity_key: str) -> bool:
        """Remove a pending proposal by identity key without touching decisions."""
        target = str(identity_key or "").strip()
        if not target:
            return False
        for idx, proposal in enumerate(self._proposals):
            if self._identity_key(proposal) != target:
                continue
            if proposal.status != "pending":
                return False
            del self._proposals[idx]
            await self._store.async_save(self._serialize())
            self._write_sensor()
            return True
        return False

    async def _set_status(self, proposal_id: str, status: str) -> bool:
        for idx, proposal in enumerate(self._proposals):
            if proposal.proposal_id != proposal_id:
                continue
            updates: dict[str, Any] = {
                "status": status,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            if (
                status == "accepted"
                and isinstance(proposal, ReactionProposal)
                and not proposal.target_reaction_id
            ):
                updates["target_reaction_id"] = proposal.proposal_id
                updates["target_reaction_type"] = proposal.reaction_type
            self._proposals[idx] = replace(proposal, **updates)
            await self._store.async_save(self._serialize())
            await self._sync_lifecycle_record_for(self._proposals[idx])
            self._write_sensor()
            return True
        return False

    def diagnostics(self) -> dict[str, Any]:
        ordered = self._sort_proposals(self._proposals)
        review_state = self._review_group_state()
        visible_pending = self.pending_proposals()
        bundle_view = build_temporal_review_bundles(visible_pending)
        review_rows = _proposal_review_rows(visible_pending, bundle_view)
        temporal_bundle_by_proposal_id = _temporal_bundle_member_map(bundle_view)
        return {
            "total": len(ordered),
            "loaded_proposals": self._last_load_proposal_count,
            "load_errors": self._load_errors,
            "analyzer_failures": self._last_analyzer_failures,
            "analyzer_output_errors": self._last_analyzer_output_errors,
            "pending": len(visible_pending),
            "suppressed_in_review_count": len(review_state.suppressed_ids),
            "review_groups": review_state.groups,
            "review_rows": review_rows,
            "review_row_count": len(review_rows),
            "temporal_bundles": [bundle.as_dict() for bundle in bundle_view.bundles],
            "temporal_bundle_count": len(bundle_view.bundles),
            "temporal_bundle_member_count": len(bundle_view.bundled_proposal_ids),
            "lifecycle_monitoring": self._lifecycle_diagnostics(),
            "pending_stale": sum(
                1
                for proposal in ordered
                if proposal.status == "pending"
                and proposal.proposal_id in review_state.visible_pending_ids
                and self._is_stale(proposal)
            ),
            "stale_after_s": int(self._stale_after.total_seconds()),
            "prune_pending_stale_after_s": int(self._prune_pending_stale_after.total_seconds()),
            "proposals": [
                {
                    "id": p.proposal_id,
                    "type": _proposal_type(p),
                    "analyzer": getattr(p, "analyzer_id", "ActivityAnalyzer"),
                    "description": _proposal_description(p),
                    "confidence": round(p.confidence, 2),
                    "origin": getattr(p, "origin", "learned"),
                    "followup_kind": getattr(p, "followup_kind", "discovery"),
                    "status": p.status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "last_observed_at": p.last_observed_at,
                    "identity_key": self._identity_key(p),
                    "fingerprint": self._fingerprint(p) if isinstance(p, ReactionProposal) else "",
                    "target_reaction_id": getattr(p, "target_reaction_id", ""),
                    "target_reaction_type": getattr(p, "target_reaction_type", ""),
                    "target_reaction_origin": getattr(p, "target_reaction_origin", ""),
                    "target_template_id": getattr(p, "target_template_id", ""),
                    "improves_reaction_type": getattr(p, "improves_reaction_type", ""),
                    "improvement_reason": getattr(p, "improvement_reason", ""),
                    "review_group_key": review_state.group_key_by_id.get(p.proposal_id),
                    "review_group_role": review_state.role_by_id.get(p.proposal_id),
                    "suppressed_by_review_group": p.proposal_id in review_state.suppressed_ids,
                    "temporal_bundle_key": temporal_bundle_by_proposal_id.get(
                        p.proposal_id, {}
                    ).get("key"),
                    "temporal_bundle_role": temporal_bundle_by_proposal_id.get(
                        p.proposal_id, {}
                    ).get("role"),
                    "temporal_bundle_span_key": temporal_bundle_by_proposal_id.get(
                        p.proposal_id, {}
                    ).get("span_key"),
                    "temporal_bundle_member_count": temporal_bundle_by_proposal_id.get(
                        p.proposal_id, {}
                    ).get("member_count", 0),
                    "is_stale": self._is_stale(p),
                    "stale_reason": self._stale_reason(p),
                    "config_summary": self._proposal_config_summary(p)
                    if isinstance(p, ReactionProposal)
                    else _activity_config_summary(p),
                    "explainability": self._proposal_explainability(p)
                    if isinstance(p, ReactionProposal)
                    else {},
                }
                for p in ordered
            ],
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"proposals": [p.as_dict() for p in self._proposals]}}

    async def async_evaluate_house_state_lifecycle_opportunities(self) -> None:
        """Refresh accepted house-state lifecycle evidence from aggregate event windows."""
        if self._lifecycle_store is None:
            return
        records = [
            record
            for record in self._lifecycle_store.records()
            if record.proposal_type == HOUSE_STATE_PROPOSAL_TYPE
            and not record.retired_at
            and not record.replaced_by
        ]
        if not records:
            return

        since = min(
            (record.monitoring_window_start or record.accepted_at for record in records),
            default="",
        )
        events = await self._event_store.async_query(since=since or None)
        for record in records:
            updated = self._evaluate_house_state_lifecycle_record(record, events)
            await self._lifecycle_store.async_replace_record(updated)
            await self._async_submit_lifecycle_suggestion(updated)

    def _evaluate_house_state_lifecycle_record(
        self,
        record: ProposalLifecycleRecord,
        events: list[Any],
    ) -> ProposalLifecycleRecord:
        proposal = self._proposal_by_id(record.proposal_id)
        if not isinstance(proposal, ReactionProposal):
            return self._dependency_unavailable_lifecycle_record(record)

        link_state = self._classify_reaction_link_state(record)["state"]
        if link_state in {"reaction_missing", "linked_uninterpretable"}:
            return self._dependency_unavailable_lifecycle_record(record)

        baseline = _house_state_lifecycle_baseline(proposal)
        if baseline is None:
            return self._dependency_unavailable_lifecycle_record(record)

        counts = _house_state_lifecycle_counts(
            events,
            baseline,
            window_limit=self._lifecycle_policy.rolling_window_limit,
        )
        review_kind = _lifecycle_review_kind(
            counts=counts,
            policy=self._lifecycle_policy,
        )
        return replace(
            record,
            last_confirmed_at=str(counts.get("last_confirmed_at") or ""),
            confirmed_count=int(counts["confirmed"]),
            outcome_contradiction_count=int(counts["outcome_contradicted"]),
            context_miss_count=int(counts["context_missed"]),
            unknown_transient_count=int(counts["unknown_transient"]),
            dependency_unavailable_count=int(counts["dependency_unavailable"]),
            evaluated_window_count=int(counts["evaluated_windows"]),
            replacement_candidate_state=str(counts.get("replacement_candidate_state") or ""),
            replacement_candidate_count=int(counts["replacement_candidate_count"]),
            lifecycle_review_kind=review_kind,
        )

    def _dependency_unavailable_lifecycle_record(
        self, record: ProposalLifecycleRecord
    ) -> ProposalLifecycleRecord:
        counts = {
            "confirmed": 0,
            "outcome_contradicted": 0,
            "context_missed": 0,
            "unknown_transient": 0,
            "dependency_unavailable": 1,
            "evaluated_windows": 0,
            "replacement_candidate_state": "",
            "replacement_candidate_count": 0,
        }
        return replace(
            record,
            confirmed_count=0,
            outcome_contradiction_count=0,
            context_miss_count=0,
            unknown_transient_count=0,
            dependency_unavailable_count=1,
            evaluated_window_count=0,
            replacement_candidate_state="",
            replacement_candidate_count=0,
            lifecycle_review_kind=_lifecycle_review_kind(
                counts=counts,
                policy=self._lifecycle_policy,
            ),
        )

    async def _async_submit_lifecycle_suggestion(self, record: ProposalLifecycleRecord) -> None:
        if not record.lifecycle_review_kind:
            return
        proposal = self._lifecycle_suggestion_proposal(record)
        if proposal is None:
            return
        await self.async_submit_proposal(proposal)

    def _lifecycle_suggestion_proposal(
        self, record: ProposalLifecycleRecord
    ) -> ReactionProposal | None:
        source = self._proposal_by_id(record.proposal_id)
        if not isinstance(source, ReactionProposal):
            return None

        kind = str(record.lifecycle_review_kind or "").strip()
        if kind not in {
            "replacement_suggestion",
            "retirement_suggestion",
            "maintenance_suggestion",
        }:
            return None

        cfg = _lifecycle_suggestion_config(
            record=record,
            source=source,
            policy=self._lifecycle_policy,
            link=self._classify_reaction_link_state(record),
        )
        rejection_key = str(cfg["rejection_key"])
        return ReactionProposal(
            analyzer_id="proposal_lifecycle",
            reaction_type=PROPOSAL_LIFECYCLE_SUGGESTION_TYPE,
            description=_lifecycle_suggestion_description(cfg),
            confidence=1.0,
            origin="learned",
            followup_kind=kind,  # type: ignore[arg-type]
            identity_key=f"{PROPOSAL_LIFECYCLE_SUGGESTION_TYPE}:{rejection_key}",
            suggested_reaction_config=cfg,
            target_reaction_id=record.linked_reaction_id,
            target_reaction_type=record.linked_reaction_type,
        )

    async def _sync_accepted_lifecycle_records(self) -> None:
        for proposal in self._proposals:
            await self._sync_lifecycle_record_for(proposal)

    async def _sync_lifecycle_record_for(self, proposal: ProposalItem) -> None:
        if self._lifecycle_store is None:
            return
        if not isinstance(proposal, ReactionProposal):
            return
        if proposal.status != "accepted" or proposal.reaction_type != HOUSE_STATE_PROPOSAL_TYPE:
            return
        record = self._lifecycle_record_for_house_state_proposal(proposal)
        await self._lifecycle_store.async_upsert_missing(record)

    def _lifecycle_record_for_house_state_proposal(
        self, proposal: ReactionProposal
    ) -> ProposalLifecycleRecord:
        accepted_at = proposal.updated_at or proposal.created_at
        linked_reaction_id = str(proposal.target_reaction_id or "").strip()
        linked_reaction_type = str(
            proposal.target_reaction_type or proposal.reaction_type or ""
        ).strip()
        return ProposalLifecycleRecord(
            proposal_id=proposal.proposal_id,
            identity_key=self._identity_key(proposal),
            plugin_family="house_state",
            proposal_type=HOUSE_STATE_PROPOSAL_TYPE,
            accepted_at=accepted_at,
            linked_reaction_id=linked_reaction_id,
            linked_reaction_type=linked_reaction_type,
            reaction_link_state="linked_clean" if linked_reaction_id else "",
            monitoring_window_start=accepted_at,
        )

    def _lifecycle_diagnostics(self) -> dict[str, Any]:
        if self._lifecycle_store is None:
            return {
                "enabled": False,
                "record_count": 0,
                "records": [],
            }
        diagnostics = dict(self._lifecycle_store.diagnostics())
        diagnostics["enabled"] = True
        diagnostics["records"] = [
            self._lifecycle_record_diagnostics(record) for record in self._lifecycle_store.records()
        ]
        return diagnostics

    def _lifecycle_record_diagnostics(self, record: ProposalLifecycleRecord) -> dict[str, Any]:
        payload = record.as_dict()
        link = self._classify_reaction_link_state(record)
        payload["reaction_link_state"] = link["state"]
        payload["reaction_link_state_reason"] = link["reason"]
        payload["resolved_reaction_id"] = link["resolved_reaction_id"]
        payload["configured_reaction_type"] = link["configured_reaction_type"]
        payload["policy"] = _lifecycle_policy_diagnostics(self._lifecycle_policy)
        payload["lifecycle_review_kind"] = record.lifecycle_review_kind or _lifecycle_review_kind(
            counts=_record_lifecycle_counts(record),
            policy=self._lifecycle_policy,
        )
        return payload

    def _classify_reaction_link_state(self, record: ProposalLifecycleRecord) -> dict[str, str]:
        configured = self._configured_reactions()
        linked_id = str(record.linked_reaction_id or record.proposal_id or "").strip()
        if not linked_id:
            return _reaction_link_result("reaction_missing", reason="missing_link")

        if linked_id in configured and not isinstance(configured.get(linked_id), dict):
            return _reaction_link_result(
                "linked_uninterpretable",
                reason="configured_reaction_payload_malformed",
                resolved_reaction_id=linked_id,
            )

        reaction_id, reaction_cfg = self._find_lifecycle_reaction(record, configured)
        if reaction_cfg is None:
            return _reaction_link_result(
                "reaction_missing",
                reason="configured_reaction_not_found",
                resolved_reaction_id=linked_id,
            )

        reaction_type = resolve_reaction_type(reaction_cfg)
        expected_type = str(record.linked_reaction_type or record.proposal_type or "").strip()
        if not reaction_type or (expected_type and reaction_type != expected_type):
            return _reaction_link_result(
                "linked_uninterpretable",
                reason="reaction_type_mismatch",
                resolved_reaction_id=reaction_id,
                configured_reaction_type=reaction_type,
            )

        source_proposal_id = str(reaction_cfg.get("source_proposal_id") or "").strip()
        source_identity = str(reaction_cfg.get("source_proposal_identity_key") or "").strip()
        has_source_metadata = bool(source_proposal_id or source_identity)
        source_matches = source_proposal_id == record.proposal_id or (
            bool(record.identity_key) and source_identity == record.identity_key
        )
        if has_source_metadata and not source_matches:
            return _reaction_link_result(
                "linked_uninterpretable",
                reason="source_metadata_mismatch",
                resolved_reaction_id=reaction_id,
                configured_reaction_type=reaction_type,
            )

        if str(reaction_cfg.get("author_kind") or "").strip() and str(
            reaction_cfg.get("author_kind") or ""
        ).strip() not in {"heima", "admin"}:
            return _reaction_link_result(
                "linked_uninterpretable",
                reason="author_kind_uninterpretable",
                resolved_reaction_id=reaction_id,
                configured_reaction_type=reaction_type,
            )

        proposal = self._proposal_by_id(record.proposal_id)
        if not isinstance(proposal, ReactionProposal):
            return _reaction_link_result(
                "linked_user_baseline",
                reason="accepted_proposal_history_unavailable",
                resolved_reaction_id=reaction_id,
                configured_reaction_type=reaction_type,
            )

        baseline = self._configured_baseline_for_proposal(proposal)
        if _lifecycle_comparable_config(reaction_cfg) == _lifecycle_comparable_config(baseline):
            return _reaction_link_result(
                "linked_clean",
                reason="matches_accepted_baseline",
                resolved_reaction_id=reaction_id,
                configured_reaction_type=reaction_type,
            )
        return _reaction_link_result(
            "linked_user_baseline",
            reason="interpretable_user_modified_baseline",
            resolved_reaction_id=reaction_id,
            configured_reaction_type=reaction_type,
        )

    def _configured_reactions(self) -> dict[str, Any]:
        if self._configured_reactions_provider is None:
            return {}
        configured = self._configured_reactions_provider()
        if not isinstance(configured, dict):
            return {}
        return configured

    def _find_lifecycle_reaction(
        self,
        record: ProposalLifecycleRecord,
        configured: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        linked_id = str(record.linked_reaction_id or record.proposal_id or "").strip()
        direct = configured.get(linked_id)
        if isinstance(direct, dict):
            return linked_id, direct

        for reaction_id, raw in configured.items():
            if not isinstance(raw, dict):
                continue
            cfg = _safe_dict(raw)
            if str(cfg.get("source_proposal_id") or "").strip() == record.proposal_id:
                return str(reaction_id), cfg
            if (
                record.identity_key
                and str(cfg.get("source_proposal_identity_key") or "").strip()
                == record.identity_key
            ):
                return str(reaction_id), cfg
        return linked_id, None

    def _proposal_by_id(self, proposal_id: str) -> ProposalItem | None:
        target = str(proposal_id or "").strip()
        for proposal in self._proposals:
            if proposal.proposal_id == target:
                return proposal
        return None

    @staticmethod
    def _configured_baseline_for_proposal(proposal: ReactionProposal) -> dict[str, Any]:
        configured = _safe_dict(proposal.suggested_reaction_config)
        configured.pop("reaction_class", None)
        configured["reaction_type"] = str(proposal.reaction_type or "").strip()
        configured["origin"] = proposal.origin
        configured["author_kind"] = "admin" if proposal.origin == "admin_authored" else "heima"
        configured["source_proposal_id"] = proposal.proposal_id
        if proposal.identity_key:
            configured["source_proposal_identity_key"] = proposal.identity_key
        if proposal.created_at:
            configured["created_at"] = proposal.created_at
        configured.setdefault("source_request", "learned_pattern")
        return configured

    def _write_sensor(self) -> None:
        if not self._sensor_writer:
            return
        pending = self.pending_proposals()
        ordered = self._sort_proposals(self._proposals)
        review_state = self._review_group_state()
        sensor_items = pending[: self.SENSOR_ITEMS_LIMIT]
        attributes = {
            "total": len(ordered),
            "pending": len(pending),
            "suppressed_in_review_count": len(review_state.suppressed_ids),
            "pending_items_total": len(pending),
            "pending_items_included": len(sensor_items),
            "pending_items_truncated": len(pending) > self.SENSOR_ITEMS_LIMIT,
            "by_origin": {
                "learned": sum(1 for p in ordered if getattr(p, "origin", "learned") == "learned"),
                "admin_authored": sum(
                    1 for p in ordered if getattr(p, "origin", "learned") == "admin_authored"
                ),
            },
            "by_followup_kind": {
                "discovery": sum(
                    1 for p in ordered if getattr(p, "followup_kind", "discovery") == "discovery"
                ),
                "tuning_suggestion": sum(
                    1
                    for p in ordered
                    if getattr(p, "followup_kind", "discovery") == "tuning_suggestion"
                ),
                "improvement": sum(
                    1 for p in ordered if getattr(p, "followup_kind", "discovery") == "improvement"
                ),
                "config_suggestion": sum(
                    1
                    for p in ordered
                    if getattr(p, "followup_kind", "discovery") == "config_suggestion"
                ),
                "replacement_suggestion": sum(
                    1
                    for p in ordered
                    if getattr(p, "followup_kind", "discovery") == "replacement_suggestion"
                ),
                "retirement_suggestion": sum(
                    1
                    for p in ordered
                    if getattr(p, "followup_kind", "discovery") == "retirement_suggestion"
                ),
                "maintenance_suggestion": sum(
                    1
                    for p in ordered
                    if getattr(p, "followup_kind", "discovery") == "maintenance_suggestion"
                ),
            },
            "by_type": _proposal_type_counts(ordered),
            "items": {
                p.proposal_id: {
                    "type": _proposal_type(p),
                    "confidence": round(p.confidence, 2),
                    "origin": getattr(p, "origin", "learned"),
                    "followup_kind": getattr(p, "followup_kind", "discovery"),
                    "status": p.status,
                    "updated_at": p.updated_at,
                    "target_reaction_id": getattr(p, "target_reaction_id", ""),
                    "target_reaction_type": getattr(p, "target_reaction_type", ""),
                    "improves_reaction_type": getattr(p, "improves_reaction_type", ""),
                    "improvement_reason": getattr(p, "improvement_reason", ""),
                    "context_snapshot": _safe_dict(_proposal_context_snapshot(p)),
                    "is_stale": self._is_stale(p),
                }
                for p in sensor_items
            },
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

    def _identity_key(self, proposal: ProposalItem) -> str:
        if proposal.identity_key:
            return proposal.identity_key
        if isinstance(proposal, ActivityProposal):
            return _activity_identity_key(proposal)

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

    def _review_grouping(self, proposal: ProposalItem) -> ProposalReviewGrouping | None:
        if not isinstance(proposal, ReactionProposal):
            return None
        hooks = self._learning_plugin_registry.lifecycle_hooks_for(proposal.reaction_type)
        if hooks is None or hooks.review_grouping is None:
            return None
        grouping = hooks.review_grouping(proposal)
        if grouping is None or not str(grouping.group_key or "").strip():
            return None
        return grouping

    def _review_group_scope(
        self,
        proposal: ProposalItem,
        grouping: ProposalReviewGrouping,
    ) -> tuple[str, str]:
        return (_proposal_type(proposal), str(grouping.group_key).strip())

    @staticmethod
    def _review_group_rank(grouping: ProposalReviewGrouping) -> tuple[Any, ...]:
        return (int(grouping.specificity_rank), *tuple(grouping.quality_rank or ()))

    def _visible_pending_proposals(self) -> list[ProposalItem]:
        state = self._review_group_state()
        return [
            proposal
            for proposal in self._proposals
            if proposal.status == "pending" and proposal.proposal_id in state.visible_pending_ids
        ]

    def _review_group_state(self) -> _ReviewGroupDerivedState:
        accepted_rank_by_group: dict[tuple[str, str], tuple[Any, ...]] = {}
        grouped_pending: dict[tuple[str, str], tuple[tuple[Any, ...], ProposalItem]] = {}
        ungrouped_pending_ids: set[str] = set()
        group_key_by_id: dict[str, str] = {}
        pending_scope_by_id: dict[str, tuple[str, str]] = {}
        groups: dict[str, list[str]] = {}

        for proposal in self._proposals:
            grouping = self._review_grouping(proposal)
            if grouping is None:
                continue
            scope = self._review_group_scope(proposal, grouping)
            group_key = self._diagnostic_review_group_key(scope)
            identity_key = self._identity_key(proposal)
            group_key_by_id[proposal.proposal_id] = group_key
            groups.setdefault(group_key, []).append(identity_key)

            if proposal.status != "accepted":
                continue
            rank = self._review_group_rank(grouping)
            current = accepted_rank_by_group.get(scope)
            if current is None or rank > current:
                accepted_rank_by_group[scope] = rank

        for proposal in self._proposals:
            if proposal.status != "pending":
                continue
            grouping = self._review_grouping(proposal)
            if grouping is None:
                ungrouped_pending_ids.add(proposal.proposal_id)
                continue

            scope = self._review_group_scope(proposal, grouping)
            pending_scope_by_id[proposal.proposal_id] = scope
            rank = self._review_group_rank(grouping)
            accepted_rank = accepted_rank_by_group.get(scope)
            if accepted_rank is not None and rank <= accepted_rank:
                continue

            current = grouped_pending.get(scope)
            if current is None or rank > current[0]:
                grouped_pending[scope] = (rank, proposal)

        representative_ids = {proposal.proposal_id for _rank, proposal in grouped_pending.values()}
        visible_pending_ids = frozenset(ungrouped_pending_ids | representative_ids)
        role_by_id: dict[str, str] = {}
        suppressed_ids: set[str] = set()
        for proposal_id in pending_scope_by_id:
            if proposal_id in representative_ids:
                role_by_id[proposal_id] = "representative"
            else:
                role_by_id[proposal_id] = "suppressed"
                suppressed_ids.add(proposal_id)

        return _ReviewGroupDerivedState(
            visible_pending_ids=visible_pending_ids,
            group_key_by_id=group_key_by_id,
            role_by_id=role_by_id,
            suppressed_ids=frozenset(suppressed_ids),
            groups={key: list(values) for key, values in sorted(groups.items())},
        )

    @staticmethod
    def _diagnostic_review_group_key(scope: tuple[str, str]) -> str:
        proposal_type, group_key = scope
        return f"{proposal_type}:{group_key}"

    @staticmethod
    def _sort_proposals(proposals: list[ProposalItem]) -> list[ProposalItem]:
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
                getattr(p, "analyzer_id", "ActivityAnalyzer"),
                _proposal_type(p),
                p.proposal_id,
            ),
        )

    def _is_stale(self, proposal: ProposalItem) -> bool:
        if proposal.status != "pending":
            return False
        last_observed_at = self._parse_ts(proposal.last_observed_at)
        if last_observed_at is None:
            return True
        return (datetime.now(UTC) - last_observed_at) > self._stale_after

    def _stale_reason(self, proposal: ProposalItem) -> str | None:
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

    def _prune_stale_pending(self, proposals: list[ProposalItem]) -> list[ProposalItem]:
        retained: list[ProposalItem] = []
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
    def _proposal_from_storage(raw: dict[str, Any]) -> ProposalItem | None:
        activity_proposal = ActivityProposal.from_dict(raw)
        if activity_proposal is not None:
            return activity_proposal
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
        reaction_type = resolve_reaction_type(cfg) or proposal.reaction_type
        primary_bucket = cfg.get("primary_bucket")
        corroboration_bucket = cfg.get("corroboration_bucket")
        summary = {
            "reaction_type": reaction_type,
            "room_id": cfg.get("room_id"),
            "house_state": cfg.get("house_state"),
            "weekday": cfg.get("weekday"),
            "scheduled_min": cfg.get("scheduled_min"),
            "primary_signal_name": cfg.get("primary_signal_name"),
            "primary_bucket": primary_bucket,
            "corroboration_signal_name": cfg.get("corroboration_signal_name"),
            "corroboration_bucket": corroboration_bucket,
            "episodes_observed": cfg.get("episodes_observed"),
            "corroborated_episodes": cfg.get("corroborated_episodes"),
        }
        primary_entities = cfg.get("primary_signal_entities")
        if isinstance(primary_entities, list):
            summary["primary_signal_entities_count"] = len(primary_entities)
        corroboration_entities = cfg.get("corroboration_signal_entities")
        if isinstance(corroboration_entities, list):
            summary["corroboration_signal_entities_count"] = len(corroboration_entities)
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
            "followup_entity_min_ratio",
            "followup_entity_min_episodes",
            "corroboration_promote_min_ratio",
            "corroboration_promote_min_episodes",
            "primary_signal",
            "corroboration_signals",
            "followup_signal",
            "matched_primary_entities",
            "matched_corroboration_entities",
            "observed_followup_entities",
            "positive_episode_count",
            "competing_explanation_type",
            "selected_context_condition",
            "context_conditions_considered",
            "concentration",
            "lift",
            "negative_episode_count",
            "contrast_status",
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


def _house_state_lifecycle_baseline(proposal: ReactionProposal) -> dict[str, Any] | None:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    snapshot = _safe_dict(cfg.get("context_snapshot"))
    weekday = _safe_int(snapshot.get("weekday"), default=-1)
    hour_bucket = _safe_int(snapshot.get("hour_bucket"), default=-1)
    predicted_state = _token(snapshot.get("predicted_state") or cfg.get("predicted_state"))
    if weekday < 0 or hour_bucket < 0 or not predicted_state:
        return None
    rooms = snapshot.get("rooms")
    if not isinstance(rooms, list):
        rooms = []
    return {
        "weekday": weekday,
        "hour_bucket": hour_bucket,
        "rooms": frozenset(str(room).strip() for room in rooms if str(room).strip()),
        "anyone_home": bool(snapshot.get("anyone_home")),
        "predicted_state": predicted_state,
    }


def _house_state_lifecycle_counts(
    events: list[Any],
    baseline: dict[str, Any],
    *,
    window_limit: int,
) -> dict[str, Any]:
    windows = _house_state_lifecycle_windows(events, baseline)
    window_items = list(windows.items())[-max(1, int(window_limit)) :]
    outcome_counts: dict[str, int] = {
        "confirmed": 0,
        "outcome_contradicted": 0,
        "context_missed": 0,
        "unknown_transient": 0,
        "dependency_unavailable": 0,
    }
    last_confirmed_at = ""
    replacement_candidate_state = ""
    replacement_candidate_count = 0
    counts: dict[str, Any] = {
        **outcome_counts,
        "evaluated_windows": len(window_items),
        "last_confirmed_at": last_confirmed_at,
        "replacement_candidate_state": replacement_candidate_state,
        "replacement_candidate_count": replacement_candidate_count,
    }
    replacement_counts: dict[str, int] = {}
    for _window_key, window_events in window_items:
        outcome = _classify_house_state_lifecycle_window(window_events, baseline)
        outcome_class = str(outcome["class"])
        outcome_counts[outcome_class] += 1
        if outcome_class == "outcome_contradicted":
            state = str(outcome.get("state") or "")
            if state:
                replacement_counts[state] = replacement_counts.get(state, 0) + 1
        if outcome_class == "confirmed":
            last_ts = max(str(getattr(event, "ts", "") or "") for event in window_events)
            if last_ts > last_confirmed_at:
                last_confirmed_at = last_ts
    candidate_state = _dominant_key(replacement_counts)
    if candidate_state is not None:
        replacement_candidate_state = candidate_state
        replacement_candidate_count = replacement_counts[candidate_state]
    counts.update(outcome_counts)
    counts["last_confirmed_at"] = last_confirmed_at
    counts["replacement_candidate_state"] = replacement_candidate_state
    counts["replacement_candidate_count"] = replacement_candidate_count
    return counts


def _house_state_lifecycle_windows(
    events: list[Any],
    baseline: dict[str, Any],
) -> dict[str, list[Any]]:
    windows: dict[str, list[Any]] = {}
    expected_weekday = int(baseline["weekday"])
    expected_hour = int(baseline["hour_bucket"])
    for event in events:
        context = getattr(event, "context", None)
        if context is None:
            continue
        weekday = _safe_int(getattr(context, "weekday", None), default=-1)
        hour_bucket = _safe_int(getattr(context, "minute_of_day", None), default=-60) // 60
        if weekday != expected_weekday or hour_bucket != expected_hour:
            continue
        key = _house_state_lifecycle_window_key(event, weekday=weekday, hour_bucket=hour_bucket)
        windows.setdefault(key, []).append(event)
    return {key: windows[key] for key in sorted(windows)}


def _classify_house_state_lifecycle_window(
    events: list[Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    if not events:
        return {"class": "unknown_transient"}

    anyone_home = _dominant_bool(
        bool(_safe_int(getattr(getattr(event, "context", None), "occupants_count", 0), default=0))
        for event in events
    )
    if anyone_home is None:
        return {"class": "unknown_transient"}

    occupied_rooms: set[str] = set()
    for event in events:
        context = getattr(event, "context", None)
        occupied_rooms.update(
            str(room).strip()
            for room in getattr(context, "occupied_rooms", ()) or ()
            if str(room).strip()
        )
    expected_rooms = set(baseline.get("rooms") or ())
    if anyone_home != bool(baseline["anyone_home"]) or (
        expected_rooms and not expected_rooms.issubset(occupied_rooms)
    ):
        return {"class": "context_missed"}

    state = _dominant_house_state(events)
    if state is None:
        return {"class": "unknown_transient"}
    if state == baseline["predicted_state"]:
        return {"class": "confirmed", "state": state}
    return {"class": "outcome_contradicted", "state": state}


def _lifecycle_review_kind(
    *,
    counts: dict[str, Any],
    policy: AcceptedRuleLifecyclePolicy,
) -> str:
    if _safe_int(counts.get("dependency_unavailable"), default=0) >= policy.maintenance_threshold:
        return "maintenance_suggestion"
    if (
        _safe_int(counts.get("replacement_candidate_count"), default=0)
        >= policy.replacement_threshold
    ):
        return "replacement_suggestion"
    if _safe_int(counts.get("context_missed"), default=0) >= policy.retirement_threshold:
        return "retirement_suggestion"
    if (
        _safe_int(counts.get("outcome_contradicted"), default=0) >= policy.retirement_threshold
        and _safe_int(counts.get("replacement_candidate_count"), default=0)
        < policy.replacement_threshold
    ):
        return "retirement_suggestion"
    return ""


def _record_lifecycle_counts(record: ProposalLifecycleRecord) -> dict[str, Any]:
    return {
        "confirmed": record.confirmed_count,
        "outcome_contradicted": record.outcome_contradiction_count,
        "context_missed": record.context_miss_count,
        "unknown_transient": record.unknown_transient_count,
        "dependency_unavailable": record.dependency_unavailable_count,
        "evaluated_windows": record.evaluated_window_count,
        "replacement_candidate_state": record.replacement_candidate_state,
        "replacement_candidate_count": record.replacement_candidate_count,
    }


def _lifecycle_policy_diagnostics(policy: AcceptedRuleLifecyclePolicy) -> dict[str, int]:
    return {
        "required_observations": policy.required_observations,
        "replacement_threshold": policy.replacement_threshold,
        "retirement_multiplier": policy.retirement_multiplier,
        "retirement_threshold": policy.retirement_threshold,
        "maintenance_threshold": policy.maintenance_threshold,
        "rolling_window_limit": policy.rolling_window_limit,
    }


def _lifecycle_suggestion_config(
    *,
    record: ProposalLifecycleRecord,
    source: ReactionProposal,
    policy: AcceptedRuleLifecyclePolicy,
    link: dict[str, str],
) -> dict[str, Any]:
    source_cfg = _safe_dict(source.suggested_reaction_config)
    accepted_context = _safe_dict(source_cfg.get("context_snapshot"))
    kind = str(record.lifecycle_review_kind or "").strip()
    evidence = _record_lifecycle_counts(record)
    cfg: dict[str, Any] = {
        "proposal_type": PROPOSAL_LIFECYCLE_SUGGESTION_TYPE,
        "lifecycle_suggestion_type": kind,
        "lifecycle_generation": record.lifecycle_generation,
        "target_proposal_id": record.proposal_id,
        "target_identity_key": record.identity_key,
        "target_reaction_id": record.linked_reaction_id,
        "target_reaction_type": record.linked_reaction_type,
        "accepted_context_snapshot": accepted_context,
        "accepted_predicted_state": str(source_cfg.get("predicted_state") or ""),
        "evidence": evidence,
        "policy": _lifecycle_policy_diagnostics(policy),
        "reaction_link_state": link.get("state", ""),
        "reaction_link_state_reason": link.get("reason", ""),
    }
    if kind == "replacement_suggestion":
        proposed_state = str(record.replacement_candidate_state or "").strip()
        proposed_context = dict(accepted_context)
        if proposed_state:
            proposed_context["predicted_state"] = proposed_state
        cfg.update(
            {
                "proposed_predicted_state": proposed_state,
                "proposed_context_snapshot": proposed_context,
                "proposed_action": "replace_accepted_rule_after_review",
            }
        )
    elif kind == "retirement_suggestion":
        reason = (
            "context_drift"
            if record.context_miss_count >= policy.retirement_threshold
            else "unconfirmed_outcome"
        )
        cfg.update(
            {
                "retirement_reason": reason,
                "proposed_action": "retire_accepted_rule_after_review",
            }
        )
    elif kind == "maintenance_suggestion":
        cfg.update(
            {
                "maintenance_reason": link.get("reason", "") or "dependency_unavailable",
                "proposed_action": "review_rule_dependencies_after_review",
            }
        )
    cfg["rejection_key"] = _lifecycle_rejection_key(cfg)
    return cfg


def _lifecycle_rejection_key(cfg: dict[str, Any]) -> str:
    parts = [
        str(cfg.get("lifecycle_suggestion_type") or ""),
        str(cfg.get("target_proposal_id") or ""),
        f"generation:{cfg.get('lifecycle_generation') or 1}",
        str(cfg.get("proposed_predicted_state") or ""),
        str(cfg.get("retirement_reason") or ""),
        str(cfg.get("maintenance_reason") or ""),
    ]
    evidence = _safe_dict(cfg.get("evidence"))
    parts.extend(
        [
            f"replacement:{evidence.get('replacement_candidate_state') or ''}:"
            f"{evidence.get('replacement_candidate_count') or 0}",
            f"contradicted:{evidence.get('outcome_contradicted') or 0}",
            f"context_missed:{evidence.get('context_missed') or 0}",
            f"dependency:{evidence.get('dependency_unavailable') or 0}",
        ]
    )
    return "|".join(parts)


def _lifecycle_suggestion_description(cfg: dict[str, Any]) -> str:
    kind = str(cfg.get("lifecycle_suggestion_type") or "")
    accepted = str(cfg.get("accepted_predicted_state") or "unknown")
    if kind == "replacement_suggestion":
        proposed = str(cfg.get("proposed_predicted_state") or "unknown")
        return f"Lifecycle suggestion: replace learned house-state rule {accepted} -> {proposed}."
    if kind == "retirement_suggestion":
        reason = str(cfg.get("retirement_reason") or "unconfirmed_outcome")
        return f"Lifecycle suggestion: retire learned house-state rule ({reason})."
    if kind == "maintenance_suggestion":
        reason = str(cfg.get("maintenance_reason") or "dependency_unavailable")
        return f"Lifecycle suggestion: review learned rule maintenance ({reason})."
    return "Lifecycle suggestion for learned rule."


def _applied_lifecycle_record(
    *,
    record: ProposalLifecycleRecord,
    suggestion_id: str,
    suggestion_kind: str,
    applied_at: str,
) -> ProposalLifecycleRecord:
    if suggestion_kind == "replacement_suggestion":
        return replace(
            record,
            replaced_by=record.replaced_by or suggestion_id,
            last_lifecycle_review_at=record.last_lifecycle_review_at or applied_at,
        )
    if suggestion_kind == "retirement_suggestion":
        return replace(
            record,
            retired_at=record.retired_at or applied_at,
            last_lifecycle_review_at=record.last_lifecycle_review_at or applied_at,
        )
    if suggestion_kind == "maintenance_suggestion":
        return replace(
            record,
            last_lifecycle_review_at=record.last_lifecycle_review_at or applied_at,
        )
    return record


def _replacement_house_state_config(
    *,
    record: ProposalLifecycleRecord,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    if record.proposal_type != HOUSE_STATE_PROPOSAL_TYPE:
        return {}

    proposed_context = _safe_dict(cfg.get("proposed_context_snapshot"))
    proposed_state = _token(
        proposed_context.get("predicted_state") or cfg.get("proposed_predicted_state")
    )
    if not proposed_state:
        return {}

    weekday = _safe_int(proposed_context.get("weekday"), default=-1)
    hour_bucket = _safe_int(proposed_context.get("hour_bucket"), default=-1)
    if weekday < 0 or hour_bucket < 0:
        return {}

    raw_rooms = proposed_context.get("rooms")
    rooms = [
        str(room).strip()
        for room in (raw_rooms if isinstance(raw_rooms, list) else [])
        if str(room).strip()
    ]
    learning_context = _safe_dict(proposed_context.get("learning_context"))
    context_key = house_state_context_key(
        weekday=weekday,
        hour_bucket=hour_bucket,
        rooms=rooms,
        anyone_home=bool(proposed_context.get("anyone_home")),
        predicted_state=proposed_state,
        learning_context=learning_context,
    )
    proposed_context["predicted_state"] = proposed_state
    proposed_context["rooms"] = rooms
    proposed_context["learning_context"] = learning_context
    return {
        "context_key": context_key,
        "context_snapshot": proposed_context,
        "predicted_state": proposed_state,
        "lifecycle_replaces_proposal_id": record.proposal_id,
    }


def _replacement_house_state_description(
    fallback: str,
    proposed_context: dict[str, Any],
) -> str:
    proposed_state = str(proposed_context.get("predicted_state") or "").strip()
    if not proposed_state:
        return fallback
    return f"Learned house-state context predicts {proposed_state}."


def _dominant_house_state(events: list[Any]) -> str | None:
    counts: dict[str, int] = {}
    for event in events:
        state = _house_state_from_event(event)
        if state in {"", "unknown", "unavailable", "none"}:
            continue
        counts[state] = counts.get(state, 0) + 1
    return _dominant_key(counts)


def _house_state_from_event(event: Any) -> str:
    data = getattr(event, "data", {})
    if getattr(event, "event_type", "") == "house_state" and isinstance(data, dict):
        state = _token(data.get("to_state"))
        if state:
            return state
    context = getattr(event, "context", None)
    return _token(getattr(context, "house_state", ""))


def _dominant_bool(values: Any) -> bool | None:
    counts = {True: 0, False: 0}
    for value in values:
        counts[bool(value)] += 1
    if counts[True] == counts[False]:
        return None
    return counts[True] > counts[False]


def _dominant_key(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return None
    return ordered[0][0]


def _house_state_lifecycle_window_key(event: Any, *, weekday: int, hour_bucket: int) -> str:
    ts = str(getattr(event, "ts", "") or "")
    day = ts.split("T", 1)[0] if "T" in ts else ts[:10]
    return f"{day}:weekday:{weekday}:hour:{hour_bucket}"


def _lifecycle_comparable_config(value: dict[str, Any]) -> str:
    excluded = {
        "last_tuned_at",
        "last_tuning_followup_kind",
        "last_tuning_origin",
        "last_tuning_proposal_id",
    }
    comparable = {key: item for key, item in value.items() if key not in excluded}
    return json.dumps(comparable, sort_keys=True, separators=(",", ":"), default=str)


def _reaction_link_result(
    state: str,
    *,
    reason: str,
    resolved_reaction_id: str = "",
    configured_reaction_type: str = "",
) -> dict[str, str]:
    return {
        "state": state,
        "reason": reason,
        "resolved_reaction_id": resolved_reaction_id,
        "configured_reaction_type": configured_reaction_type,
    }


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _proposal_type(proposal: ProposalItem) -> str:
    if isinstance(proposal, ActivityProposal):
        return proposal.proposal_type
    return proposal.reaction_type


def _proposal_description(proposal: ProposalItem) -> str:
    if isinstance(proposal, ActivityProposal):
        return (
            f"Composite activity '{proposal.activity_name}' observed "
            f"{proposal.occurrence_count} times."
        )
    return proposal.description


def _proposal_context_snapshot(proposal: ProposalItem) -> dict[str, Any]:
    if isinstance(proposal, ActivityProposal):
        return _activity_config_summary(proposal)
    return _safe_dict(_safe_dict(proposal.suggested_reaction_config).get("context_snapshot"))


def _proposal_review_rows(
    visible_pending: list[ProposalItem],
    bundle_view: ProposalReviewBundleView,
) -> list[dict[str, Any]]:
    bundle_by_first_member = {
        bundle.proposal_ids[0]: bundle
        for bundle in bundle_view.bundles
        if bundle.proposal_ids
    }
    bundled_ids = set(bundle_view.bundled_proposal_ids)
    rows: list[dict[str, Any]] = []
    for proposal in visible_pending:
        bundle = bundle_by_first_member.get(proposal.proposal_id)
        if bundle is not None:
            rows.append(
                {
                    "row_type": "temporal_bundle",
                    "bundle_id": bundle.bundle_id,
                    "bundle_type": bundle.bundle_type,
                    "proposal_ids": list(bundle.proposal_ids),
                    "identity_keys": list(bundle.identity_keys),
                    "member_count": bundle.member_count,
                    "weekday": bundle.weekday,
                    "start_hour_bucket": bundle.start_hour_bucket,
                    "end_hour_bucket": bundle.end_hour_bucket,
                    "anyone_home": bundle.anyone_home,
                    "predicted_state": bundle.predicted_state,
                    "confidence_min": bundle.confidence_min,
                    "confidence_max": bundle.confidence_max,
                    "confidence_avg": bundle.confidence_avg,
                    "support_total": bundle.support_total,
                    "total_observations": bundle.total_observations,
                }
            )
            continue
        if proposal.proposal_id in bundled_ids:
            continue
        rows.append(
            {
                "row_type": "proposal",
                "proposal_id": proposal.proposal_id,
                "type": _proposal_type(proposal),
                "identity_key": getattr(proposal, "identity_key", ""),
                "confidence": round(float(getattr(proposal, "confidence", 0.0) or 0.0), 2),
            }
        )
    return rows


def _temporal_bundle_member_map(
    bundle_view: ProposalReviewBundleView,
) -> dict[str, dict[str, Any]]:
    by_proposal_id: dict[str, dict[str, Any]] = {}
    for bundle in bundle_view.bundles:
        for proposal_id in bundle.proposal_ids:
            by_proposal_id[proposal_id] = {
                "key": bundle.grouping_key,
                "role": "member",
                "span_key": bundle.bundle_id,
                "member_count": bundle.member_count,
            }
    return by_proposal_id


def _activity_config_summary(proposal: ActivityProposal) -> dict[str, Any]:
    return {
        "activity_name": proposal.activity_name,
        "primitive_pattern": sorted(proposal.primitive_pattern),
        "context_conditions": _safe_dict(proposal.context_conditions),
        "occurrence_count": proposal.occurrence_count,
        "representative_ts": list(proposal.representative_ts),
        "bootstrap": bool(proposal.bootstrap),
    }


def _activity_identity_key(proposal: ActivityProposal) -> str:
    context_raw = json.dumps(
        _safe_dict(proposal.context_conditions),
        sort_keys=True,
        separators=(",", ":"),
    )
    pattern = ",".join(sorted(proposal.primitive_pattern))
    return f"{proposal.proposal_type}:{proposal.activity_name}:{pattern}:{context_raw}"


def _token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _latest_proposal_match(
    matches: list[tuple[int, ReactionProposal]],
) -> tuple[int, ReactionProposal] | None:
    if not matches:
        return None
    return max(matches, key=lambda item: item[1].updated_at or item[1].created_at)


def _configured_contextual_lighting_covers_darkness_candidate(
    candidate_cfg: dict[str, Any],
    reaction_cfg: dict[str, Any],
) -> bool:
    if (
        str(candidate_cfg.get("room_id") or "").strip()
        != str(reaction_cfg.get("room_id") or "").strip()
    ):
        return False
    candidate_signal = str(candidate_cfg.get("primary_signal_name") or "").strip().lower()
    reaction_signal = str(reaction_cfg.get("primary_signal_name") or "").strip().lower()
    if candidate_signal and reaction_signal and candidate_signal != reaction_signal:
        return False
    if candidate_signal and not reaction_signal:
        return False

    candidate_entities = _sorted_strings(candidate_cfg.get("primary_signal_entities"))
    reaction_entities = _sorted_strings(reaction_cfg.get("primary_signal_entities"))
    if candidate_entities and reaction_entities and candidate_entities != reaction_entities:
        return False

    profiles = reaction_cfg.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        return False
    return any(
        isinstance(profile, dict) and isinstance(profile.get("entity_steps"), list)
        for profile in profiles.values()
    )


def _proposal_type_counts(proposals: list[ProposalItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for proposal in proposals:
        proposal_type = _proposal_type(proposal)
        counts[proposal_type] = counts.get(proposal_type, 0) + 1
    return dict(sorted(counts.items()))


def _sorted_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item).strip() for item in value if str(item).strip())
