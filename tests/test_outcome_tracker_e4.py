from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.inference.snapshot_store import HouseSnapshot
from custom_components.heima.runtime.outcome_tracker import OutcomeTracker, PendingVerification
from custom_components.heima.runtime.reactions.base import HeimaReaction


class DegradingReaction(HeimaReaction):
    @property
    def reaction_id(self) -> str:
        return "reaction.unreliable"

    def evaluate(self, history):  # noqa: ANN001
        return [ApplyStep(domain="lighting", target="light.test", action="light.turn_on")]


class FakeProposalEngine:
    def __init__(self, existing: ReactionProposal | None = None) -> None:
        self.existing = existing
        self.submitted: list[ReactionProposal] = []
        self.boosted: list[tuple[str, float]] = []

    def proposal_by_identity_key(self, identity_key: str) -> ReactionProposal | None:
        if self.existing is not None and self.existing.identity_key == identity_key:
            return self.existing
        return None

    async def async_submit_proposal(self, proposal: ReactionProposal) -> str:
        self.submitted.append(proposal)
        return proposal.proposal_id

    async def async_boost_confidence(self, reaction_id: str, delta: float) -> None:
        self.boosted.append((reaction_id, delta))


def _make_engine():
    from custom_components.heima.runtime.engine import HeimaEngine

    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.async_services.return_value = {}
    entry = MagicMock()
    entry.entry_id = "test"
    entry.options = {}
    engine = HeimaEngine(hass, entry)
    engine.register_reaction(DegradingReaction())
    return engine


def _snapshot() -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-05-04T10:00:00+00:00",
        weekday=0,
        minute_of_day=600,
        anyone_home=True,
        named_present=("stefano",),
        room_occupancy={"studio": True},
    )


def _pending(reaction_id: str, *, fired_at_ts: float) -> PendingVerification:
    return PendingVerification(
        reaction_id=reaction_id,
        expected_event_type="presence",
        expected_within_s=1.0,
        fired_at_ts=fired_at_ts,
        snapshot_at_fire=_snapshot(),
        match_data={"transition": "arrive"},
    )


def _tracker_with_streak(streak: int) -> OutcomeTracker:
    tracker = OutcomeTracker(now_provider=lambda: 10.0)
    for index in range(streak):
        tracker.register_pending(_pending("reaction.unreliable", fired_at_ts=float(index)))
        tracker.check_pending([])
    return tracker


def _tracker_with_positive_streak(streak: int) -> OutcomeTracker:
    tracker = OutcomeTracker(now_provider=lambda: 10.0)
    for index in range(streak):
        tracker.register_pending(_pending("reaction.unreliable", fired_at_ts=float(index)))
        tracker.check_pending([{"event_type": "presence", "data": {"transition": "arrive"}}])
    return tracker


def _proposal(status: str) -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="outcome_tracker",
        reaction_type="DegradingReaction",
        description="Existing",
        confidence=1.0,
        status=status,  # type: ignore[arg-type]
        identity_key="degradation:reaction.unreliable",
    )


async def _run_e4(
    *,
    tracker: OutcomeTracker,
    proposal_engine: FakeProposalEngine,
) -> list[ReactionProposal]:
    engine = _make_engine()
    engine.set_outcome_tracker(tracker)
    engine.set_proposal_engine(proposal_engine)  # type: ignore[arg-type]

    await engine._maybe_submit_degradation_proposals()

    return proposal_engine.submitted


async def test_degradation_proposal_submitted_after_threshold() -> None:
    submitted = await _run_e4(
        tracker=_tracker_with_streak(OutcomeTracker.DEGRADATION_THRESHOLD),
        proposal_engine=FakeProposalEngine(),
    )

    assert len(submitted) == 1
    proposal = submitted[0]
    assert proposal.followup_kind == "tuning_suggestion"
    assert proposal.suggested_reaction_config["enabled"] is False
    assert proposal.identity_key == "degradation:reaction.unreliable"
    assert proposal.target_reaction_id == "reaction.unreliable"
    assert proposal.target_reaction_type == "DegradingReaction"


async def test_degradation_proposal_not_resubmitted_if_accepted() -> None:
    submitted = await _run_e4(
        tracker=_tracker_with_streak(OutcomeTracker.DEGRADATION_THRESHOLD),
        proposal_engine=FakeProposalEngine(existing=_proposal("accepted")),
    )

    assert submitted == []


async def test_degradation_proposal_not_resubmitted_if_rejected() -> None:
    submitted = await _run_e4(
        tracker=_tracker_with_streak(OutcomeTracker.DEGRADATION_THRESHOLD),
        proposal_engine=FakeProposalEngine(existing=_proposal("rejected")),
    )

    assert submitted == []


async def test_degradation_proposal_refreshed_if_pending() -> None:
    submitted = await _run_e4(
        tracker=_tracker_with_streak(OutcomeTracker.DEGRADATION_THRESHOLD),
        proposal_engine=FakeProposalEngine(existing=_proposal("pending")),
    )

    assert len(submitted) == 1
    assert submitted[0].identity_key == "degradation:reaction.unreliable"


async def test_degradation_confidence_at_threshold() -> None:
    submitted = await _run_e4(
        tracker=_tracker_with_streak(OutcomeTracker.DEGRADATION_THRESHOLD),
        proposal_engine=FakeProposalEngine(),
    )

    assert submitted[0].confidence == 1.0


async def test_no_proposal_below_threshold() -> None:
    submitted = await _run_e4(
        tracker=_tracker_with_streak(OutcomeTracker.DEGRADATION_THRESHOLD - 1),
        proposal_engine=FakeProposalEngine(),
    )

    assert submitted == []


async def test_positive_streak_boosts_confidence_and_resets_streak() -> None:
    tracker = _tracker_with_positive_streak(OutcomeTracker.POSITIVE_BOOST_THRESHOLD)
    proposal_engine = FakeProposalEngine()
    engine = _make_engine()
    engine.set_outcome_tracker(tracker)
    engine.set_proposal_engine(proposal_engine)  # type: ignore[arg-type]

    await engine._maybe_boost_reaction_confidence()

    assert proposal_engine.boosted == [
        ("reaction.unreliable", OutcomeTracker.POSITIVE_CONFIDENCE_BOOST)
    ]
    assert tracker.positive_streak("reaction.unreliable") == 0


async def test_positive_streak_below_threshold_does_not_boost() -> None:
    tracker = _tracker_with_positive_streak(OutcomeTracker.POSITIVE_BOOST_THRESHOLD - 1)
    proposal_engine = FakeProposalEngine()
    engine = _make_engine()
    engine.set_outcome_tracker(tracker)
    engine.set_proposal_engine(proposal_engine)  # type: ignore[arg-type]

    await engine._maybe_boost_reaction_confidence()

    assert proposal_engine.boosted == []
