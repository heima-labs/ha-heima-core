"""Invariant check debounce state."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .plugin_contracts import InvariantViolation


@dataclass
class InvariantCheckState:
    """Per-check debounce and resolution state."""

    first_seen_ts: float | None = None
    last_emitted_ts: float | None = None
    is_active: bool = False


@dataclass(frozen=True)
class InvariantCheckOutcome:
    """Invariant check state transition output."""

    violation: InvariantViolation | None = None
    resolved: bool = False


def evaluate_invariant_state(
    *,
    state: InvariantCheckState,
    violation: InvariantViolation | None,
    debounce_s: float,
    re_emit_interval_s: float,
    now: float | None = None,
) -> InvariantCheckOutcome:
    """Apply debounce/re-emit/resolution semantics for one invariant check."""
    now_ts = time.monotonic() if now is None else float(now)
    if violation is None:
        was_active = state.is_active
        state.first_seen_ts = None
        state.last_emitted_ts = None
        state.is_active = False
        return InvariantCheckOutcome(resolved=was_active)

    if state.first_seen_ts is None:
        state.first_seen_ts = now_ts
    elapsed = now_ts - state.first_seen_ts
    if elapsed < debounce_s:
        return InvariantCheckOutcome()

    should_emit = state.last_emitted_ts is None or (
        now_ts - state.last_emitted_ts >= re_emit_interval_s
    )
    state.is_active = True
    if not should_emit:
        return InvariantCheckOutcome()

    state.last_emitted_ts = now_ts
    return InvariantCheckOutcome(violation=violation)
