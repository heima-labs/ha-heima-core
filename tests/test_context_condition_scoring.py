from __future__ import annotations

from math import isinf

import pytest

from custom_components.heima.runtime.analyzers.context_conditions import (
    DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION,
    DEFAULT_CONTEXT_CONDITION_MIN_LIFT,
    DEFAULT_CONTEXT_CONDITION_MIN_NEGATIVE_EPISODES,
    ContextCondition,
    normalize_context_condition,
    normalize_context_conditions,
    score_context_condition,
)


def test_normalize_context_condition_rejects_raw_entity_id_signal_name():
    assert (
        normalize_context_condition(
            {"signal_name": "media_player.projector", "state_in": ["active"]}
        )
        is None
    )


def test_normalize_context_conditions_dedupes_and_normalizes():
    items = normalize_context_conditions(
        [
            {"signal_name": "Projector_Context", "state_in": ["Active", "active"]},
            {"signal_name": "projector_context", "state_in": ["active"]},
            {"signal_name": " ", "state_in": ["active"]},
        ]
    )

    assert items == [ContextCondition(signal_name="projector_context", state_in=("active",))]


def test_score_context_condition_computes_concentration_and_lift():
    result = score_context_condition(
        condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
        positive_episode_count=10,
        positive_match_count=8,
        negative_episode_count=10,
        negative_match_count=2,
    )

    assert result.concentration == 0.8
    assert result.lift == 4.0
    assert result.negative_episode_count == 10
    assert result.contrast_status == "verified"
    assert result.eligible is True


def test_score_context_condition_marks_unverified_when_negatives_are_insufficient():
    result = score_context_condition(
        condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
        positive_episode_count=10,
        positive_match_count=7,
        negative_episode_count=2,
        negative_match_count=0,
    )

    assert result.concentration == 0.7
    assert result.lift is None
    assert result.negative_episode_count == 2
    assert result.contrast_status == "unverified"
    assert result.eligible is True


def test_score_context_condition_rejects_when_concentration_is_too_low():
    result = score_context_condition(
        condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
        positive_episode_count=10,
        positive_match_count=6,
        negative_episode_count=10,
        negative_match_count=1,
    )

    assert result.concentration < DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION
    assert result.contrast_status == "verified"
    assert result.eligible is False


def test_score_context_condition_rejects_when_lift_is_too_low():
    result = score_context_condition(
        condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
        positive_episode_count=10,
        positive_match_count=8,
        negative_episode_count=10,
        negative_match_count=7,
    )

    assert result.concentration >= DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION
    assert result.lift is not None
    assert result.lift < DEFAULT_CONTEXT_CONDITION_MIN_LIFT
    assert result.contrast_status == "verified"
    assert result.eligible is False


def test_score_context_condition_uses_infinite_lift_when_inactive_baseline_is_zero():
    result = score_context_condition(
        condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
        positive_episode_count=10,
        positive_match_count=10,
        negative_episode_count=10,
        negative_match_count=0,
    )

    assert result.contrast_status == "verified"
    assert result.lift is not None
    assert isinf(result.lift)
    assert result.eligible is True


def test_score_context_condition_validates_input_ranges():
    with pytest.raises(ValueError):
        score_context_condition(
            condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
            positive_episode_count=0,
            positive_match_count=0,
            negative_episode_count=0,
            negative_match_count=0,
        )

    with pytest.raises(ValueError):
        score_context_condition(
            condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
            positive_episode_count=5,
            positive_match_count=6,
            negative_episode_count=0,
            negative_match_count=0,
        )

    with pytest.raises(ValueError):
        score_context_condition(
            condition=ContextCondition(signal_name="projector_context", state_in=("active",)),
            positive_episode_count=5,
            positive_match_count=4,
            negative_episode_count=3,
            negative_match_count=4,
        )


def test_phase1_default_thresholds_match_rfc():
    assert DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION == 0.65
    assert DEFAULT_CONTEXT_CONDITION_MIN_LIFT == 2.0
    assert DEFAULT_CONTEXT_CONDITION_MIN_NEGATIVE_EPISODES == 3
