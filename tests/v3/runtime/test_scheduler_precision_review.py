"""Review regressions: canonical duration must survive float transport conservatively."""

from datetime import UTC, datetime, timedelta
from fractions import Fraction
from math import inf, nextafter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import format_instant
from custom_components.heima.v3.contracts.timing import AtJob
from custom_components.heima.v3.runtime.clock import ExecutionClockReading
from custom_components.heima.v3.runtime.timing import AtJobScheduler


class Timer:
    def __init__(self):
        self.delay = None

    def call_later(self, seconds, callback):
        self.delay = seconds
        return Handle()


class Handle:
    def cancel(self):
        pass


@pytest.mark.parametrize("basis", ["elapsed", "wall_clock"])
@pytest.mark.parametrize(
    "seconds,microseconds", [(0, 1), (0, 100000), (1, 1), (2**20, 1), (2**35, 1)]
)
def test_countdown_float_never_precedes_canonical_difference(basis, seconds, microseconds):
    anchor = datetime(2026, 1, 1, tzinfo=UTC)
    now = format_instant(anchor)
    due = format_instant(anchor + timedelta(seconds=seconds, microseconds=microseconds))
    job = AtJob("id", "owner", due, "label", basis)
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    scheduler.register(job, ExecutionClockReading(now, now), lambda job: None)
    exact = Fraction(seconds) + Fraction(microseconds, 1000000)
    assert Fraction.from_float(timer.delay) >= exact
    assert Fraction.from_float(nextafter(timer.delay, -inf)) < exact
    assert scheduler.pending_jobs == (job,)
    if basis == "wall_clock":
        assert scheduler.rearm_wall_clock(ExecutionClockReading(now, now)) == ()
        assert Fraction.from_float(timer.delay) >= exact


@given(seconds=st.integers(0, 100000000000), microseconds=st.integers(1, 999999))
def test_countdown_is_first_representable_float_at_or_after_exact_duration(seconds, microseconds):
    anchor = datetime(2026, 1, 1, tzinfo=UTC)
    now = format_instant(anchor)
    due = format_instant(anchor + timedelta(seconds=seconds, microseconds=microseconds))
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    scheduler.register(
        AtJob("id", "owner", due, "label", "elapsed"),
        ExecutionClockReading(now, now),
        lambda job: None,
    )
    exact = Fraction(seconds) + Fraction(microseconds, 1000000)
    assert Fraction.from_float(timer.delay) >= exact
    assert Fraction.from_float(nextafter(timer.delay, -inf)) < exact
