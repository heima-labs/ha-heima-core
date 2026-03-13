"""Bounded ring buffer of DecisionSnapshot objects for the reactive engine."""

from __future__ import annotations

from collections import deque

from .snapshot import DecisionSnapshot

_DEFAULT_CAPACITY = 20


class SnapshotBuffer:
    """Bounded ring buffer that keeps the N most recent DecisionSnapshot objects.

    The buffer is maintained by the engine after each evaluation cycle and
    exposed to HeimaReaction instances as their observation window.

    Ordering: oldest first, newest last (index -1 is the most recent).
    """

    def __init__(self, capacity: int = _DEFAULT_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError(f"SnapshotBuffer capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._buf: deque[DecisionSnapshot] = deque(maxlen=capacity)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def capacity(self) -> int:
        return self._capacity

    def push(self, snapshot: DecisionSnapshot) -> None:
        """Append a snapshot; oldest entry is evicted when capacity is reached."""
        self._buf.append(snapshot)

    def history(self) -> list[DecisionSnapshot]:
        """Return a list of snapshots in chronological order (oldest first)."""
        return list(self._buf)

    def latest(self) -> DecisionSnapshot | None:
        """Return the most recently pushed snapshot, or None if empty."""
        return self._buf[-1] if self._buf else None

    def __len__(self) -> int:
        return len(self._buf)

    def clear(self) -> None:
        self._buf.clear()
