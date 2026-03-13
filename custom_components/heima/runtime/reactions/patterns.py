"""Pattern detector protocol and built-in detectors."""

from __future__ import annotations

from typing import Callable, Protocol

from ..snapshot import DecisionSnapshot


class IPatternDetector(Protocol):
    """Stateless plugin that evaluates a condition over a snapshot history window.

    Implementations must be pure: same history → same result, no side effects.
    """

    def matches(self, history: list[DecisionSnapshot]) -> bool:
        """Return True if the pattern is active for this history window."""
        ...


class ConsecutiveMatchDetector:
    """Fires when the last N snapshots all satisfy a predicate.

    Args:
        predicate: A function that receives a single DecisionSnapshot and
                   returns True if the condition holds for that snapshot.
        consecutive_n: Number of consecutive matching snapshots required.
                       Must be >= 1.
    """

    def __init__(
        self,
        predicate: Callable[[DecisionSnapshot], bool],
        consecutive_n: int,
    ) -> None:
        if consecutive_n < 1:
            raise ValueError(f"consecutive_n must be >= 1, got {consecutive_n}")
        self._predicate = predicate
        self._consecutive_n = consecutive_n

    @property
    def consecutive_n(self) -> int:
        return self._consecutive_n

    def matches(self, history: list[DecisionSnapshot]) -> bool:
        """Return True if the last `consecutive_n` snapshots all match the predicate."""
        if len(history) < self._consecutive_n:
            return False
        window = history[-self._consecutive_n:]
        return all(self._predicate(s) for s in window)
