"""Built-in HeimaReaction implementations."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction
from .patterns import ConsecutiveMatchDetector

if TYPE_CHECKING:
    from .learning import ILearningBackend

_DEFAULT_CONFIDENCE_THRESHOLD = 0.5


class ConsecutiveStateReaction(HeimaReaction):
    """Fires when a condition holds for N consecutive evaluation snapshots.

    This is a **level-triggered** reaction: it contributes its steps on every
    evaluation cycle where the last `consecutive_n` snapshots all match the
    predicate. When the condition is no longer met, it stops contributing.

    If a `learning_backend` is provided, the reaction checks its confidence
    before firing. If confidence < `confidence_threshold` (default 0.5), the
    reaction is silenced for that cycle (suppressed). The backend is also
    notified after each evaluate via `observe()`.

    Override detection is the caller's responsibility: call
    `learning_backend.record_override(reaction_id)` when external evidence
    shows the user negated the reaction's output (e.g., the engine detects a
    heating setpoint reversal in the next snapshot).

    Args:
        predicate: Callable receiving a DecisionSnapshot, returns True if the
                   condition holds for that snapshot.
        consecutive_n: Number of consecutive matching snapshots required to
                       activate. Must be >= 1.
        steps: ApplyStep instances to inject when the pattern is active.
               Each step's `source` field is overwritten by the engine dispatcher.
        reaction_id: Optional stable identifier. Defaults to class name.
        learning_backend: Optional ILearningBackend for confidence-based
                          suppression. If None, the reaction always fires when
                          the pattern matches.
        confidence_threshold: Minimum confidence required to fire (default 0.5).
    """

    def __init__(
        self,
        *,
        predicate: Callable[[DecisionSnapshot], bool],
        consecutive_n: int,
        steps: list[ApplyStep],
        reaction_id: str | None = None,
        learning_backend: "ILearningBackend | None" = None,
        confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._detector = ConsecutiveMatchDetector(predicate, consecutive_n)
        self._steps = list(steps)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._backend = learning_backend
        self._confidence_threshold = confidence_threshold
        self._last_matched: bool = False
        self._suppressed_count: int = 0
        self._last_fired_ts: float | None = None
        self._fire_count: int = 0

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        # Check confidence before evaluating the pattern
        if self._backend is not None:
            conf = self._backend.confidence(self._reaction_id)
            if conf < self._confidence_threshold:
                self._suppressed_count += 1
                self._last_matched = False
                self._backend.observe(self._reaction_id, fired=False, steps=[])
                return []

        matched = self._detector.matches(history)
        self._last_matched = matched
        steps = list(self._steps) if matched else []

        if self._backend is not None:
            self._backend.observe(self._reaction_id, fired=matched, steps=steps)

        if matched:
            self._last_fired_ts = time.monotonic()
            self._fire_count += 1

        return steps

    def diagnostics(self) -> dict[str, Any]:
        diag: dict[str, Any] = {
            "consecutive_n": self._detector.consecutive_n,
            "last_matched": self._last_matched,
            "last_fired_ts": self._last_fired_ts,
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "steps_count": len(self._steps),
        }
        if self._backend is not None:
            diag["learning"] = self._backend.diagnostics(self._reaction_id)
        return diag
