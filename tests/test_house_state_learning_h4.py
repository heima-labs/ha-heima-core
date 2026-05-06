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
    coordinator._proposal_engine = SimpleNamespace(async_submit_proposal=AsyncMock())
    coordinator._sync_house_state_approval_state = MagicMock()

    await coordinator._async_submit_house_state_candidates()

    coordinator._sync_house_state_approval_state.assert_called_once()
    coordinator._proposal_engine.async_submit_proposal.assert_awaited_once()
    proposal = coordinator._proposal_engine.async_submit_proposal.await_args.args[0]
    assert proposal.identity_key == f"{HOUSE_STATE_PROPOSAL_TYPE}:ctx-submit"


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

    result = await coordinator.async_review_house_state_proposal(
        "proposal-lighting",
        decision="approved",
        approved_by="installer",
    )

    assert result is True
    assert coordinator._approval_store.records() == ()
    coordinator._sync_house_state_approval_state.assert_not_called()
