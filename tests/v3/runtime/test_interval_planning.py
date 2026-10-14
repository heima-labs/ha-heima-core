"""Interval planning/admission using canonical construction and paired references."""

from datetime import timedelta

import pytest

from custom_components.heima.v3.contracts.deadlines import Unrepresentable
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.timing import (
    CronEntry,
    IntervalRecurrence,
    WeeklyRecurrence,
    Window,
)
from custom_components.heima.v3.runtime.clock import ExecutionClockReading
from custom_components.heima.v3.runtime.recurrence import plan_interval_job, register_interval_job
from custom_components.heima.v3.runtime.timing import AtJobScheduler

ANCHOR = "2026-10-14T12:00:00.000000+00:00"


def entry(seconds=1e-7):
    return CronEntry("id", "owner", IntervalRecurrence(Window(seconds)), "label")


def reading(anchor=ANCHOR, wall=None):
    return ExecutionClockReading(wall or anchor, anchor)


class Timer:
    def __init__(self):
        self.arms = []

    def call_later(self, seconds, callback):
        handle = Handle(seconds, callback)
        self.arms.append(handle)
        return handle


class Handle:
    def __init__(self, seconds, callback):
        self.seconds = seconds
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def test_elapsed_planning_uses_floor_and_preserves_identity():
    result = plan_interval_job(entry(30), reading(wall="2026-10-14T11:59:58.000000+00:00"))
    assert result.due == "2026-10-14T12:00:30.000000+00:00"
    assert (result.job_id, result.owner, result.label, result.basis) == (
        "id",
        "owner",
        "label",
        "elapsed",
    )


def test_tiny_interval_rearms_after_each_current_anchor():
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    current = reading()
    delivered = []

    def callback(job):
        nonlocal current
        delivered.append(job)
        current = reading(job.due)
        assert register_interval_job(scheduler, entry(), current, callback) is None

    assert register_interval_job(scheduler, entry(), current, callback) is None
    for us in range(1, 6):
        armed = timer.arms[-1]
        assert armed.seconds == 1e-6
        armed.callback()
        assert delivered[-1].due == format_instant(
            parse_instant(ANCHOR) + timedelta(microseconds=us)
        )
        armed.callback()
        assert len(delivered) == us
    assert len(scheduler.pending_jobs) == 1


def test_overflow_returns_diagnostic_and_preserves_existing_arm():
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    assert register_interval_job(scheduler, entry(1), reading(), lambda job: None) is None
    existing = scheduler.pending_jobs
    result = register_interval_job(scheduler, entry(1e308), reading(), lambda job: None)
    assert isinstance(result, Unrepresentable)
    assert result.anchor == ANCHOR
    assert result.duration == Window(1e308)
    assert len(timer.arms) == 1
    assert not timer.arms[0].cancelled
    assert scheduler.pending_jobs == existing


def test_overflow_on_empty_scheduler_arms_nothing():
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    result = register_interval_job(
        scheduler, entry(), reading("9999-12-31T23:59:59.999999+00:00"), lambda job: None
    )
    assert isinstance(result, Unrepresentable)
    assert timer.arms == []
    assert scheduler.pending_jobs == ()


def test_late_delivery_retains_due_and_next_arm_uses_current_clock():
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    assert register_interval_job(scheduler, entry(0.1), reading(), delivered.append) is None
    original = scheduler.pending_jobs[0]
    timer.arms[-1].callback()  # Coordinator delivers after a simulated loop stall.
    assert delivered == [original]
    assert original.due == "2026-10-14T12:00:00.100000+00:00"
    late = reading("2026-10-14T12:00:00.105000+00:00")
    assert register_interval_job(scheduler, entry(0.1), late, delivered.append) is None
    assert scheduler.pending_jobs[0].due == "2026-10-14T12:00:00.205000+00:00"
    assert timer.arms[-1].seconds == 0.1


@pytest.mark.parametrize(
    "definition,clock",
    [
        (None, None),
        (CronEntry("id", "owner", WeeklyRecurrence(frozenset({0}), 1), "label"), reading()),
        (entry(), None),
    ],
)
def test_planning_rejects_wrong_shapes(definition, clock):
    with pytest.raises(TypeError):
        plan_interval_job(definition, clock)
