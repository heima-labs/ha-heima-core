"""Learning backend protocol and built-in implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..contracts import ApplyStep


class ILearningBackend(Protocol):
    """Plugin for adaptive confidence tracking per reaction.

    The backend receives feedback signals from the reaction and adjusts
    a per-reaction confidence value (0.0–1.0). Reactions use this value
    to decide whether to fire or stay silent.

    Confidence starts at 1.0. It decays when overrides are recorded and
    recovers automatically after enough override-free cycles.
    """

    def observe(self, reaction_id: str, fired: bool, steps: list[ApplyStep]) -> None:
        """Called after each evaluation cycle.

        Args:
            reaction_id: Stable identifier of the reaction.
            fired: Whether the reaction produced steps in this cycle.
            steps: The steps produced (empty list when fired=False).
        """
        ...

    def record_override(self, reaction_id: str) -> None:
        """Signal that the user overrode the reaction's last output.

        Override detection is the caller's responsibility (e.g., the engine
        comparing last reaction steps with subsequent HA state). Repeated
        overrides decay the reaction's confidence.
        """
        ...

    def confidence(self, reaction_id: str) -> float:
        """Return the current confidence for this reaction (0.0–1.0)."""
        ...

    def diagnostics(self, reaction_id: str) -> dict[str, Any]:
        """Return diagnostic data for this reaction."""
        ...


@dataclass
class _ReactionLearningState:
    confidence: float = 1.0
    consecutive_overrides: int = 0
    cycles_since_last_override: int = 0


class NaiveLearningBackend:
    """Counter-based confidence backend.

    Logic:
    - Confidence starts at 1.0.
    - Each call to `record_override` increments `consecutive_overrides`.
      When `consecutive_overrides >= override_threshold`, confidence is
      reduced by `1 / override_threshold` (floored at 0.0) and the counter
      resets. Minimum confidence is 0.0.
    - Each cycle where the reaction fires (observe called with fired=True)
      increments `cycles_since_last_override`. Once this reaches
      `reset_cycles`, confidence is fully restored to 1.0 and the override
      counter resets.
    - Pluggable: swap this backend with a statistical or ML backend without
      touching any reaction code.

    Args:
        override_threshold: Number of consecutive overrides before confidence
                            is penalised. Default: 3.
        reset_cycles: Number of override-free firing cycles before confidence
                      is fully restored. Default: 20.
    """

    def __init__(
        self,
        *,
        override_threshold: int = 3,
        reset_cycles: int = 20,
    ) -> None:
        if override_threshold < 1:
            raise ValueError(f"override_threshold must be >= 1, got {override_threshold}")
        if reset_cycles < 1:
            raise ValueError(f"reset_cycles must be >= 1, got {reset_cycles}")
        self._override_threshold = override_threshold
        self._reset_cycles = reset_cycles
        self._state: dict[str, _ReactionLearningState] = {}

    def _get(self, reaction_id: str) -> _ReactionLearningState:
        if reaction_id not in self._state:
            self._state[reaction_id] = _ReactionLearningState()
        return self._state[reaction_id]

    def observe(self, reaction_id: str, fired: bool, steps: list[ApplyStep]) -> None:
        if not fired:
            return
        s = self._get(reaction_id)
        s.cycles_since_last_override += 1
        if s.cycles_since_last_override >= self._reset_cycles:
            s.confidence = 1.0
            s.consecutive_overrides = 0

    def record_override(self, reaction_id: str) -> None:
        s = self._get(reaction_id)
        s.consecutive_overrides += 1
        s.cycles_since_last_override = 0
        if s.consecutive_overrides >= self._override_threshold:
            penalty = 1.0 / self._override_threshold
            s.confidence = max(0.0, s.confidence - penalty)
            s.consecutive_overrides = 0

    def confidence(self, reaction_id: str) -> float:
        return self._get(reaction_id).confidence

    def diagnostics(self, reaction_id: str) -> dict[str, Any]:
        s = self._get(reaction_id)
        return {
            "confidence": s.confidence,
            "consecutive_overrides": s.consecutive_overrides,
            "cycles_since_last_override": s.cycles_since_last_override,
            "override_threshold": self._override_threshold,
            "reset_cycles": self._reset_cycles,
        }
