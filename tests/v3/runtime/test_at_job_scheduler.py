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
from custom_components.heima.v3.runtime.timing import AtJobScheduler

ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)


def instant(seconds=0):
    return format_instant(ANCHOR + timedelta(seconds=seconds))


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
    scheduler.register(definition, instant(), delivered.append)
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
    scheduler.register(job(10), instant(), old.append)
    original = timer.handles[-1]
    timer.advance(1)
    replacement = job(20)
    scheduler.register(replacement, instant(1), new.append)
    assert original.cancelled
    assert scheduler.pending_jobs == (replacement,)
    original.callback()  # Cancellation can race with a ready callback.
    assert old == [] and new == []
    timer.advance(19)
    assert new == [replacement] and old == []


def test_owner_scopes_replace_and_cancel_keys(runtime):
    timer, scheduler = runtime
    first, second, other_id = [], [], []
    scheduler.register(job(owner="first"), instant(), first.append)
    scheduler.register(job(owner="second"), instant(), second.append)
    scheduler.register(job(owner="first", job_id="other"), instant(), other_id.append)
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
    scheduler.register(elapsed_job, instant(), elapsed.append)
    scheduler.register(wall_job, instant(), wall.append)
    elapsed_handle, old_wall_handle = timer.handles
    scheduler.rearm_wall_clock(instant(shift))
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
    scheduler.register(definition, instant(), delivered.append)
    for now in [5, 15, -5, 15]:
        scheduler.rearm_wall_clock(instant(now))
    for stale in timer.handles[:-1]:
        assert stale.cancelled
        stale.callback()
    assert delivered == []
    timer.advance(0)
    scheduler.rearm_wall_clock(instant(20))
    assert delivered == [definition]
    assert len(timer.handles) == 5


def test_cancel_all_and_stale_callbacks(runtime):
    timer, scheduler = runtime
    delivered = []
    scheduler.register(job(), instant(), delivered.append)
    scheduler.register(job(job_id="other"), instant(), delivered.append)
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
        scheduler.register(job(20), instant(10), delivered.append)

    scheduler.register(job(), instant(), callback)
    timer.advance(10)
    assert scheduler.pending_jobs == (job(20),)
    timer.advance(10)
    assert delivered == [job(10), job(20)]


def test_owner_exception_does_not_leave_job_pending(runtime):
    timer, scheduler = runtime

    def callback(_):
        raise RuntimeError("owner failed")

    scheduler.register(job(), instant(), callback)
    with pytest.raises(RuntimeError, match="owner failed"):
        timer.advance(10)
    assert scheduler.pending_jobs == ()
    timer.handles[0].callback()


def test_timer_failure_preserves_previous_registration(runtime):
    timer, scheduler = runtime
    delivered = []
    scheduler.register(job(), instant(), delivered.append)
    timer.fail = True
    with pytest.raises(RuntimeError, match="Timer unavailable"):
        scheduler.register(job(20), instant(), delivered.append)
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
    scheduler.register(job(), instant(), delivered.append)
    values = dict(job_id="job", owner="engine", due=instant(20), label="label", basis="elapsed")
    values[field] = value
    with pytest.raises((ValueError, TypeError)):
        scheduler.register(UnvalidatedJob(**values), instant(), delivered.append)
    assert len(timer.handles) == 1
    assert not timer.handles[0].cancelled
    assert scheduler.pending_jobs == (job(),)


@pytest.mark.parametrize("operation", ["job", "callback", "now", "rearm_now"])
def test_invalid_admission_inputs_do_not_arm(runtime, operation):
    timer, scheduler = runtime
    with pytest.raises((TypeError, ValueError)):
        match operation:
            case "job":
                scheduler.register(None, instant(), lambda _: None)
            case "callback":
                scheduler.register(job(), instant(), None)
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
            scheduler.register(definition, instant(), lambda _, r=revision: delivered.append(r))
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
    scheduler.register(job(10), instant(), delivered.append)
    scheduler.register(job(10, job_id="wall", basis="wall_clock"), instant(), lambda _: None)
    timer.advance(2)
    scheduler.rearm_wall_clock(instant(2 + shift))
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
    scheduler.register(definition, instant(), lambda value: delivered.append((value, timer.now)))
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
    scheduler.register(job(10), instant(), old.append)
    overdue_handle = timer.handles[-1]
    timer.now = 100
    if operation == "replace":
        scheduler.register(job(110), instant(100), new.append)
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
        scheduler.register(job(10, job_id=str(index)), instant(), delivered.append)
    timer.now = 30
    # Same-deadline callback order is unspecified by asyncio; deliberately reverse it.
    for handle in reversed(timer.handles):
        handle.callback()
    assert len(delivered) == 1000
    assert {value.job_id for value in delivered} == {str(index) for index in range(1000)}
    assert scheduler.pending_jobs == ()
    timer.drain_ready()
    assert len(delivered) == 1000
