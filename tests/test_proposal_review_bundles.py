from __future__ import annotations

from typing import Any

from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.inference.approval_store import HOUSE_STATE_PROPOSAL_TYPE
from custom_components.heima.runtime.proposal_review_bundles import (
    build_temporal_review_bundles,
)


def test_temporal_review_bundles_group_adjacent_visible_house_state_proposals() -> None:
    first = _house_state_proposal("p-8", hour_bucket=8, confidence=0.75, support=4)
    second = _house_state_proposal("p-9", hour_bucket=9, confidence=0.85, support=6)

    view = build_temporal_review_bundles([first, second])

    assert view.bundled_proposal_ids == ("p-8", "p-9")
    assert view.unbundled_proposal_ids == ()
    assert len(view.bundles) == 1
    bundle = view.bundles[0]
    assert bundle.bundle_type == "house_state_temporal"
    assert bundle.weekday == 1
    assert bundle.start_hour_bucket == 8
    assert bundle.end_hour_bucket == 9
    assert bundle.anyone_home is True
    assert bundle.predicted_state == "working"
    assert bundle.proposal_ids == ("p-8", "p-9")
    assert bundle.identity_keys == (
        f"{HOUSE_STATE_PROPOSAL_TYPE}:ctx-p-8",
        f"{HOUSE_STATE_PROPOSAL_TYPE}:ctx-p-9",
    )
    assert bundle.member_count == 2
    assert bundle.confidence_min == 0.75
    assert bundle.confidence_max == 0.85
    assert bundle.confidence_avg == 0.8
    assert bundle.support_total == 10
    assert bundle.total_observations == 10


def test_temporal_review_bundles_split_on_hour_gaps_and_leave_singletons_unbundled() -> None:
    proposals = [
        _house_state_proposal("p-8", hour_bucket=8),
        _house_state_proposal("p-9", hour_bucket=9),
        _house_state_proposal("p-11", hour_bucket=11),
    ]

    view = build_temporal_review_bundles(proposals)

    assert len(view.bundles) == 1
    assert view.bundles[0].proposal_ids == ("p-8", "p-9")
    assert view.unbundled_proposal_ids == ("p-11",)


def test_temporal_review_bundles_separate_context_dimensions() -> None:
    proposals = [
        _house_state_proposal("p-work-8", hour_bucket=8, predicted_state="working"),
        _house_state_proposal("p-work-9", hour_bucket=9, predicted_state="working"),
        _house_state_proposal("p-home-8", hour_bucket=8, predicted_state="home"),
        _house_state_proposal("p-home-9", hour_bucket=9, predicted_state="home"),
        _house_state_proposal("p-away-8", hour_bucket=8, anyone_home=False),
        _house_state_proposal("p-away-9", hour_bucket=9, anyone_home=False),
        _house_state_proposal("p-tue-8", weekday=2, hour_bucket=8),
        _house_state_proposal("p-tue-9", weekday=2, hour_bucket=9),
    ]

    view = build_temporal_review_bundles(proposals)

    assert {bundle.proposal_ids for bundle in view.bundles} == {
        ("p-work-8", "p-work-9"),
        ("p-away-8", "p-away-9"),
        ("p-home-8", "p-home-9"),
        ("p-tue-8", "p-tue-9"),
    }


def test_temporal_review_bundles_ignore_non_house_state_proposals() -> None:
    house_state = _house_state_proposal("p-8", hour_bucket=8)
    lighting = ReactionProposal(
        proposal_id="lighting",
        reaction_type="room_smart_lighting_assist",
        confidence=0.9,
        suggested_reaction_config={"weekday": 1, "hour_bucket": 9},
    )

    view = build_temporal_review_bundles([house_state, lighting])

    assert view.bundles == ()
    assert view.bundled_proposal_ids == ()
    assert view.unbundled_proposal_ids == ("p-8", "lighting")


def test_temporal_review_bundles_support_top_level_context_fallbacks() -> None:
    first = _house_state_proposal(
        "p-8",
        context_snapshot={},
        suggested_overrides={
            "weekday": "1",
            "hour_bucket": "8",
            "anyone_home": "on",
            "house_state": "Working",
        },
    )
    second = _house_state_proposal(
        "p-9",
        context_snapshot={},
        suggested_overrides={
            "weekday": 1,
            "hour_bucket": 9,
            "anyone_home": True,
            "predicted_state": "working",
        },
    )

    view = build_temporal_review_bundles(item for item in [first, second])

    assert len(view.bundles) == 1
    assert view.bundles[0].proposal_ids == ("p-8", "p-9")
    assert view.bundles[0].predicted_state == "working"


def _house_state_proposal(
    proposal_id: str,
    *,
    weekday: int = 1,
    hour_bucket: int = 8,
    anyone_home: bool = True,
    predicted_state: str = "working",
    confidence: float = 0.8,
    support: int = 3,
    total: int | None = None,
    context_snapshot: dict[str, Any] | None = None,
    suggested_overrides: dict[str, Any] | None = None,
) -> ReactionProposal:
    snapshot = (
        dict(context_snapshot)
        if context_snapshot is not None
        else {
            "weekday": weekday,
            "hour_bucket": hour_bucket,
            "anyone_home": anyone_home,
            "predicted_state": predicted_state,
        }
    )
    cfg: dict[str, Any] = {
        "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
        "context_key": f"ctx-{proposal_id}",
        "context_snapshot": snapshot,
        "predicted_state": predicted_state,
        "support": support,
        "total": support if total is None else total,
    }
    cfg.update(suggested_overrides or {})
    return ReactionProposal(
        proposal_id=proposal_id,
        analyzer_id="house_state_inference",
        reaction_type=HOUSE_STATE_PROPOSAL_TYPE,
        description="Learned house-state context",
        confidence=confidence,
        identity_key=f"{HOUSE_STATE_PROPOSAL_TYPE}:ctx-{proposal_id}",
        suggested_reaction_config=cfg,
    )
