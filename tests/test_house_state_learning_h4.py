"""Tests for Phase H4 house-state learning coordinator wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.const import OPT_ROOMS
from custom_components.heima.coordinator import (
    HeimaCoordinator,
    _proposal_from_house_state_candidate,
    _sensorless_occupancy_room_ids,
)
from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.inference.approval_store import (
    ACTIVITY_PROPOSAL_TYPE,
    HOUSE_STATE_PROPOSAL_TYPE,
    ApprovalRecord,
)
from custom_components.heima.runtime.inference.modules.house_state_inference import (
    LearnedHouseStateCandidate,
)
from custom_components.heima.runtime.proposal_engine import ActivityProposal, ProposalEngine


def _candidate(context_key: str = "ctx-1") -> LearnedHouseStateCandidate:
    return LearnedHouseStateCandidate(
        proposal_type=HOUSE_STATE_PROPOSAL_TYPE,
        context_key=context_key,
        context_snapshot={
            "weekday": 1,
            "hour_bucket": 8,
            "rooms": ["bedroom"],
            "anyone_home": True,
            "predicted_state": "working",
            "learning_context": {},
        },
        predicted_state="working",
        support=4,
        total=5,
        confidence=0.8,
    )


def _activity_proposal(*, bootstrap: bool = False) -> ActivityProposal:
    return ActivityProposal(
        proposal_id="proposal-activity",
        activity_name="movie_night",
        primitive_pattern=frozenset({"tv", "relax"}),
        context_conditions={"room_id": "living_room", "hour_range": [20, 21]},
        occurrence_count=12,
        confidence=0.9,
        representative_ts=["2026-05-01T20:00:00+00:00"],
        bootstrap=bootstrap,
        identity_key="activity-key",
    )


class _ApprovalStoreStub:
    def __init__(self, records: list[ApprovalRecord] | None = None) -> None:
        self._records = list(records or [])
        self.async_record = AsyncMock(side_effect=self._record)
        self.async_flush = AsyncMock()

    def records(self) -> tuple[ApprovalRecord, ...]:
        return tuple(self._records)

    async def _record(self, record: ApprovalRecord) -> None:
        self._records.append(record)


class _ServicesStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, bool]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict,
        blocking: bool = False,
    ) -> None:
        self.calls.append((domain, service, dict(data), blocking))


class _LifecycleRegistryStub:
    def lifecycle_hooks_for(self, reaction_type: str) -> None:
        return None


def _record(
    *,
    context_key: str,
    decision: str,
    proposal_type: str = HOUSE_STATE_PROPOSAL_TYPE,
) -> ApprovalRecord:
    return ApprovalRecord(
        proposal_id=f"proposal-{context_key}",
        proposal_type=proposal_type,
        decision=decision,  # type: ignore[arg-type]
        approved_by="resident",
        context_key=context_key,
        context_snapshot={"context_key": context_key},
    )


def test_house_state_candidate_builds_stable_identity_key() -> None:
    proposal = _proposal_from_house_state_candidate(_candidate("ctx-alpha"))

    assert proposal.reaction_type == HOUSE_STATE_PROPOSAL_TYPE
    assert proposal.analyzer_id == "house_state_inference"
    assert proposal.identity_key == f"{HOUSE_STATE_PROPOSAL_TYPE}:ctx-alpha"
    assert proposal.suggested_reaction_config["context_key"] == "ctx-alpha"
    assert proposal.suggested_reaction_config["context_snapshot"]["predicted_state"] == "working"


def test_proposal_sensor_includes_house_state_context_snapshot() -> None:
    written: list[tuple[int, dict]] = []

    engine = ProposalEngine.__new__(ProposalEngine)
    engine._sensor_writer = lambda count, attrs: written.append((count, attrs))
    engine._stale_after = ProposalEngine.DEFAULT_STALE_AFTER
    engine._learning_plugin_registry = _LifecycleRegistryStub()
    proposal = _proposal_from_house_state_candidate(_candidate("ctx-sensor"))
    engine._proposals = [proposal]

    engine._write_sensor()

    assert written[0][0] == 1
    item = written[0][1]["items"][proposal.proposal_id]
    assert item["type"] == HOUSE_STATE_PROPOSAL_TYPE
    assert item["context_snapshot"]["predicted_state"] == "working"


def test_sync_house_state_approval_state_passes_approved_and_rejected_sets() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._approval_store = _ApprovalStoreStub(
        [
            _record(context_key="approved-key", decision="approved"),
            _record(context_key="rejected-key", decision="rejected"),
            _record(
                context_key="other-key",
                decision="approved",
                proposal_type="activity_discovered",
            ),
        ]
    )
    coordinator._house_state_module = SimpleNamespace(sync_approval_state=MagicMock())

    coordinator._sync_house_state_approval_state()

    coordinator._house_state_module.sync_approval_state.assert_called_once_with(
        {"approved-key"},
        {"rejected-key"},
    )


def test_sync_activity_approval_state_passes_only_approved_activity_proposals() -> None:
    activity = _activity_proposal()
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._approval_store = _ApprovalStoreStub(
        [
            ApprovalRecord(
                proposal_id=activity.proposal_id,
                proposal_type=ACTIVITY_PROPOSAL_TYPE,
                decision="approved",
                approved_by="resident",
                context_key="activity-key",
                context_snapshot={
                    "activity_name": "movie_night",
                    "primitive_pattern": ["relax", "tv"],
                    "context_conditions": {"room_id": "living_room"},
                },
            ),
            _record(context_key="house-key", decision="approved"),
        ]
    )
    coordinator._proposal_engine = SimpleNamespace(proposal_by_id=MagicMock(return_value=activity))
    coordinator._activity_module = SimpleNamespace(sync_approved_proposals=MagicMock())

    coordinator._sync_activity_approval_state()

    coordinator._activity_module.sync_approved_proposals.assert_called_once_with([activity])


@pytest.mark.asyncio
async def test_review_activity_proposal_records_approved_decision_and_syncs() -> None:
    proposal = _activity_proposal(bootstrap=True)
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=True),
        async_reject_proposal=AsyncMock(return_value=False),
    )
    coordinator._approval_store = _ApprovalStoreStub()
    coordinator._sync_activity_approval_state = MagicMock()
    coordinator._notified_activity_proposal_keys = {proposal.identity_key}

    result = await coordinator.async_review_activity_proposal(
        proposal.proposal_id,
        decision="approved",
        approved_by="resident",
    )

    assert result is True
    coordinator._proposal_engine.async_accept_proposal.assert_awaited_once_with(
        proposal.proposal_id
    )
    record = coordinator._approval_store.records()[0]
    assert record.proposal_type == ACTIVITY_PROPOSAL_TYPE
    assert record.decision == "approved"
    assert record.approved_by == "resident"
    assert record.context_snapshot["activity_name"] == "movie_night"
    assert record.context_snapshot["primitive_pattern"] == ["relax", "tv"]
    assert record.metadata["bootstrap"] is True
    coordinator._approval_store.async_flush.assert_awaited_once()
    coordinator._sync_activity_approval_state.assert_called_once()
    assert proposal.identity_key not in coordinator._notified_activity_proposal_keys


@pytest.mark.asyncio
async def test_review_activity_proposal_records_rejection() -> None:
    proposal = _activity_proposal()
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=False),
        async_reject_proposal=AsyncMock(return_value=True),
    )
    coordinator._approval_store = _ApprovalStoreStub()
    coordinator._sync_activity_approval_state = MagicMock()
    coordinator._notified_activity_proposal_keys = {proposal.identity_key}

    result = await coordinator.async_review_activity_proposal(
        proposal.proposal_id,
        decision="rejected",
        approved_by="installer",
    )

    assert result is True
    coordinator._proposal_engine.async_reject_proposal.assert_awaited_once_with(
        proposal.proposal_id
    )
    record = coordinator._approval_store.records()[0]
    assert record.decision == "rejected"
    assert record.approved_by == "installer"
    coordinator._sync_activity_approval_state.assert_called_once()


@pytest.mark.asyncio
async def test_review_proposal_dispatches_by_proposal_type() -> None:
    proposal = _activity_proposal()
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(proposal_by_id=MagicMock(return_value=proposal))
    coordinator.async_review_house_state_proposal = AsyncMock(return_value=False)
    coordinator.async_review_activity_proposal = AsyncMock(return_value=True)

    result = await coordinator.async_review_proposal(
        proposal.proposal_id,
        decision="approved",
        approved_by="resident",
    )

    assert result is True
    coordinator.async_review_activity_proposal.assert_awaited_once_with(
        proposal.proposal_id,
        decision="approved",
        approved_by="resident",
    )
    coordinator.async_review_house_state_proposal.assert_not_awaited()


@pytest.mark.asyncio
async def test_activity_proposal_notification_is_deduplicated() -> None:
    proposal = _activity_proposal()
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        proposal_by_id=MagicMock(return_value=proposal),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_activity_proposal_keys = set()

    await coordinator._async_notify_pending_activity_proposals()
    await coordinator._async_notify_pending_activity_proposals()

    assert len(services.calls) == 1
    assert services.calls[0][0:2] == ("persistent_notification", "create")
    assert "composite activity" in services.calls[0][2]["message"]


@pytest.mark.asyncio
async def test_analyze_inference_modules_includes_activity_module() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._sync_house_state_approval_state = MagicMock()
    coordinator._sync_activity_approval_state = MagicMock()
    coordinator._house_snapshot_store = object()
    coordinator._weekday_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._heating_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._house_state_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._activity_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._lighting_pattern_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._room_state_correlation_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._occupancy_inference_module = SimpleNamespace(analyze=AsyncMock())
    coordinator._async_submit_house_state_candidates = AsyncMock()
    coordinator._proposal_engine = SimpleNamespace(
        async_evaluate_house_state_lifecycle_opportunities=AsyncMock()
    )

    await coordinator._async_analyze_inference_modules()

    coordinator._sync_house_state_approval_state.assert_called_once()
    coordinator._sync_activity_approval_state.assert_called_once()
    coordinator._activity_module.analyze.assert_awaited_once_with(coordinator._house_snapshot_store)
    coordinator._lighting_pattern_module.analyze.assert_awaited_once_with(
        coordinator._house_snapshot_store
    )
    coordinator._room_state_correlation_module.analyze.assert_awaited_once_with(
        coordinator._house_snapshot_store
    )
    coordinator._occupancy_inference_module.analyze.assert_awaited_once_with(
        coordinator._house_snapshot_store
    )
    coordinator._async_submit_house_state_candidates.assert_awaited_once()
    coordinator._proposal_engine.async_evaluate_house_state_lifecycle_opportunities.assert_awaited_once()


def test_sensorless_occupancy_room_ids_uses_derived_rooms_without_occupancy_sources() -> None:
    assert _sensorless_occupancy_room_ids(
        {
            OPT_ROOMS: [
                {"room_id": "studio", "occupancy_mode": "derived", "occupancy_sources": []},
                {
                    "room_id": "living",
                    "occupancy_mode": "derived",
                    "occupancy_sources": ["binary_sensor.living_motion"],
                },
                {"room_id": "garage", "occupancy_mode": "none", "occupancy_sources": []},
                {"room_id": "guest", "learning_sources": ["sensor.guest_lux"]},
            ]
        }
    ) == {"guest", "studio"}


def test_sync_occupancy_inference_rooms_uses_current_options() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    module = SimpleNamespace(sync_sensorless_rooms=MagicMock())
    coordinator._occupancy_inference_module = module
    coordinator.entry = SimpleNamespace(
        options={
            OPT_ROOMS: [
                {"room_id": "studio", "occupancy_mode": "derived", "occupancy_sources": []},
                {
                    "room_id": "living",
                    "occupancy_mode": "derived",
                    "occupancy_sources": ["binary_sensor.living_motion"],
                },
            ]
        }
    )

    coordinator._sync_occupancy_inference_rooms()

    module.sync_sensorless_rooms.assert_called_once_with({"studio"})


@pytest.mark.asyncio
async def test_submit_house_state_candidates_submits_generated_proposals() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    candidate = _candidate("ctx-submit")
    coordinator._house_state_module = SimpleNamespace(generate_candidates=lambda: [candidate])
    submitted_proposals: list[ReactionProposal] = []

    async def _submit(proposal: ReactionProposal) -> str:
        proposal.proposal_id = "proposal-submit"
        submitted_proposals.append(proposal)
        return proposal.proposal_id

    coordinator._proposal_engine = SimpleNamespace(
        async_submit_proposal=AsyncMock(side_effect=_submit),
        pending_proposals=lambda: list(submitted_proposals),
    )
    coordinator._sync_house_state_approval_state = MagicMock()
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_house_state_proposal_keys = set()

    await coordinator._async_submit_house_state_candidates()

    coordinator._sync_house_state_approval_state.assert_called_once()
    coordinator._proposal_engine.async_submit_proposal.assert_awaited_once()
    proposal = coordinator._proposal_engine.async_submit_proposal.await_args.args[0]
    assert proposal.identity_key == f"{HOUSE_STATE_PROPOSAL_TYPE}:ctx-submit"
    assert len(services.calls) == 1
    assert services.calls[0][0:2] == ("persistent_notification", "create")
    assert "Open the Heima dashboard" in services.calls[0][2]["message"]


@pytest.mark.asyncio
async def test_house_state_candidate_notification_is_deduplicated() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    candidate = _candidate("ctx-dedup")
    coordinator._house_state_module = SimpleNamespace(generate_candidates=lambda: [candidate])
    submitted_proposals: list[ReactionProposal] = []

    async def _submit(proposal: ReactionProposal) -> str:
        proposal.proposal_id = "proposal-dedup"
        submitted_proposals.append(proposal)
        return proposal.proposal_id

    coordinator._proposal_engine = SimpleNamespace(
        async_submit_proposal=AsyncMock(side_effect=_submit),
        pending_proposals=lambda: list(submitted_proposals),
    )
    coordinator._sync_house_state_approval_state = MagicMock()
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_house_state_proposal_keys = set()

    await coordinator._async_submit_house_state_candidates()
    await coordinator._async_submit_house_state_candidates()

    assert coordinator._proposal_engine.async_submit_proposal.await_count == 2
    assert len(services.calls) == 1


@pytest.mark.asyncio
async def test_review_house_state_proposal_records_approved_decision_and_syncs() -> None:
    candidate = _candidate("ctx-approved")
    proposal = _proposal_from_house_state_candidate(candidate)
    proposal.proposal_id = "proposal-approved"
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=True),
        async_reject_proposal=AsyncMock(return_value=False),
    )
    coordinator._approval_store = _ApprovalStoreStub()
    coordinator._sync_house_state_approval_state = MagicMock()
    coordinator._notified_house_state_proposal_keys = {proposal.identity_key}

    result = await coordinator.async_review_house_state_proposal(
        "proposal-approved",
        decision="approved",
        approved_by="resident",
    )

    assert result is True
    coordinator._proposal_engine.async_accept_proposal.assert_awaited_once_with("proposal-approved")
    record = coordinator._approval_store.records()[0]
    assert record.decision == "approved"
    assert record.approved_by == "resident"
    assert record.context_key == "ctx-approved"
    assert record.context_snapshot == candidate.context_snapshot
    coordinator._approval_store.async_flush.assert_awaited_once()
    coordinator._sync_house_state_approval_state.assert_called_once()
    assert proposal.identity_key not in coordinator._notified_house_state_proposal_keys


@pytest.mark.asyncio
async def test_review_house_state_proposal_records_rejected_installer_override() -> None:
    proposal = _proposal_from_house_state_candidate(_candidate("ctx-rejected"))
    proposal.proposal_id = "proposal-rejected"
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=False),
        async_reject_proposal=AsyncMock(return_value=True),
    )
    coordinator._approval_store = _ApprovalStoreStub()
    coordinator._sync_house_state_approval_state = MagicMock()
    coordinator._notified_house_state_proposal_keys = {proposal.identity_key}

    result = await coordinator.async_review_house_state_proposal(
        "proposal-rejected",
        decision="rejected",
        approved_by="installer",
    )

    assert result is True
    coordinator._proposal_engine.async_reject_proposal.assert_awaited_once_with("proposal-rejected")
    record = coordinator._approval_store.records()[0]
    assert record.decision == "rejected"
    assert record.approved_by == "installer"
    assert record.context_key == "ctx-rejected"
    coordinator._sync_house_state_approval_state.assert_called_once()
    assert proposal.identity_key not in coordinator._notified_house_state_proposal_keys


@pytest.mark.asyncio
async def test_review_non_house_state_proposal_preserves_existing_proposal_flow() -> None:
    proposal = ReactionProposal(
        proposal_id="proposal-lighting",
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=True),
        async_reject_proposal=AsyncMock(return_value=False),
    )
    coordinator._approval_store = _ApprovalStoreStub()
    coordinator._sync_house_state_approval_state = MagicMock()
    coordinator._notified_house_state_proposal_keys = set()

    result = await coordinator.async_review_house_state_proposal(
        "proposal-lighting",
        decision="approved",
        approved_by="installer",
    )

    assert result is True
    assert coordinator._approval_store.records() == ()
    coordinator._sync_house_state_approval_state.assert_not_called()
