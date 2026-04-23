"""Promotion helpers for context-conditioned lighting learning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .context_conditions import (
    DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION,
    DEFAULT_CONTEXT_CONDITION_MIN_LIFT,
    DEFAULT_CONTEXT_CONDITION_MIN_NEGATIVE_EPISODES,
    ContextCondition,
    ContextConditionScore,
    score_context_condition,
)
from .context_episode_sampling import LightingContextDataset


@dataclass(frozen=True)
class ContextConditionPromotionDecision:
    """Phase-3 promotion decision for one lighting candidate."""

    selected_condition: ContextCondition | None
    selected_score: ContextConditionScore | None
    considered_scores: tuple[ContextConditionScore, ...]
    total_negative_episode_count: int

    @property
    def should_promote(self) -> bool:
        return self.selected_score is not None and self.selected_score.eligible

    def diagnostics(self) -> dict[str, Any]:
        return {
            "context_conditions_considered": [score.as_dict() for score in self.considered_scores],
            "selected_context_condition": (
                self.selected_condition.as_dict() if self.selected_condition is not None else None
            ),
            "concentration": (
                self.selected_score.concentration if self.selected_score is not None else None
            ),
            "lift": self.selected_score.lift if self.selected_score is not None else None,
            "negative_episode_count": (
                self.selected_score.negative_episode_count
                if self.selected_score is not None
                else self.total_negative_episode_count
            ),
            "contrast_status": (
                self.selected_score.contrast_status if self.selected_score is not None else None
            ),
        }


def evaluate_context_condition_promotion(
    dataset: LightingContextDataset,
    *,
    min_concentration: float = DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION,
    min_lift: float = DEFAULT_CONTEXT_CONDITION_MIN_LIFT,
    min_negative_episodes: int = DEFAULT_CONTEXT_CONDITION_MIN_NEGATIVE_EPISODES,
) -> ContextConditionPromotionDecision:
    """Return the best eligible context condition, if any."""

    conditions = _candidate_conditions_from_dataset(dataset)
    if not conditions:
        return ContextConditionPromotionDecision(
            selected_condition=None,
            selected_score=None,
            considered_scores=(),
            total_negative_episode_count=len(dataset.negative_episodes),
        )

    scores: list[ContextConditionScore] = []
    positive_count = len(dataset.positive_episodes)
    negative_count = len(dataset.negative_episodes)
    for condition in conditions:
        positive_match_count = sum(
            1
            for episode in dataset.positive_episodes
            if episode.context_signals.get(condition.signal_name) in condition.state_in
        )
        negative_match_count = sum(
            1
            for episode in dataset.negative_episodes
            if episode.context_signals.get(condition.signal_name) in condition.state_in
        )
        scores.append(
            score_context_condition(
                condition=condition,
                positive_episode_count=positive_count,
                positive_match_count=positive_match_count,
                negative_episode_count=negative_count,
                negative_match_count=negative_match_count,
                min_concentration=min_concentration,
                min_lift=min_lift,
                min_negative_episodes=min_negative_episodes,
            )
        )

    ordered = sorted(scores, key=_score_order_key, reverse=True)
    selected_score = next((score for score in ordered if score.eligible), None)
    selected_condition = (
        ContextCondition(
            signal_name=selected_score.signal_name,
            state_in=selected_score.state_in,
        )
        if selected_score is not None
        else None
    )
    return ContextConditionPromotionDecision(
        selected_condition=selected_condition,
        selected_score=selected_score,
        considered_scores=tuple(ordered),
        total_negative_episode_count=negative_count,
    )


def _candidate_conditions_from_dataset(dataset: LightingContextDataset) -> list[ContextCondition]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    conditions: list[ContextCondition] = []
    for episode in dataset.positive_episodes:
        for signal_name, state in sorted(episode.context_signals.items()):
            if not signal_name or not state:
                continue
            key = (signal_name, (state,))
            if key in seen:
                continue
            seen.add(key)
            conditions.append(ContextCondition(signal_name=signal_name, state_in=(state,)))
    return conditions


def _score_order_key(score: ContextConditionScore) -> tuple[Any, ...]:
    lift = float("-inf") if score.lift is None else float(score.lift)
    return (
        1 if score.eligible else 0,
        1 if score.contrast_status == "verified" else 0,
        score.concentration,
        lift,
        score.signal_name,
        score.state_in,
    )
