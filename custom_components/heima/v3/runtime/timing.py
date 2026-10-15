"""Process-local AtJob dispatch; the timer port must use monotonic time."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from math import inf, nextafter
from typing import Protocol

from ..contracts.instants import parse_instant
from ..contracts.timing import AtJob
from .clock import ExecutionClockReading

type JobCallback = Callable[[AtJob], None]
type JobKey = tuple[str, str]


class TimerHandle(Protocol):
    def cancel(self) -> None:
        """Cancel without blocking or raising; repeated cancellation is safe."""


class MonotonicTimer(Protocol):
    def call_later(self, seconds: float, callback: Callable[[], None]) -> TimerHandle:
        """Defer callback on this event loop, including when seconds is zero.

        Raising leaves no scheduled callback. Callbacks never run inline, and
        scheduler calls and dispatch run serially on the same event loop.
        """


@dataclass(frozen=True, slots=True)
class _Pending:
    token: object
    job: AtJob
    callback: JobCallback
    handle: TimerHandle


@dataclass(frozen=True, slots=True)
class WallClockRearmFailure:
    job: AtJob
    error_type: str
    message: str


class AtJobScheduler:
    """One pending timer per (owner, job_id), without HA or ambient clocks.

    The caller supplies paired wall/cycle-instant execution references. This class
    does not detect clock discontinuities, compute recurring deadlines, or
    emit runtime diagnostics. Admission errors propagate to that boundary.
    Once delivered, an owner must check its activation and arm revision before
    acting; scheduler cancellation cannot retract an already delivered callback.
    """

    def __init__(self, timer: MonotonicTimer) -> None:
        self._timer = timer
        self._pending: dict[JobKey, _Pending] = {}

    @property
    def pending_jobs(self) -> tuple[AtJob, ...]:
        return tuple(pending.job for pending in self._pending.values())

    def register(self, job: AtJob, now: ExecutionClockReading, callback: JobCallback) -> None:
        if not isinstance(job, AtJob):
            raise TypeError("Registration requires AtJob")
        if not callable(callback):
            raise TypeError("Registration requires an owner callback")
        # Revalidate at admission, including a subtype/reconstructed object.
        validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
        reading = _validated_reading(now)
        reference = reading.wall if validated.basis == "wall_clock" else reading.cycle_instant
        delay = _countdown(parse_instant(validated.due) - parse_instant(reference))
        self._arm(validated, delay, callback)

    def cancel(self, owner: str, job_id: str) -> None:
        pending = self._pending.pop((owner, job_id), None)
        if pending is not None:
            pending.handle.cancel()

    def rearm_wall_clock(self, now: ExecutionClockReading) -> tuple[WallClockRearmFailure, ...]:
        """Re-arm each civil timer; retire invalid old arms if replacement fails.

        Keeping the pre-correction monotonic countdown could execute too early.
        Return each failure for owner diagnostics; continue with the other jobs.
        """
        instant = parse_instant(_validated_reading(now).wall)
        failures = []
        for pending in tuple(self._pending.values()):
            if pending.job.basis == "wall_clock":
                delay = _countdown(parse_instant(pending.job.due) - instant)
                try:
                    self._arm(pending.job, delay, pending.callback)
                except Exception as error:
                    self.cancel(pending.job.owner, pending.job.job_id)
                    failures.append(
                        WallClockRearmFailure(pending.job, type(error).__qualname__, str(error))
                    )
        return tuple(failures)

    def cancel_all(self) -> None:
        pending = tuple(self._pending.values())
        self._pending.clear()
        for entry in pending:
            entry.handle.cancel()

    def _arm(self, job: AtJob, delay: float, callback: JobCallback) -> None:
        key = (job.owner, job.job_id)
        token = object()
        handle = self._timer.call_later(delay, lambda: self._deliver(key, token))
        previous = self._pending.get(key)
        self._pending[key] = _Pending(token, job, callback, handle)
        if previous is not None:
            previous.handle.cancel()

    def _deliver(self, key: JobKey, token: object) -> None:
        pending = self._pending.get(key)
        if pending is None:
            return
        if pending.token is not token:
            return
        del self._pending[key]
        pending.callback(pending.job)


def _validated_reading(reading: ExecutionClockReading) -> ExecutionClockReading:
    if not isinstance(reading, ExecutionClockReading):
        raise TypeError("Scheduling requires paired execution references")
    return ExecutionClockReading(reading.wall, reading.cycle_instant)


def _countdown(delta: timedelta) -> float:
    """Transport integer microseconds as the least float that cannot fire early."""
    microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    if microseconds <= 0:
        return 0.0
    seconds = microseconds / 1_000_000
    numerator, denominator = seconds.as_integer_ratio()
    if numerator * 1_000_000 < microseconds * denominator:
        seconds = nextafter(seconds, inf)
    return seconds
