"""Standing intervals: faults, reentrant edits and fresh execution references."""

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.deadlines import Unrepresentable
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.timing import (
    AtJob,
    CronEntry,
    IntervalRecurrence,
    WeeklyRecurrence,
    Window,
)
from custom_components.heima.v3.runtime.clock import ExecutionClockReading
from custom_components.heima.v3.runtime.interval_recurrences import (
    IntervalDeadlineRejected,
    IntervalRearmFault,
    IntervalRecurrences,
    JobCallbackFault,
)
from custom_components.heima.v3.runtime.timing import AtJobScheduler

ANCHOR = "2026-10-14T12:00:00.000000+00:00"


def instant(seconds=0):
    return format_instant(parse_instant(ANCHOR) + timedelta(seconds=seconds))


def definition(seconds=30, owner="owner", job_id="id"):
    return CronEntry(job_id, owner, IntervalRecurrence(Window(seconds)), "label")


def reading(value=ANCHOR, wall=None):
    return ExecutionClockReading(wall or value, value)


class Clock:
    def __init__(self):
        self.current = reading()
        self.failure = None
        self.reads = 0

    def __call__(self):
        self.reads += 1
        if self.failure:
            raise self.failure
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


def setup():
    timer = Timer()
    clock = Clock()
    diagnostics = []
    scheduler = AtJobScheduler(timer)
    service = IntervalRecurrences(scheduler, clock, diagnostics.append)
    return service, scheduler, timer, clock, diagnostics


def test_automatic_rearm_uses_reading_after_owner_work():
    service, scheduler, timer, clock, diagnostics = setup()
    delivered = []

    def callback(job):
        delivered.append(job)
        clock.current = reading(instant(35), wall=instant(33))

    assert service.register(definition(), callback) is None
    clock.current = reading(instant(30))
    timer.handles[0].callback()
    assert delivered[0].due == instant(30)
    assert scheduler.pending_jobs[0].due == instant(65)
    assert timer.handles[-1].seconds == 30
    assert clock.reads == 2
    assert service.entries == (definition(),)
    assert diagnostics == []


def test_callback_failure_is_diagnosed_and_recurring_safety_net_survives():
    service, scheduler, timer, clock, diagnostics = setup()

    def failing(job):
        raise ValueError("owner failed")

    service.register(definition(), failing)
    received = []
    service.register(definition(owner="other"), received.append)
    clock.current = reading(instant(30))
    first, second = timer.handles
    first.callback()
    second.callback()
    assert len(received) == 1
    assert diagnostics == [
        JobCallbackFault(
            AtJob("id", "owner", instant(30), "label", "elapsed"), "ValueError", "owner failed"
        )
    ]
    assert len(scheduler.pending_jobs) == 2
    assert all(job.due == instant(60) for job in scheduler.pending_jobs)
    with pytest.raises(FrozenInstanceError):
        diagnostics[0].message = "changed"


@pytest.mark.parametrize("fails", [False, True])
def test_owner_cancellation_prevents_automatic_rearm(fails):
    service, scheduler, timer, clock, diagnostics = setup()

    def callback(job):
        service.cancel(job.owner, job.job_id)
        if fails:
            raise RuntimeError("cancelled by owner")

    service.register(definition(), callback)
    timer.handles[0].callback()
    assert service.entries == ()
    assert scheduler.pending_jobs == ()
    assert len(timer.handles) == 1
    assert len(diagnostics) == int(fails)


@pytest.mark.parametrize("fails", [False, True])
def test_owner_replacement_is_not_overwritten_by_old_rearm(fails):
    service, scheduler, timer, clock, diagnostics = setup()
    delivered = []
    replacement = definition(60)

    def callback(job):
        service.register(replacement, delivered.append)
        if fails:
            raise RuntimeError("old owner failed after replacement")

    service.register(definition(), callback)
    clock.current = reading(instant(30))
    old = timer.handles[0]
    old.callback()
    assert service.entries == (replacement,)
    assert scheduler.pending_jobs[0].due == instant(90)
    assert len(timer.handles) == 2
    old.callback()
    assert len(timer.handles) == 2
    clock.current = reading(instant(90))
    timer.handles[-1].callback()
    assert delivered[0].due == instant(90)
    assert scheduler.pending_jobs[0].due == instant(150)
    assert len(diagnostics) == int(fails)


def test_failed_reentrant_replacement_keeps_old_rule_running():
    service, scheduler, timer, clock, diagnostics = setup()

    def callback(job):
        timer.fail = True
        try:
            with pytest.raises(RuntimeError):
                service.register(definition(60), lambda job: None)
        finally:
            timer.fail = False

    service.register(definition(), callback)
    clock.current = reading(instant(30))
    timer.handles[0].callback()
    assert service.entries == (definition(),)
    assert scheduler.pending_jobs[0].due == instant(60)
    assert len(timer.handles) == 2
    assert diagnostics == []


def test_shutdown_cancels_only_owned_rules_and_stale_callbacks_do_nothing():
    service, scheduler, timer, clock, diagnostics = setup()
    delivered = []
    service.register(definition(), delivered.append)
    service.register(definition(owner="other"), delivered.append)
    unrelated = AtJob("one-shot", "engine", instant(60), "one-shot", "elapsed")
    scheduler.register(unrelated, clock.current, delivered.append)
    first, second, third = timer.handles
    service.stop()
    service.stop()
    assert service.entries == ()
    assert scheduler.pending_jobs == (unrelated,)
    assert first.cancelled and second.cancelled
    assert not third.cancelled
    first.callback()
    second.callback()
    assert delivered == []
    third.callback()
    assert delivered == [unrelated]


def test_shutdown_inside_callback_does_not_restart_service():
    service, scheduler, timer, clock, diagnostics = setup()
    service.register(definition(), lambda job: service.stop())
    timer.handles[0].callback()
    assert service.entries == ()
    assert scheduler.pending_jobs == ()
    assert len(timer.handles) == 1


def test_cancel_missing_rule_leaves_shared_one_shot_untouched():
    service, scheduler, timer, clock, diagnostics = setup()
    job = AtJob("id", "owner", instant(30), "one-shot", "elapsed")
    scheduler.register(job, clock.current, lambda job: None)
    service.cancel("owner", "id")
    assert scheduler.pending_jobs == (job,)
    assert not timer.handles[0].cancelled


@pytest.mark.parametrize("failure", ["timer", "clock", "invalid_clock"])
def test_failed_admission_preserves_existing_registration(failure):
    service, scheduler, timer, clock, diagnostics = setup()
    service.register(definition(), lambda job: None)
    before = scheduler.pending_jobs
    if failure == "timer":
        timer.fail = True
    elif failure == "clock":
        clock.failure = RuntimeError("clock unavailable")
    else:
        clock.current = ANCHOR
    with pytest.raises((RuntimeError, TypeError)):
        service.register(definition(60), lambda job: None)
    assert service.entries == (definition(),)
    assert scheduler.pending_jobs == before
    assert len(timer.handles) == 1
    assert not timer.handles[0].cancelled


@pytest.mark.parametrize("existing", [False, True])
def test_overflow_admission_reports_once_without_changing_active_rule(existing):
    service, scheduler, timer, clock, diagnostics = setup()
    if existing:
        service.register(definition(), lambda job: None)
    before = scheduler.pending_jobs
    overflow = definition(1e308)
    result = service.register(overflow, lambda job: None)
    assert isinstance(result, Unrepresentable)
    assert diagnostics == [IntervalDeadlineRejected(overflow, result)]
    assert scheduler.pending_jobs == before
    assert len(timer.handles) == int(existing)
    assert service.entries == ((definition(),) if existing else ())
    with pytest.raises(FrozenInstanceError):
        diagnostics[0].entry = definition()


@pytest.mark.parametrize("failure", ["timer", "clock", "invalid_clock"])
def test_rearm_failure_is_reported_and_definition_is_retained(failure):
    service, scheduler, timer, clock, diagnostics = setup()
    received = []
    service.register(definition(), received.append)
    if failure == "timer":
        timer.fail = True
    elif failure == "clock":
        clock.failure = RuntimeError("clock unavailable")
    else:
        clock.current = ANCHOR
    timer.handles[0].callback()
    assert len(received) == 1
    assert scheduler.pending_jobs == ()
    assert service.entries == (definition(),)
    assert len(diagnostics) == 1
    fault = diagnostics[0]
    assert isinstance(fault, IntervalRearmFault)
    assert fault.entry == definition()
    assert fault.error_type == ("TypeError" if failure == "invalid_clock" else "RuntimeError")
    if failure != "invalid_clock":
        assert fault.message == ("timer unavailable" if failure == "timer" else "clock unavailable")
    with pytest.raises(FrozenInstanceError):
        fault.message = "changed"
    timer.handles[0].callback()
    assert len(diagnostics) == 1


def test_rearm_at_calendar_end_is_explicit_rejection_not_immediate_loop():
    service, scheduler, timer, clock, diagnostics = setup()
    service.register(definition(1e-7), lambda job: None)
    clock.current = reading("9999-12-31T23:59:59.999999+00:00")
    timer.handles[0].callback()
    assert len(timer.handles) == 1
    assert scheduler.pending_jobs == ()
    assert isinstance(diagnostics[0], IntervalDeadlineRejected)
    assert diagnostics[0].entry == definition(1e-7)
    assert diagnostics[0].deadline.anchor == clock.current.cycle_instant
    assert service.entries == (definition(1e-7),)


def test_restart_arms_from_now_without_replaying_previous_countdown():
    service, scheduler, timer, clock, diagnostics = setup()
    received = []
    service.register(definition(), received.append)
    service.stop()
    clock.current = reading(instant(1000))
    restarted = IntervalRecurrences(scheduler, clock, diagnostics.append)
    restarted.register(definition(), received.append)
    assert scheduler.pending_jobs[0].due == instant(1030)
    assert received == []
    assert timer.handles[-1].seconds == 30


def legacy_weekly_entry():
    entry = object.__new__(CronEntry)
    for field, value in (
        ("job_id", "id"),
        ("owner", "owner"),
        ("pattern", WeeklyRecurrence(frozenset({0}), 7)),
        ("label", "label"),
    ):
        object.__setattr__(entry, field, value)
    return entry


@pytest.mark.parametrize(
    "entry,callback",
    [
        (None, lambda job: None),
        (legacy_weekly_entry(), lambda job: None),
        (definition(), None),
    ],
)
def test_rejects_wrong_shapes_before_arming(entry, callback):
    service, scheduler, timer, clock, diagnostics = setup()
    with pytest.raises(TypeError):
        service.register(entry, callback)
    assert service.entries == ()
    assert timer.handles == []
    assert clock.reads == 0


@given(
    seconds=st.floats(min_value=5e-324, max_value=60, allow_nan=False, allow_infinity=False),
    count=st.integers(1, 15),
)
def test_repeated_fires_keep_one_future_arm_without_duplicate_delivery(seconds, count):
    service, scheduler, timer, clock, diagnostics = setup()
    received = []
    rule = definition(seconds)
    service.register(rule, received.append)
    for index in range(count):
        pending = scheduler.pending_jobs[0]
        assert pending.due > clock.current.cycle_instant
        clock.current = reading(pending.due)
        handle = timer.handles[-1]
        assert handle.seconds > 0
        handle.callback()
        handle.callback()
        assert len(received) == index + 1
        assert received[-1] == pending
        assert service.entries == (rule,)
        assert len(scheduler.pending_jobs) == 1
        assert scheduler.pending_jobs[0].due > pending.due
    assert diagnostics == []
