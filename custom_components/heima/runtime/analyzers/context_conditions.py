"""Contracts and scoring helpers for context-conditioned learning."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Any, Literal

DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION = 0.65
DEFAULT_CONTEXT_CONDITION_MIN_LIFT = 2.0
DEFAULT_CONTEXT_CONDITION_MIN_NEGATIVE_EPISODES = 3

ContrastStatus = Literal["verified", "unverified"]


@dataclass(frozen=True)
class ContextCondition:
    """Abstract, bounded context condition used by learned reactions."""

    signal_name: str
    state_in: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "state_in": list(self.state_in),
        }


@dataclass(frozen=True)
class ContextConditionScore:
    """Scoring result for one candidate context condition."""

    signal_name: str
    state_in: tuple[str, ...]
    concentration: float
    lift: float | None
    negative_episode_count: int
    contrast_status: ContrastStatus
    eligible: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "state_in": list(self.state_in),
            "concentration": self.concentration,
            "lift": self.lift,
            "negative_episode_count": self.negative_episode_count,
            "contrast_status": self.contrast_status,
            "eligible": self.eligible,
        }


def normalize_context_condition(raw: dict[str, Any]) -> ContextCondition | None:
    """Return a normalized abstract context condition or None if invalid."""
    if not isinstance(raw, dict):
        return None
    signal_name = str(raw.get("signal_name") or "").strip().lower()
    if not signal_name or "." in signal_name:
        return None
    state_in = tuple(
        dict.fromkeys(
            str(item).strip().lower()
            for item in list(raw.get("state_in") or [])
            if str(item).strip()
        )
    )
    if not state_in:
        return None
    return ContextCondition(signal_name=signal_name, state_in=state_in)


def normalize_context_conditions(raw_list: Any) -> list[ContextCondition]:
    """Return normalized context conditions, dropping invalid items."""
    if not isinstance(raw_list, list):
        return []
    normalized: list[ContextCondition] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for raw in raw_list:
        item = normalize_context_condition(raw)
        if item is None:
            continue
        key = (item.signal_name, item.state_in)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def score_context_condition(
    *,
    condition: ContextCondition,
    positive_episode_count: int,
    positive_match_count: int,
    negative_episode_count: int,
    negative_match_count: int,
    min_concentration: float = DEFAULT_CONTEXT_CONDITION_MIN_CONCENTRATION,
    min_lift: float = DEFAULT_CONTEXT_CONDITION_MIN_LIFT,
    min_negative_episodes: int = DEFAULT_CONTEXT_CONDITION_MIN_NEGATIVE_EPISODES,
) -> ContextConditionScore:
    """Score one abstract context condition against positive and negative episodes."""
    if positive_episode_count <= 0:
        raise ValueError("positive_episode_count must be > 0")
    if positive_match_count < 0 or positive_match_count > positive_episode_count:
        raise ValueError("positive_match_count out of range")
    if negative_episode_count < 0:
        raise ValueError("negative_episode_count must be >= 0")
    if negative_match_count < 0 or negative_match_count > negative_episode_count:
        raise ValueError("negative_match_count out of range")

    concentration = positive_match_count / positive_episode_count
    contrast_status: ContrastStatus

    if negative_episode_count < min_negative_episodes:
        contrast_status = "unverified"
        return ContextConditionScore(
            signal_name=condition.signal_name,
            state_in=condition.state_in,
            concentration=concentration,
            lift=None,
            negative_episode_count=negative_episode_count,
            contrast_status=contrast_status,
            eligible=concentration >= min_concentration,
        )

    contrast_status = "verified"
    active_total = positive_match_count + negative_match_count
    inactive_positive_count = positive_episode_count - positive_match_count
    inactive_negative_count = negative_episode_count - negative_match_count
    inactive_total = inactive_positive_count + inactive_negative_count

    scene_when_active = positive_match_count / active_total if active_total > 0 else 0.0
    if inactive_total == 0:
        lift: float | None = None
    else:
        scene_when_inactive = inactive_positive_count / inactive_total
        if scene_when_inactive == 0.0:
            lift = inf if scene_when_active > 0.0 else 0.0
        else:
            lift = scene_when_active / scene_when_inactive

    return ContextConditionScore(
        signal_name=condition.signal_name,
        state_in=condition.state_in,
        concentration=concentration,
        lift=lift,
        negative_episode_count=negative_episode_count,
        contrast_status=contrast_status,
        eligible=(concentration >= min_concentration and lift is not None and lift >= min_lift),
    )
