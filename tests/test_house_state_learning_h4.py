"""Tests for Phase H4 house-state learning coordinator wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.coordinator import (
    HeimaCoordinator,
    _proposal_from_house_state_candidate,
)
from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.inference.approval_store import (
    HOUSE_STATE_PROPOSAL_TYPE,
    ApprovalRecord,
)
from custom_components.heima.runtime.inference.modules.house_state_inference import (
    LearnedHouseStateCandidate,
)
from custom_components.heima.runtime.proposal_engine import ProposalEngine


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


@pytest.mark.asyncio
async def test_submit_house_state_candidates_submits_generated_proposals() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    candidate = _candidate("ctx-submit")
    coordinator._house_state_module = SimpleNamespace(generate_candidates=lambda: [candidate])
    coordinator._proposal_engine = SimpleNamespace(
        async_submit_proposal=AsyncMock(return_value="proposal-submit")
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
    coordinator._proposal_engine = SimpleNamespace(
        async_submit_proposal=AsyncMock(return_value="proposal-dedup")
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
