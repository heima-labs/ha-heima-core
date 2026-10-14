"""Asyncio countdowns preserving minimum monotonic deadlines, even on early wakeup."""

from collections.abc import Callable
from math import inf, isfinite, nextafter
from time import get_clock_info
from typing import Protocol, cast

from ...contracts.timing import validate_duration
from ...runtime.timing import TimerHandle


class _TimerLoop(Protocol):
    def time(self) -> float:
        """Read the loop's finite monotonic clock."""

    def call_at(self, when: float, callback: Callable[[], None]) -> TimerHandle:
        """Schedule on this loop, never inline; delivery may be one resolution early."""


class AsyncioMonotonicTimer:
    """Inject HA's existing event loop; create no loop, task, thread or polling timer.

    Clock resolution defaults to the standard asyncio monotonic clock metadata.
    An alternative loop must supply its matching resolution explicitly. All calls
    belong to the loop thread. Callbacks must be brief owner handoffs.
    """

    def __init__(self, loop: _TimerLoop, *, clock_resolution: float | None = None) -> None:
        self._loop = loop
        resolution = (
            get_clock_info("monotonic").resolution if clock_resolution is None else clock_resolution
        )
        self._resolution = validate_duration(resolution)

    def call_later(self, seconds: float, callback: Callable[[], None]) -> TimerHandle:
        if type(seconds) not in (int, float):
            raise TypeError("Timer delay must be a non-boolean number")
        try:
            delay = float(cast(int | float, seconds))
        except OverflowError as error:
            raise ValueError("Timer delay must be finite") from error
        if not isfinite(delay) or delay < 0:
            raise ValueError("Timer delay must be finite and nonnegative")
        if not callable(callback):
            raise TypeError("Timer callback must be callable")
        deadline = _deadline_after(self._loop.time(), delay)
        return _DeadlineTimer(self._loop, deadline, self._resolution, callback)


def _deadline_after(origin: float, delay: float) -> float:
    deadline = origin + delay
    if not isfinite(deadline):
        raise ValueError("Timer deadline is not representable")
    # TwoSum recovers the addition's rounding error. Advance only a sum rounded
    # down, including a tiny positive delay lost entirely at a large uptime.
    recovered_delay = deadline - origin
    error = (origin - (deadline - recovered_delay)) + (delay - recovered_delay)
    if error > 0:
        deadline = nextafter(deadline, inf)
    if not isfinite(deadline):
        raise ValueError("Timer deadline is not representable")
    return deadline


class _DeadlineTimer:
    __slots__ = ("_loop", "_deadline", "_resolution", "_callback", "_handle")

    def __init__(
        self, loop: _TimerLoop, deadline: float, resolution: float, callback: Callable[[], None]
    ) -> None:
        self._loop = loop
        self._deadline = deadline
        self._resolution = resolution
        self._callback: Callable[[], None] | None = callback
        self._handle: TimerHandle | None = loop.call_at(deadline, self._wake)

    def cancel(self) -> None:
        self._callback = None
        handle = self._handle
        self._handle = None
        if handle is not None:
            handle.cancel()

    def _wake(self) -> None:
        callback = self._callback
        if callback is None:
            return
        now = self._loop.time()
        if now < self._deadline:
            # Beyond the loop's early-wakeup horizon, including float rounding.
            # Yield to the loop rather than repeatedly running in its ready batch.
            retry_at = max(self._deadline, nextafter(now + self._resolution, inf))
            self._handle = self._loop.call_at(retry_at, self._wake)
            return
        self._callback = None
        self._handle = None
        callback()
