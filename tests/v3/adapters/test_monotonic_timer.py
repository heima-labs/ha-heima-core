"""Asyncio minimum deadlines, coarse clocks, lifecycle and actual-loop wiring."""

import asyncio
import weakref
from dataclasses import dataclass
from fractions import Fraction
from math import inf, nan, nextafter
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.adapters.ha import monotonic_timer
from custom_components.heima.v3.adapters.ha.monotonic_timer import AsyncioMonotonicTimer
from custom_components.heima.v3.contracts.instants import validate_instant
from custom_components.heima.v3.contracts.timing import AtJob
from custom_components.heima.v3.runtime.timing import AtJobScheduler


@dataclass
class Scheduled:
    when: float
    callback: object
    cancelled: bool = False

    def cancel(self):
        self.cancelled = True


class Loop:
    def __init__(self, now=100.0):
        self.now = now
        self.scheduled = []
        self.fail = False

    def time(self):
        return self.now

    def call_at(self, when, callback):
        if self.fail:
            raise RuntimeError("loop closing")
        entry = Scheduled(when, callback)
        self.scheduled.append(entry)
        return entry


@pytest.mark.parametrize("resolution", [1e-9, 0.001, 1.0])
def test_early_wake_yields_past_resolution_horizon(resolution):
    loop = Loop()
    delivered = []
    timer = AsyncioMonotonicTimer(loop, clock_resolution=resolution)
    timer.call_later(0.25, lambda: delivered.append(loop.now))
    assert delivered == []
    first = loop.scheduled[0]
    loop.now = nextafter(first.when, -inf)
    first.callback()
    assert delivered == []
    assert len(loop.scheduled) == 2
    assert loop.scheduled[-1].when > loop.now + resolution
    loop.now = loop.scheduled[-1].when
    loop.scheduled[-1].callback()
    assert delivered == [loop.now]
    loop.scheduled[-1].callback()
    assert delivered == [loop.now]


@pytest.mark.parametrize("delay", [0, -0.0, 5e-324, 0.5, 1])
def test_zero_tiny_and_exact_delay_boundaries(delay):
    loop = Loop()
    delivered = []
    timer = AsyncioMonotonicTimer(loop, clock_resolution=0.001)
    timer.call_later(delay, lambda: delivered.append(loop.now))
    assert delivered == []
    exact = Fraction(100) + Fraction(delay)
    when = loop.scheduled[0].when
    assert Fraction(when) >= exact
    if delay in (0, 0.5, 1):
        assert when == 100 + delay  # No extra resolution/ULP added to exact sums.
    if delay == 5e-324:
        assert when > 100
        loop.scheduled[0].callback()
        assert delivered == []
    loop.now = loop.scheduled[-1].when
    loop.scheduled[-1].callback()
    assert delivered == [loop.now]


@pytest.mark.parametrize("offset", [0, 1, 3600])
def test_at_or_after_deadline_delivers_once_without_rearm(offset):
    loop = Loop()
    delivered = []
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    timer.call_later(10, lambda: delivered.append(loop.now))
    loop.now = 110 + offset
    loop.scheduled[0].callback()
    loop.scheduled[0].callback()
    assert delivered == [110 + offset]
    assert len(loop.scheduled) == 1


@pytest.mark.parametrize("early_wake", [False, True])
def test_cancel_releases_latest_handle_and_blocks_ready_callback(early_wake):
    loop = Loop()
    delivered = []
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    handle = timer.call_later(10, lambda: delivered.append(loop.now))
    if early_wake:
        loop.now = 109.5
        loop.scheduled[0].callback()
    handle.cancel()
    handle.cancel()
    assert loop.scheduled[-1].cancelled
    loop.now = 200
    for entry in loop.scheduled:
        entry.callback()
    assert delivered == []


@pytest.mark.parametrize("terminal", ["cancel", "deliver"])
def test_terminal_timer_releases_owner_callback(terminal):
    class Owner:
        def callback(self):
            pass

    loop = Loop()
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    owner = Owner()
    reference = weakref.ref(owner)
    handle = timer.call_later(10, owner.callback)
    del owner
    assert reference() is not None
    if terminal == "cancel":
        handle.cancel()
    else:
        loop.now = 110
        loop.scheduled[0].callback()
    assert reference() is None


def test_callback_exception_consumes_timer():
    loop = Loop()
    calls = []

    def fail():
        calls.append(1)
        raise RuntimeError("owner failed")

    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    handle = timer.call_later(10, fail)
    loop.now = 110
    with pytest.raises(RuntimeError, match="owner failed"):
        loop.scheduled[0].callback()
    loop.scheduled[0].callback()
    handle.cancel()
    assert calls == [1]


@pytest.mark.parametrize("delay", [True, False, None, "1", -5e-324, -1, nan, inf, -inf, 10**400])
def test_invalid_delay_never_schedules(delay):
    loop = Loop()
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    with pytest.raises((TypeError, ValueError)):
        timer.call_later(delay, lambda: None)
    assert loop.scheduled == []


@pytest.mark.parametrize("resolution", [True, 0, -1, nan, inf, "1"])
def test_invalid_resolution_rejected(resolution):
    loop = Loop()
    with pytest.raises((TypeError, ValueError)):
        AsyncioMonotonicTimer(loop, clock_resolution=resolution)
    assert loop.scheduled == []


def test_clock_metadata_is_read_once_and_zero_is_not_a_default(monkeypatch):
    reads = []

    def clock_info(name):
        reads.append(name)
        return SimpleNamespace(resolution=0.001)

    monkeypatch.setattr(monotonic_timer, "get_clock_info", clock_info)
    loop = Loop()
    timer = AsyncioMonotonicTimer(loop)
    timer.call_later(0, lambda: None)
    timer.call_later(10, lambda: None)
    assert reads == ["monotonic"]
    with pytest.raises(ValueError):
        AsyncioMonotonicTimer(loop, clock_resolution=0)
    assert reads == ["monotonic"]


def test_callback_and_unrepresentable_deadline_rejected_before_scheduling():
    loop = Loop()
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    with pytest.raises(TypeError):
        timer.call_later(1, None)
    loop.now = 1.7976931348623157e308
    for delay in [5e-324, loop.now]:
        with pytest.raises(ValueError):
            timer.call_later(delay, lambda: None)
    assert loop.scheduled == []


def test_scheduling_failure_has_no_backend_registration():
    loop = Loop()
    loop.fail = True
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    with pytest.raises(RuntimeError, match="loop closing"):
        timer.call_later(1, lambda: None)
    assert loop.scheduled == []


@settings(max_examples=100)
@given(
    st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_property_deadline_is_smallest_float_not_before_exact_sum(origin, delay):
    loop = Loop(origin)
    timer = AsyncioMonotonicTimer(loop, clock_resolution=0.001)
    timer.call_later(delay, lambda: None)
    when = loop.scheduled[0].when
    exact = Fraction(origin) + Fraction(delay)
    assert Fraction(when) >= exact
    assert Fraction(nextafter(when, -inf)) < exact


@settings(max_examples=50)
@given(st.integers(1, 100), st.integers(1, 100), st.booleans())
def test_property_early_wakeup_and_cancel_preserve_single_delivery(delay, lateness, cancel):
    loop = Loop()
    timer = AsyncioMonotonicTimer(loop, clock_resolution=1)
    delivered = []
    handle = timer.call_later(delay, lambda: delivered.append(loop.now))
    deadline = loop.scheduled[0].when
    loop.now = nextafter(deadline, -inf)
    loop.scheduled[0].callback()
    assert delivered == []
    if cancel:
        handle.cancel()
    loop.now = deadline + lateness
    for entry in tuple(loop.scheduled):
        entry.callback()
    assert delivered == ([] if cancel else [loop.now])


def test_scheduler_and_guarded_timer_replace_after_early_wakeup():
    loop = Loop()
    scheduler = AtJobScheduler(AsyncioMonotonicTimer(loop, clock_resolution=1))
    now = validate_instant("2026-01-01T00:00:00.000000+00:00")
    due = validate_instant("2026-01-01T00:00:10.000000+00:00")
    job = AtJob("job", "engine", due, "label", "elapsed")
    delivered = []
    scheduler.register(job, now, delivered.append)
    loop.now = 109.5
    loop.scheduled[0].callback()
    previous_retry = loop.scheduled[-1]
    scheduler.register(job, now, delivered.append)
    assert previous_retry.cancelled
    loop.now = loop.scheduled[-1].when
    for entry in tuple(loop.scheduled):
        entry.callback()
    assert delivered == [job]
    assert scheduler.pending_jobs == ()


@pytest.mark.parametrize("delay", [0, 0.001])
@pytest.mark.asyncio
async def test_real_asyncio_loop_deferred_and_minimum_deadline(delay):
    loop = asyncio.get_running_loop()
    delivered = loop.create_future()
    timer = AsyncioMonotonicTimer(loop)
    origin = loop.time()
    timer.call_later(delay, lambda: delivered.set_result(loop.time()))
    assert not delivered.done()
    async with asyncio.timeout(10):  # Test watchdog, not a runtime latency requirement.
        when = await delivered
    assert when >= origin + delay


def test_adapter_import_resolves_to_active_source_tree():
    assert Path(monotonic_timer.__file__).resolve().is_relative_to(Path.cwd() / "custom_components")
