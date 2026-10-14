"""Layer 0 §3.1 dispatch, simulated monotonic time and callback races."""

import heapq
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import format_instant
from custom_components.heima.v3.contracts.timing import AtJob
from custom_components.heima.v3.runtime import timing
from custom_components.heima.v3.runtime.clock import CycleClock, ExecutionClockReading
from custom_components.heima.v3.runtime.timing import AtJobScheduler

ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)


def instant(seconds=0):
    return format_instant(ANCHOR + timedelta(seconds=seconds))


def reading(seconds=0):
    value = instant(seconds)
    return ExecutionClockReading(value, value)


def job(seconds=10, owner="engine", job_id="job", basis="elapsed"):
    return AtJob(job_id, owner, instant(seconds), "label", basis)


@dataclass
class Handle:
    due: float
    callback: object
    cancelled: bool = False

    def cancel(self):
        self.cancelled = True


class FakeTimer:
    def __init__(self):
        self.now = 0.0
        self.handles = []
        self.queue = []
        self.fail = False

    def call_later(self, seconds, callback):
        if self.fail:
            raise RuntimeError("Timer unavailable")
        assert seconds >= 0
        handle = Handle(self.now + seconds, callback)
        heapq.heappush(self.queue, (handle.due, len(self.handles), handle))
        self.handles.append(handle)
        return handle

    def advance(self, seconds):
        target = self.now + seconds
        while self.queue and self.queue[0][0] <= target:
            due, _, handle = heapq.heappop(self.queue)
            self.now = due
            if not handle.cancelled:
                handle.callback()
        self.now = target

    def drain_ready(self):
        """Deliver overdue callbacks at current time, after a simulated loop stall."""
        while self.queue:
            due, _, handle = self.queue[0]
            if due > self.now:
                break
            heapq.heappop(self.queue)
            if not handle.cancelled:
                handle.callback()


@pytest.fixture
def runtime():
    timer = FakeTimer()
    return timer, AtJobScheduler(timer)


@pytest.mark.parametrize("delay", [-1, -0.000001, 0, 0.000001, 1])
def test_deadline_boundaries_and_one_delivery(runtime, delay):
    timer, scheduler = runtime
    delivered = []
    definition = job(delay)
    scheduler.register(definition, reading(), delivered.append)
    assert delivered == []  # An immediate due still defers to the event loop.
    assert timer.handles[-1].due == max(0, delay)
    assert scheduler.pending_jobs == (definition,)
    if delay > 0:
        timer.advance(delay / 2)
        assert delivered == []
        timer.advance(delay / 2)
    else:
        timer.advance(0)
    assert delivered == [definition]
    assert scheduler.pending_jobs == ()
    timer.handles[-1].callback()  # A timer port delivering twice cannot repeat work.
    assert delivered == [definition]


def test_replacement_cancels_old_handle_and_discards_queued_callback(runtime):
    timer, scheduler = runtime
    old, new = [], []
    scheduler.register(job(10), reading(), old.append)
    original = timer.handles[-1]
    timer.advance(1)
    replacement = job(20)
    scheduler.register(replacement, reading(1), new.append)
    assert original.cancelled
    assert scheduler.pending_jobs == (replacement,)
    original.callback()  # Cancellation can race with a ready callback.
    assert old == [] and new == []
    timer.advance(19)
    assert new == [replacement] and old == []


def test_owner_scopes_replace_and_cancel_keys(runtime):
    timer, scheduler = runtime
    first, second, other_id = [], [], []
    scheduler.register(job(owner="first"), reading(), first.append)
    scheduler.register(job(owner="second"), reading(), second.append)
    scheduler.register(job(owner="first", job_id="other"), reading(), other_id.append)
    scheduler.cancel("first", "job")
    scheduler.cancel("first", "job")
    scheduler.cancel("missing", "job")
    assert len(scheduler.pending_jobs) == 2
    timer.handles[0].callback()
    timer.advance(10)
    assert first == []
    assert second == [job(owner="second")]
    assert other_id == [job(owner="first", job_id="other")]


@pytest.mark.parametrize("shift,expected_wall_delay", [(0, 10), (20, 0), (-20, 30)])
def test_only_wall_clock_jobs_rearm_against_unchanged_due(runtime, shift, expected_wall_delay):
    timer, scheduler = runtime
    elapsed, wall = [], []
    elapsed_job = job(job_id="elapsed")
    wall_job = job(job_id="wall", basis="wall_clock")
    scheduler.register(elapsed_job, reading(), elapsed.append)
    scheduler.register(wall_job, reading(), wall.append)
    elapsed_handle, old_wall_handle = timer.handles
    scheduler.rearm_wall_clock(reading(shift))
    assert not elapsed_handle.cancelled
    assert old_wall_handle.cancelled
    assert len(timer.handles) == 3
    assert timer.handles[-1].due == expected_wall_delay
    old_wall_handle.callback()
    assert wall == []
    timer.advance(0)
    assert wall == ([wall_job] if expected_wall_delay == 0 else [])
    timer.advance(10)
    assert elapsed == [elapsed_job]
    timer.advance(30)
    assert wall == [wall_job]
    assert scheduler.pending_jobs == ()


def test_repeated_wall_rearm_stale_arms_cannot_deliver(runtime):
    timer, scheduler = runtime
    delivered = []
    definition = job(10, basis="wall_clock")
    scheduler.register(definition, reading(), delivered.append)
    for now in [5, 15, -5, 15]:
        scheduler.rearm_wall_clock(reading(now))
    for stale in timer.handles[:-1]:
        assert stale.cancelled
        stale.callback()
    assert delivered == []
    timer.advance(0)
    scheduler.rearm_wall_clock(reading(20))
    assert delivered == [definition]
    assert len(timer.handles) == 5


def test_cancel_all_and_stale_callbacks(runtime):
    timer, scheduler = runtime
    delivered = []
    scheduler.register(job(), reading(), delivered.append)
    scheduler.register(job(job_id="other"), reading(), delivered.append)
    scheduler.cancel_all()
    scheduler.cancel_all()
    assert scheduler.pending_jobs == ()
    for handle in timer.handles:
        assert handle.cancelled
        handle.callback()
    timer.advance(20)
    assert delivered == []


def test_delivery_retires_before_owner_can_register_next_arm(runtime):
    timer, scheduler = runtime
    delivered = []

    def callback(definition):
        assert scheduler.pending_jobs == ()
        delivered.append(definition)
        scheduler.register(job(20), reading(10), delivered.append)

    scheduler.register(job(), reading(), callback)
    timer.advance(10)
    assert scheduler.pending_jobs == (job(20),)
    timer.advance(10)
    assert delivered == [job(10), job(20)]


def test_owner_exception_does_not_leave_job_pending(runtime):
    timer, scheduler = runtime

    def callback(_):
        raise RuntimeError("owner failed")

    scheduler.register(job(), reading(), callback)
    with pytest.raises(RuntimeError, match="owner failed"):
        timer.advance(10)
    assert scheduler.pending_jobs == ()
    timer.handles[0].callback()


def test_timer_failure_preserves_previous_registration(runtime):
    timer, scheduler = runtime
    delivered = []
    scheduler.register(job(), reading(), delivered.append)
    timer.fail = True
    with pytest.raises(RuntimeError, match="Timer unavailable"):
        scheduler.register(job(20), reading(), delivered.append)
    assert not timer.handles[0].cancelled
    assert scheduler.pending_jobs == (job(),)
    timer.advance(10)
    assert delivered == [job()]


class UnvalidatedJob(AtJob):
    def __post_init__(self):
        pass


@pytest.mark.parametrize("field,value", [("basis", "wrong"), ("due", "invalid"), ("owner", None)])
def test_invalid_dynamic_job_never_changes_pending_registration(runtime, field, value):
    timer, scheduler = runtime
    delivered = []
    scheduler.register(job(), reading(), delivered.append)
    values = dict(job_id="job", owner="engine", due=instant(20), label="label", basis="elapsed")
    values[field] = value
    with pytest.raises((ValueError, TypeError)):
        scheduler.register(UnvalidatedJob(**values), reading(), delivered.append)
    assert len(timer.handles) == 1
    assert not timer.handles[0].cancelled
    assert scheduler.pending_jobs == (job(),)


@pytest.mark.parametrize("operation", ["job", "callback", "now", "rearm_now"])
def test_invalid_admission_inputs_do_not_arm(runtime, operation):
    timer, scheduler = runtime
    with pytest.raises((TypeError, ValueError)):
        match operation:
            case "job":
                scheduler.register(None, reading(), lambda _: None)
            case "callback":
                scheduler.register(job(), reading(), None)
            case "now":
                scheduler.register(job(), "invalid", lambda _: None)
            case "rearm_now":
                scheduler.rearm_wall_clock("invalid")
    assert timer.handles == []
    assert scheduler.pending_jobs == ()


@settings(max_examples=50)
@given(st.lists(st.tuples(st.booleans(), st.sampled_from(["a", "b"]), st.integers(0, 2))))
def test_property_last_registration_per_owner_key_is_only_delivery(actions):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    expected = {}
    delivered = []
    for revision, (register, owner, job_id) in enumerate(actions):
        key = (owner, str(job_id))
        if register:
            definition = job(1, owner, str(job_id))
            scheduler.register(definition, reading(), lambda _, r=revision: delivered.append(r))
            expected[key] = revision
        else:
            scheduler.cancel(*key)
            expected.pop(key, None)
    timer.advance(1)
    assert sorted(delivered) == sorted(expected.values())
    assert scheduler.pending_jobs == ()
    for handle in timer.handles:
        handle.callback()
    assert sorted(delivered) == sorted(expected.values())


@settings(max_examples=50)
@given(st.integers(-100, 100))
def test_property_wall_correction_preserves_elapsed_countdown(shift):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    scheduler.register(job(10), reading(), delivered.append)
    scheduler.register(job(10, job_id="wall", basis="wall_clock"), reading(), lambda _: None)
    timer.advance(2)
    scheduler.rearm_wall_clock(reading(2 + shift))
    timer.advance(7.5)
    assert delivered == []
    timer.advance(0.5)
    assert delivered == [job(10)]


def test_scheduler_import_resolves_to_active_source_tree():
    assert Path(timing.__file__).resolve().is_relative_to(Path.cwd() / "custom_components")


@settings(max_examples=50)
@given(st.integers(0, 3600))
def test_property_late_delivery_preserves_due_and_delivers_only_once(lateness):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    definition = job(10)
    scheduler.register(definition, reading(), lambda value: delivered.append((value, timer.now)))
    timer.now = 10 + lateness  # Passage of time while HA's loop cannot dispatch.
    timer.drain_ready()
    assert delivered == [(definition, 10 + lateness)]
    assert scheduler.pending_jobs == ()
    timer.drain_ready()
    timer.handles[0].callback()
    assert delivered == [(definition, 10 + lateness)]


@pytest.mark.parametrize("operation", ["replace", "cancel"])
def test_overdue_callback_invalidated_before_delayed_dispatch(operation):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    old, new = [], []
    scheduler.register(job(10), reading(), old.append)
    overdue_handle = timer.handles[-1]
    timer.now = 100
    if operation == "replace":
        scheduler.register(job(110), reading(100), new.append)
    else:
        scheduler.cancel("engine", "job")
    overdue_handle.callback()  # Even a callback already placed in a ready queue.
    timer.drain_ready()
    assert old == [] and new == []
    timer.advance(10)
    assert new == ([job(110)] if operation == "replace" else [])
    assert old == []


def test_burst_of_equal_deadlines_has_no_order_or_duplicate_dependency():
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    for index in range(1000):  # A workload example, not an approved capacity limit.
        scheduler.register(job(10, job_id=str(index)), reading(), delivered.append)
    timer.now = 30
    # Same-deadline callback order is unspecified by asyncio; deliberately reverse it.
    for handle in reversed(timer.handles):
        handle.callback()
    assert len(delivered) == 1000
    assert {value.job_id for value in delivered} == {str(index) for index in range(1000)}
    assert scheduler.pending_jobs == ()
    timer.drain_ready()
    assert len(delivered) == 1000


def test_ca499_regression_due_waits_for_corrected_wall():

    cycle = CycleClock()
    first = cycle.next_cycle(instant(100), 0)
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    scheduler.register(
        job(110, basis="wall_clock"), first.comparison.execution_clock, delivered.append
    )
    timer.advance(1)
    tick = cycle.next_cycle(instant(98), 1_000_000_000)
    scheduler.rearm_wall_clock(tick.comparison.execution_clock)
    assert timer.handles[-1].due - timer.now == 12


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check", "bootstrap"])
def test_ca499_rearm_uses_detection_wall_and_never_repeats(detection):
    cycle = CycleClock(instant(100)) if detection == "bootstrap" else CycleClock()
    initial = (
        cycle.read_execution(instant(100))
        if detection == "bootstrap"
        else cycle.next_cycle(instant(100), 0).comparison.execution_clock
    )
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    definition = job(110, basis="wall_clock")
    scheduler.register(definition, initial, lambda value: delivered.append((value, timer.now)))
    timer.advance(1)
    comparison = (
        cycle.compare(instant(98), 1_000_000_000)
        if detection == "periodic_check"
        else cycle.next_cycle(instant(98), 1_000_000_000).comparison
    )
    assert comparison.requires_wall_clock_rearm
    assert comparison.execution_clock.wall == instant(98)
    assert comparison.execution_clock.cycle_instant == instant(100.000001)
    scheduler.rearm_wall_clock(comparison.execution_clock)
    scheduler.rearm_wall_clock(comparison.execution_clock)
    assert timer.handles[-1].due - timer.now == 12
    assert scheduler.pending_jobs == (definition,)
    for old in timer.handles[:-1]:
        assert old.cancelled
        old.callback()
    timer.advance(11.5)
    assert delivered == []
    timer.advance(0.5)
    assert delivered == [(definition, 13)]
    assert 98 + (delivered[0][1] - 1) == 110  # Corrected wall reaches the civil due.
    timer.handles[-1].callback()
    assert delivered == [(definition, 13)]


@pytest.mark.parametrize("basis,expected_delay", [("wall_clock", 32.000001), ("elapsed", 30)])
def test_ca499_basis_selects_distinct_execution_reference(basis, expected_delay):
    cycle = CycleClock(instant(100))
    tick = cycle.next_cycle(instant(98), 0)
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    scheduler.register(
        job(130.000001, basis=basis), tick.comparison.execution_clock, delivered.append
    )
    assert timer.handles[-1].due == expected_delay
    assert tick.when == instant(100.000001)
    timer.advance(29.5)
    assert delivered == []
    if basis == "elapsed":
        scheduler.rearm_wall_clock(cycle.compare(instant(90), 1_000_000_000).execution_clock)
        assert len(timer.handles) == 1
        timer.advance(0.5)
        assert delivered == [job(130.000001, basis=basis)]


def test_ca499_wall_due_and_history_instant_stay_separate():
    cycle = CycleClock(instant(100))
    tick = cycle.next_cycle(instant(98), 0)
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    definition = job(99, basis="wall_clock")
    scheduler.register(definition, tick.comparison.execution_clock, delivered.append)
    timer.advance(1)
    assert delivered == [definition]
    firing_cycle = cycle.next_cycle(instant(99), 1_000_000_000)
    assert firing_cycle.when == instant(100.000002)
    assert firing_cycle.when != definition.due


@pytest.mark.parametrize("difference", [-0.000001, 0, 0.000001])
def test_ca499_wall_due_boundaries_under_frozen_floor(difference):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    delivered = []
    scheduler.register(
        job(98 + difference, basis="wall_clock"),
        ExecutionClockReading(instant(98), instant(100)),
        delivered.append,
    )
    assert timer.handles[-1].due == max(0, difference)
    assert delivered == []
    timer.advance(max(0, difference))
    assert delivered == [job(98 + difference, basis="wall_clock")]


class UnvalidatedExecutionReading(ExecutionClockReading):
    def __post_init__(self):
        pass


@pytest.mark.parametrize(
    "invalid",
    [
        "one instant",
        UnvalidatedExecutionReading("invalid", instant()),
        UnvalidatedExecutionReading(instant(2), instant(1)),
    ],
)
def test_ca499_invalid_execution_pair_preserves_pending_arms(invalid):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    scheduler.register(job(), reading(), lambda _: None)
    with pytest.raises((TypeError, ValueError)):
        scheduler.register(job(20), invalid, lambda _: None)
    with pytest.raises((TypeError, ValueError)):
        scheduler.rearm_wall_clock(invalid)
    assert len(timer.handles) == 1
    assert not timer.handles[0].cancelled
    assert scheduler.pending_jobs == (job(),)


@settings(max_examples=50)
@given(st.integers(0, 1000), st.integers(1, 1000))
def test_property_ca499_wall_countdown_does_not_depend_on_history_floor(floor_offset, delay):
    timer = FakeTimer()
    scheduler = AtJobScheduler(timer)
    scheduler.register(
        job(98 + delay, basis="wall_clock"),
        ExecutionClockReading(instant(98), instant(98 + floor_offset)),
        lambda _: None,
    )
    assert timer.handles[-1].due == delay
