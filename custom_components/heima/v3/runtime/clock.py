"""Cycle instants, clock-change classification and gap boundary intents, without I/O."""

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Literal

from ..contracts.instants import EvidenceInstant, format_instant, parse_instant, validate_instant

_ONE_SECOND_NS = 1_000_000_000


@dataclass(frozen=True, slots=True)
class ExecutionClockReading:
    """Paired execution references; process-local, never a history timestamp."""

    wall: EvidenceInstant
    cycle_instant: EvidenceInstant

    def __post_init__(self) -> None:
        parse_instant(self.wall)
        parse_instant(self.cycle_instant)
        if self.cycle_instant < self.wall:
            raise ValueError("Cycle-instant reference must not precede wall time")


@dataclass(frozen=True, slots=True)
class ClockGap:
    """Boundary intent for future persistence; an end is not an acknowledgement."""

    start: EvidenceInstant
    end: EvidenceInstant | None
    await_floor_recovery: bool

    def finish(self, tick: "CycleTick") -> "ClockGap":
        if self.end is not None:
            return self
        if tick.when <= self.start:
            return self
        if tick.wall_behind_floor:
            return replace(self, await_floor_recovery=True)
        if self.await_floor_recovery:
            if tick.previous_when is not None:
                if tick.comparison.wall <= _successor(tick.previous_when):
                    return self
        return replace(self, end=tick.when)


@dataclass(frozen=True, slots=True)
class ClockComparison:
    """Process-local reading; no measured elapsed interval exists at bootstrap."""

    wall: EvidenceInstant
    adjustment_ns: int | None
    discontinuity: Literal["forward", "backward"] | None
    bootstrap_offset_ns: int | None = None
    detection_point: Literal["cycle_start", "periodic_check"] | None = None
    wall_behind_floor: bool = False
    gap: ClockGap | None = None
    execution_clock: ExecutionClockReading | None = None

    @property
    def requires_wall_clock_rearm(self) -> bool:
        return self.discontinuity is not None

    @property
    def requires_clock_regression(self) -> bool:
        if self.discontinuity == "backward":
            return True
        correction = self.adjustment_ns
        if correction is None:
            correction = self.bootstrap_offset_ns
        if correction is None:
            return False
        return correction < 0 and self.wall_behind_floor


@dataclass(frozen=True, slots=True)
class CycleTick:
    when: EvidenceInstant
    previous_when: EvidenceInstant | None
    wall_behind_floor: bool
    comparison: ClockComparison


class ClockDiscontinuityDetector:
    """Share one comparison baseline across cycle starts and periodic checks.

    Inputs are paired canonical wall and monotonic-nanosecond readings supplied
    by Layer 0. No raw clock is read here. Bootstrap's durable floor is not a
    monotonic anchor; forward downtime must not be classified as a clock jump.
    """

    def __init__(self, durable_floor: EvidenceInstant | None = None) -> None:
        self._durable_floor = None if durable_floor is None else validate_instant(durable_floor)
        self._previous_wall: EvidenceInstant | None = None
        self._previous_monotonic_ns: int | None = None

    def compare(self, wall: EvidenceInstant, monotonic_ns: int) -> ClockComparison:
        validated = validate_instant(wall)
        if type(monotonic_ns) is not int:
            raise TypeError("Monotonic reading must be a non-boolean integer")
        if monotonic_ns < 0:
            raise ValueError("Monotonic reading must be nonnegative")
        direction: Literal["forward", "backward"] | None = None
        adjustment = None
        bootstrap_offset = None
        previous_mono = self._previous_monotonic_ns
        if previous_mono is None:
            floor = self._durable_floor
            if floor is not None:
                bootstrap_offset = _difference_ns(validated, floor)
                if bootstrap_offset < -_ONE_SECOND_NS:
                    direction = "backward"
        else:
            if monotonic_ns < previous_mono:
                raise ValueError("Monotonic clock must not regress within a process")
            previous_wall = self._previous_wall
            assert previous_wall is not None
            adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
            if adjustment > _ONE_SECOND_NS:
                direction = "forward"
            elif adjustment < -_ONE_SECOND_NS:
                direction = "backward"
        self._previous_wall = validated
        self._previous_monotonic_ns = monotonic_ns
        return ClockComparison(validated, adjustment, direction, bootstrap_offset)


class CycleClock:
    """Strictly increasing canonical instants; compare-only checks create no cycle.

    Outcomes describe clock changes and whether the wall reading fell behind the
    floor. Future runtime wiring owns diagnostics, scheduler re-arm, and durable
    acknowledgement of gap boundaries. No history continuity is certified here.
    """

    def __init__(self, durable_floor: EvidenceInstant | None = None) -> None:
        self._previous = None if durable_floor is None else validate_instant(durable_floor)
        self._detector = ClockDiscontinuityDetector(durable_floor)

    @property
    def previous_instant(self) -> EvidenceInstant | None:
        return self._previous

    def compare(self, wall: EvidenceInstant, monotonic_ns: int) -> ClockComparison:
        reading = self.read_execution(wall)
        behind = self._behind_floor(wall)
        comparison = self._detector.compare(wall, monotonic_ns)
        gap = None
        if comparison.requires_wall_clock_rearm:
            if self._previous is not None:
                gap = ClockGap(self._previous, None, behind)
        return replace(
            comparison,
            detection_point="periodic_check",
            wall_behind_floor=behind,
            gap=gap,
            execution_clock=reading,
        )

    def next_cycle(self, wall: EvidenceInstant, monotonic_ns: int) -> CycleTick:
        previous = self._previous
        # Compute before mutating either baseline, including calendar overflow.
        reading = self.read_execution(wall)
        when = reading.cycle_instant
        behind = self._behind_floor(wall)
        comparison = self._detector.compare(wall, monotonic_ns)
        gap = None
        if comparison.requires_wall_clock_rearm:
            if comparison.discontinuity == "backward" and behind:
                gap = ClockGap(when, None, True)
            elif previous is not None:
                gap = ClockGap(previous, when, False)
        comparison = replace(
            comparison,
            detection_point="cycle_start",
            wall_behind_floor=behind,
            gap=gap,
            execution_clock=reading,
        )
        self._previous = when
        return CycleTick(when, previous, behind, comparison)

    def read_execution(self, wall: EvidenceInstant) -> ExecutionClockReading:
        """Apply the floor at this reading without consuming a cycle/comparison."""
        validated = validate_instant(wall)
        cycle_instant = validated
        if self._previous is not None:
            cycle_instant = max(validated, _successor(self._previous))
        return ExecutionClockReading(validated, cycle_instant)

    def _behind_floor(self, wall: EvidenceInstant) -> bool:
        validate_instant(wall)
        if self._previous is None:
            return False
        # Canonical instants have integer microseconds: wall < previous + 1 us
        # is exactly wall <= previous, including at the maximum calendar value.
        return wall <= self._previous


def _successor(instant: EvidenceInstant) -> EvidenceInstant:
    return format_instant(parse_instant(instant) + timedelta(microseconds=1))


def _difference_ns(later: EvidenceInstant, earlier: EvidenceInstant) -> int:
    elapsed = parse_instant(later) - parse_instant(earlier)
    # Integer arithmetic keeps the specified >1 s threshold exact, including
    # 1 ns either side; total_seconds() would introduce a float comparison.
    return ((elapsed.days * 86_400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds) * 1000
