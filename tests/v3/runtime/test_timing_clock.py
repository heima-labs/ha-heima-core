"""Captured clock-to-scheduler effects, without real time or persistence."""

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.timing import AtJob, CronEntry, IntervalRecurrence, Window
from custom_components.heima.v3.runtime.clock import CycleClock, ExecutionClockReading
from custom_components.heima.v3.runtime.interval_recurrences import IntervalRecurrences
from custom_components.heima.v3.runtime.timing import AtJobScheduler
from custom_components.heima.v3.runtime.timing_clock import (
    ClockRearmFault,
    ClockSample,
    TimingClock,
)

ANCHOR = "2026-10-15T12:00:00.000000+00:00"


def instant(seconds=0):
    return format_instant(parse_instant(ANCHOR) + timedelta(seconds=seconds))


class Source:
    def __init__(self):
        self.current = ClockSample(instant(), 0)
        self.calls = 0

    def sample(self):
        self.calls += 1
        return self.current


class Timer:
    def __init__(self):
        self.handles = []
        self.fail = False

    def call_later(self, seconds, callback):
        if self.fail:
            raise RuntimeError("timer unavailable")
        handle = Handle(seconds, callback)
        self.handles.append(handle)
        return handle


class Handle:
    def __init__(self, seconds, callback):
        self.seconds = seconds
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def setup(floor=None):
    source = Source()
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    observed = []
    faults = []
    domain = CycleClock(floor)
    clock = TimingClock(domain, source, scheduler, observed.append, faults.append)
    return clock, domain, source, scheduler, timer, observed, faults


def arm(scheduler, due, basis="wall_clock", key="wall"):
    job = AtJob(key, "owner", instant(due), "label", basis)
    scheduler.register(job, ExecutionClockReading(instant(), instant()), lambda job: None)
    return job


@pytest.mark.parametrize("detection", ["cycle", "periodic", "bootstrap"])
def test_raw_detecting_wall_rearms_civil_jobs_without_touching_elapsed(detection):
    clock, domain, source, scheduler, timer, observed, faults = setup(
        instant() if detection == "bootstrap" else None
    )
    if detection != "bootstrap":
        clock.next_cycle()
    wall = arm(scheduler, 110)
    elapsed = arm(scheduler, 30, "elapsed", "elapsed")
    old_wall, old_elapsed = timer.handles
    source.current = ClockSample(instant(-2), 1_000_000_000)
    if detection == "periodic":
        comparison = clock.check_periodic()
    else:
        comparison = clock.next_cycle().comparison
    assert comparison.discontinuity == "backward"
    assert comparison.execution_clock.wall == instant(-2)
    assert timer.handles[-1].seconds == 112
    assert old_wall.cancelled
    assert not old_elapsed.cancelled
    assert scheduler.pending_jobs == (wall, elapsed)
    assert observed[-1] is comparison
    assert faults == []


def test_periodic_gap_opens_before_rearm_and_next_cycle_does_not_redetect():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    arm(scheduler, 110)

    def observe(comparison):
        observed.append(comparison)
        if comparison.discontinuity:
            assert len(timer.handles) == 1

    clock = TimingClock(domain, source, scheduler, observe, faults.append)
    source.current = ClockSample(instant(58), 60_000_000_000)
    comparison = clock.check_periodic()
    assert comparison.detection_point == "periodic_check"
    assert comparison.gap.start == instant()
    assert comparison.gap.end is None
    assert timer.handles[-1].seconds == 52
    assert domain.previous_instant == instant()
    source.current = ClockSample(instant(59), 61_000_000_000)
    tick = clock.next_cycle()
    assert tick.comparison.discontinuity is None
    assert len(timer.handles) == 2
    assert comparison.gap.finish(tick).end == instant(59)
    assert comparison.gap.end is None  # Completion intent is not durable acknowledgement.
    assert source.calls == 3


@pytest.mark.parametrize(
    "wall,mono,regression", [(0.5, 1_000_000_000, False), (-0.4, 100_000_000, True)]
)
def test_small_correction_only_reports_floor_regression_without_rearm(wall, mono, regression):
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    arm(scheduler, 110)
    source.current = ClockSample(instant(wall), mono)
    comparison = clock.check_periodic()
    assert comparison.requires_clock_regression is regression
    assert comparison.discontinuity is None
    assert comparison.gap is None
    assert len(timer.handles) == 1
    assert observed[-1] is comparison


def test_execution_read_does_not_advance_cycle_or_comparison():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    source.current = ClockSample(instant(-1), 1_000_000_000)
    reference = clock.read_execution()
    assert reference.wall == instant(-1)
    assert reference.cycle_instant == "2026-10-15T12:00:00.000001+00:00"
    assert domain.previous_instant == instant()
    assert len(observed) == 1
    source.current = ClockSample(instant(2), 2_000_000_000)
    assert clock.next_cycle().comparison.adjustment_ns == 0
    assert source.calls == 3


def test_rearm_failure_keeps_comparison_and_gap_observable():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    job = arm(scheduler, 110)
    timer.fail = True
    source.current = ClockSample(instant(70), 60_000_000_000)
    comparison = clock.check_periodic()
    assert comparison.discontinuity == "forward"
    assert observed[-1] is comparison
    assert faults == [ClockRearmFault(comparison, job, "RuntimeError", "timer unavailable")]
    assert scheduler.pending_jobs == ()
    assert timer.handles[0].cancelled
    with pytest.raises(FrozenInstanceError):
        faults[0].message = "changed"


def test_failed_rearm_cannot_deliver_old_arm_before_corrected_wall_due():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    job = AtJob("wall", "owner", instant(110), "label", "wall_clock")
    delivered = []
    scheduler.register(job, ExecutionClockReading(instant(), instant()), delivered.append)
    timer.fail = True
    source.current = ClockSample(instant(-2), 1_000_000_000)
    clock.check_periodic()
    # At the old monotonic deadline (110 s), corrected wall is only 107 s.
    source.current = ClockSample(instant(107), 110_000_000_000)
    timer.handles[0].callback()
    assert delivered == []
    assert scheduler.pending_jobs == ()
    assert len(faults) == 1


def test_scheduler_returns_immutable_per_job_failure_detail():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    job = arm(scheduler, 110)
    timer.fail = True
    reading = ExecutionClockReading(instant(-2), instant())
    failures = scheduler.rearm_wall_clock(reading)
    assert isinstance(failures, tuple)
    assert len(failures) == 1
    failure = failures[0]
    assert failure.job == job
    assert (failure.error_type, failure.message) == ("RuntimeError", "timer unavailable")
    with pytest.raises(FrozenInstanceError):
        failure.message = "changed"
    assert scheduler.pending_jobs == ()


def test_rearm_failure_is_per_job_and_does_not_block_other_civil_jobs():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    first = arm(scheduler, 110)
    second = arm(scheduler, 120, key="other")
    elapsed = arm(scheduler, 30, "elapsed", "elapsed")
    original = timer.call_later
    attempts = []

    def partial_failure(seconds, callback):
        attempts.append(seconds)
        if len(attempts) == 1:
            raise RuntimeError("one timer failed")
        return original(seconds, callback)

    timer.call_later = partial_failure
    source.current = ClockSample(instant(-2), 1_000_000_000)
    comparison = clock.check_periodic()
    assert faults == [ClockRearmFault(comparison, first, "RuntimeError", "one timer failed")]
    assert scheduler.pending_jobs == (second, elapsed)
    assert attempts == [112, 122]
    assert timer.handles[0].cancelled
    assert timer.handles[1].cancelled
    assert not timer.handles[2].cancelled
    assert timer.handles[-1].seconds == 122


def test_sixty_second_interval_uses_same_comparison_path_without_creating_cycle():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    interval_faults = []
    intervals = IntervalRecurrences(scheduler, clock.read_execution, interval_faults.append)
    checks = []

    def check(job):
        checks.append(clock.check_periodic())

    entry = CronEntry("continuity", "layer0", IntervalRecurrence(Window(60)), "continuity")
    intervals.register(entry, check)
    assert timer.handles[-1].seconds == 60
    source.current = ClockSample(instant(58), 60_000_000_000)
    timer.handles[0].callback()
    assert checks[0].discontinuity == "backward"
    assert domain.previous_instant == instant()
    assert scheduler.pending_jobs[0].due == instant(118)
    assert timer.handles[-1].seconds == 60
    assert interval_faults == faults == []


def test_invalid_monotonic_sample_rejects_before_observation_and_rearm():
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    source.current = ClockSample(instant(10), -1)
    with pytest.raises(ValueError):
        clock.check_periodic()
    assert len(observed) == 1
    assert domain.previous_instant == instant()
    source.current = ClockSample(instant(1), 1_000_000_000)
    assert clock.next_cycle().comparison.adjustment_ns == 0


@given(adjustment=st.integers(-10, 10))
def test_generated_changes_preserve_due_and_only_rearm_civil_jobs(adjustment):
    clock, domain, source, scheduler, timer, observed, faults = setup()
    clock.next_cycle()
    wall = arm(scheduler, 200)
    elapsed = arm(scheduler, 100, "elapsed", "elapsed")
    old_wall, old_elapsed = timer.handles
    source.current = ClockSample(instant(30 + adjustment), 30_000_000_000)
    comparison = clock.check_periodic()
    assert comparison.adjustment_ns == adjustment * 1_000_000_000
    assert old_wall.cancelled is (abs(adjustment) > 1)
    assert not old_elapsed.cancelled
    if abs(adjustment) > 1:
        assert timer.handles[-1].seconds == 170 - adjustment
    assert scheduler.pending_jobs == (wall, elapsed)
    assert faults == []
