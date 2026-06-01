from __future__ import annotations

from custom_components.heima.config_flow._reaction_helpers import (
    house_state_proposal_review_details,
)
from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.inference.approval_store import HOUSE_STATE_PROPOSAL_TYPE


def _house_state_proposal() -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="house_state_inference",
        reaction_type=HOUSE_STATE_PROPOSAL_TYPE,
        description="Learned house-state context predicts 'working'.",
        confidence=1.0,
        suggested_reaction_config={},
    )


def test_house_state_proposal_review_details_renders_italian_weekday_name() -> None:
    details = house_state_proposal_review_details(
        _house_state_proposal(),
        {
            "context_snapshot": {
                "weekday": 5,
                "hour_bucket": 8,
                "rooms": ["bagno_piccolo"],
                "anyone_home": True,
                "predicted_state": "working",
            },
            "support": 3,
            "total": 3,
        },
        is_it=True,
    )

    assert "Giorno: sabato" in details
    assert "Giorno: 5" not in details
    assert "Ora: 08:00" in details


def test_house_state_proposal_review_details_renders_english_weekday_name() -> None:
    details = house_state_proposal_review_details(
        _house_state_proposal(),
        {
            "context_snapshot": {
                "weekday": 5,
                "hour_bucket": 8,
                "rooms": ["small_bathroom"],
                "anyone_home": True,
                "predicted_state": "working",
            },
            "support": 3,
            "total": 3,
        },
        is_it=False,
    )

    assert "Weekday: Saturday" in details
    assert "Weekday: 5" not in details
    assert "Hour: 08:00" in details
