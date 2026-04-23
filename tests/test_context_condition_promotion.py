from __future__ import annotations

from custom_components.heima.runtime.analyzers.context_condition_promotion import (
    evaluate_context_condition_promotion,
)
from custom_components.heima.runtime.analyzers.context_episode_sampling import (
    LightingContextDataset,
    LightingEpisodeSample,
)


def _episode(
    *,
    ts: str,
    minute: int = 1200,
    context_signals: dict[str, str],
    matches_target_scene: bool,
) -> LightingEpisodeSample:
    return LightingEpisodeSample(
        ts=ts,
        room_id="studio",
        weekday=1,
        minute_of_day=minute,
        scene_signature=(("light.studio_spot", "on", 80, None, None),),
        context_signals=context_signals,
        matches_target_scene=matches_target_scene,
    )


def test_evaluate_context_condition_promotion_selects_strong_verified_candidate():
    dataset = LightingContextDataset(
        positive_episodes=(
            _episode(
                ts="2026-04-07T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-14T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-21T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-28T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=True,
            ),
        ),
        negative_episodes=(
            _episode(
                ts="2026-04-08T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-15T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-22T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-29T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=False,
            ),
        ),
    )

    decision = evaluate_context_condition_promotion(dataset)

    assert decision.should_promote is True
    assert decision.selected_condition is not None
    assert decision.selected_condition.signal_name == "projector_context"
    assert decision.selected_condition.state_in == ("active",)
    assert decision.selected_score is not None
    assert decision.selected_score.contrast_status == "verified"
    assert decision.selected_score.eligible is True


def test_evaluate_context_condition_promotion_allows_unverified_when_negatives_are_insufficient():
    dataset = LightingContextDataset(
        positive_episodes=(
            _episode(
                ts="2026-04-07T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-14T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-21T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
        ),
        negative_episodes=(
            _episode(
                ts="2026-04-08T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-15T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
        ),
    )

    decision = evaluate_context_condition_promotion(dataset)

    assert decision.should_promote is True
    assert decision.selected_score is not None
    assert decision.selected_score.contrast_status == "unverified"
    assert decision.selected_score.lift is None


def test_evaluate_context_condition_promotion_rejects_weak_concentration():
    dataset = LightingContextDataset(
        positive_episodes=(
            _episode(
                ts="2026-04-07T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-14T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-21T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=True,
            ),
        ),
        negative_episodes=(
            _episode(
                ts="2026-04-08T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-15T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-22T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
        ),
    )

    decision = evaluate_context_condition_promotion(dataset)

    assert decision.should_promote is False
    assert decision.selected_condition is None


def test_evaluate_context_condition_promotion_rejects_weak_lift():
    dataset = LightingContextDataset(
        positive_episodes=(
            _episode(
                ts="2026-04-07T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-14T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-21T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-28T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=True,
            ),
        ),
        negative_episodes=(
            _episode(
                ts="2026-04-08T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-15T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-22T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
        ),
    )

    decision = evaluate_context_condition_promotion(dataset)

    assert decision.should_promote is False
    assert decision.selected_condition is None


def test_context_condition_promotion_diagnostics_keep_true_negative_episode_count_without_selection():
    dataset = LightingContextDataset(
        positive_episodes=(
            _episode(
                ts="2026-04-07T18:00:00+00:00",
                context_signals={"projector_context": "active"},
                matches_target_scene=True,
            ),
            _episode(
                ts="2026-04-14T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=True,
            ),
        ),
        negative_episodes=(
            _episode(
                ts="2026-04-08T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-15T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
            _episode(
                ts="2026-04-22T18:00:00+00:00",
                context_signals={"projector_context": "inactive"},
                matches_target_scene=False,
            ),
        ),
    )

    decision = evaluate_context_condition_promotion(dataset)

    assert decision.should_promote is False
    diagnostics = decision.diagnostics()
    assert diagnostics["negative_episode_count"] == 3
