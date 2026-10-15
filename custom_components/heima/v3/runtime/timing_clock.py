"""Capture clock observations and apply basis-specific scheduler effects."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..contracts.instants import EvidenceInstant
from ..contracts.timing import AtJob
from .clock import ClockComparison, CycleClock, CycleTick, ExecutionClockReading
from .timing import AtJobScheduler


@dataclass(frozen=True, slots=True)
class ClockSample:
    wall: EvidenceInstant
    monotonic_ns: int


class ClockSource(Protocol):
    def sample(self) -> ClockSample:
        """Capture near-paired raw UTC wall and process-monotonic readings."""


@dataclass(frozen=True, slots=True)
class ClockRearmFault:
    comparison: ClockComparison
    job: AtJob
    error_type: str
    message: str


class TimingClock:
    """Single-loop clock/scheduler bridge, with explicit nonblocking effect ports.

    observe receives each classified reading before re-arm, including immediate
    gap intents. It must update conservative in-memory state, publish applicable
    diagnostics and queue persistence without waiting for a durable acknowledgement.
    report_rearm_fault logs/publishes infrastructure failure. Both ports must not
    raise. CycleTick remains available to the caller for pending-gap completion.
    """

    def __init__(
        self,
        clock: CycleClock,
        source: ClockSource,
        scheduler: AtJobScheduler,
        observe: Callable[[ClockComparison], None],
        report_rearm_fault: Callable[[ClockRearmFault], None],
    ) -> None:
        self._clock = clock
        self._source = source
        self._scheduler = scheduler
        self._observe = observe
        self._report_rearm_fault = report_rearm_fault

    def read_execution(self) -> ExecutionClockReading:
        """Read an execution reference without advancing cycle/comparison baselines."""
        return self._clock.read_execution(self._source.sample().wall)

    def next_cycle(self) -> CycleTick:
        sample = self._source.sample()
        tick = self._clock.next_cycle(sample.wall, sample.monotonic_ns)
        self._apply(tick.comparison)
        return tick

    def check_periodic(self) -> ClockComparison:
        """Use from the system-owned 60 s continuity CronEntry, outside a cycle."""
        sample = self._source.sample()
        comparison = self._clock.compare(sample.wall, sample.monotonic_ns)
        self._apply(comparison)
        return comparison

    def _apply(self, comparison: ClockComparison) -> None:
        self._observe(comparison)
        if comparison.requires_wall_clock_rearm:
            reading = comparison.execution_clock
            assert reading is not None
            for failure in self._scheduler.rearm_wall_clock(reading):
                self._report_rearm_fault(
                    ClockRearmFault(comparison, failure.job, failure.error_type, failure.message)
                )
