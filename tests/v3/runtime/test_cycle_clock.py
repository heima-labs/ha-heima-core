"""Layer 0 §3.5 instants and strict discontinuity thresholds, without real clocks."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.runtime import clock
from custom_components.heima.v3.runtime.clock import ClockDiscontinuityDetector, CycleClock

ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)


def instant(seconds=0, microseconds=0):
    return format_instant(ANCHOR + timedelta(seconds=seconds, microseconds=microseconds))


@pytest.mark.parametrize(
    "wall_offset,expected_us,behind", [(-1, 1, True), (0, 1, True), (1, 1_000_000, False)]
)
def test_cycle_floor_before_equal_after(wall_offset, expected_us, behind):
    cycle = CycleClock(instant())
    reading = cycle.next_cycle(instant(wall_offset), 10)
    assert reading.when == instant(microseconds=expected_us)
    assert reading.previous_when == instant()
    assert reading.wall_behind_floor is behind
    assert cycle.previous_instant == reading.when
    with pytest.raises(FrozenInstanceError):
        reading.when = instant()


def test_first_installation_has_no_fabricated_floor():
    cycle = CycleClock()
    assert cycle.previous_instant is None
    reading = cycle.next_cycle(instant(), 0)
    assert reading.when == instant()
    assert reading.previous_when is None
    assert reading.comparison.adjustment_ns is None
    assert reading.wall_behind_floor is False
    assert reading.comparison.wall == instant()


@pytest.mark.parametrize(
    "offset_us,direction",
    [
        (-1_000_001, "backward"),
        (-1_000_000, None),
        (-999_999, None),
        (0, None),
        (600_000_000, None),
    ],
)
def test_bootstrap_backward_threshold_and_forward_downtime(offset_us, direction):
    cycle = CycleClock(instant())
    reading = cycle.next_cycle(instant(microseconds=offset_us), 500)
    assert reading.comparison.discontinuity == direction
    assert reading.comparison.adjustment_ns is None
    assert reading.comparison.requires_wall_clock_rearm is (direction is not None)
    assert reading.when > instant()


@pytest.mark.parametrize(
    "adjustment",
    [-1_000_000_001, -1_000_000_000, -999_999_999, 0, 999_999_999, 1_000_000_000, 1_000_000_001],
)
def test_exact_nanosecond_threshold_both_directions(adjustment):
    detector = ClockDiscontinuityDetector()
    detector.compare(instant(), 0)
    # Wall elapsed is fixed at 2s; monotonic elapsed spans the 1s threshold by 1ns.
    comparison = detector.compare(instant(2), 2_000_000_000 - adjustment)
    expected = (
        "forward"
        if adjustment > 1_000_000_000
        else "backward"
        if adjustment < -1_000_000_000
        else None
    )
    assert comparison.adjustment_ns == adjustment
    assert comparison.discontinuity == expected
    assert comparison.requires_wall_clock_rearm is (expected is not None)
    with pytest.raises(FrozenInstanceError):
        comparison.discontinuity = "other"


def test_slow_hardware_elapsed_time_is_not_a_clock_jump():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    reading = cycle.next_cycle(instant(600), 600_000_000_000)
    assert reading.when == instant(600)
    assert reading.comparison.adjustment_ns == 0
    assert reading.comparison.discontinuity is None


def test_backward_correction_can_leave_wall_ahead_of_previous_cycle():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    reading = cycle.next_cycle(instant(58), 60_000_000_000)
    assert reading.when == instant(58)
    assert not reading.wall_behind_floor
    assert reading.comparison.discontinuity == "backward"
    assert reading.comparison.adjustment_ns == -2_000_000_000


def test_regression_keeps_cycles_increasing_until_wall_exceeds_floor():
    cycle = CycleClock(instant(10))
    readings = [cycle.next_cycle(instant(8), 0)]
    readings.append(cycle.next_cycle(instant(9), 1_000_000_000))
    readings.append(cycle.next_cycle(instant(10), 2_000_000_000))
    readings.append(cycle.next_cycle(instant(11), 3_000_000_000))
    assert [reading.when for reading in readings] == [
        instant(10, 1),
        instant(10, 2),
        instant(10, 3),
        instant(11),
    ]
    assert [reading.wall_behind_floor for reading in readings] == [True, True, True, False]
    assert [reading.comparison.discontinuity for reading in readings] == [
        "backward",
        None,
        None,
        None,
    ]


def test_periodic_comparison_changes_baseline_without_creating_cycle():
    cycle = CycleClock()
    first = cycle.next_cycle(instant(), 0)
    periodic = cycle.compare(instant(70), 60_000_000_000)
    assert periodic.wall == instant(70)
    assert periodic.discontinuity == "forward"
    assert cycle.previous_instant == first.when
    next_cycle = cycle.next_cycle(instant(71), 61_000_000_000)
    assert next_cycle.comparison.adjustment_ns == 0
    assert next_cycle.comparison.discontinuity is None
    assert next_cycle.previous_when == first.when


def test_repeated_identical_readings_still_produce_distinct_cycles():
    cycle = CycleClock()
    readings = [cycle.next_cycle(instant(), 0) for _ in range(4)]
    assert [reading.when for reading in readings] == [instant(microseconds=i) for i in range(4)]
    assert all(reading.comparison.discontinuity is None for reading in readings)


@pytest.mark.parametrize("invalid", [True, False, None, 0.5, "1", -1])
def test_invalid_monotonic_reading_does_not_consume_baseline_or_cycle(invalid):
    cycle = CycleClock()
    cycle.next_cycle(instant(), 5)
    with pytest.raises((TypeError, ValueError)):
        cycle.next_cycle(instant(1), invalid)
    assert cycle.previous_instant == instant()
    valid = cycle.next_cycle(instant(1), 1_000_000_005)
    assert valid.comparison.adjustment_ns == 0


def test_monotonic_regression_and_invalid_wall_leave_state_unchanged():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 100)
    with pytest.raises(ValueError):
        cycle.compare(instant(1), 99)
    with pytest.raises(ValueError):
        cycle.next_cycle("invalid", 1_000_000_100)
    with pytest.raises(ValueError):
        CycleClock("invalid")
    valid = cycle.next_cycle(instant(1), 1_000_000_100)
    assert valid.comparison.adjustment_ns == 0


def test_calendar_floor_overflow_does_not_mutate_detector():
    maximum = "9999-12-31T23:59:59.999999+00:00"
    cycle = CycleClock(maximum)
    with pytest.raises(OverflowError):
        cycle.next_cycle(maximum, 0)
    assert cycle.previous_instant == maximum
    # Calendar exhaustion also rejects an execution-reference read; the floor stays unchanged.
    with pytest.raises(OverflowError):
        cycle.compare(maximum, 100)
    assert cycle.previous_instant == maximum


def test_difference_across_day_boundary_uses_exact_microseconds():
    detector = ClockDiscontinuityDetector()
    detector.compare("2025-12-31T23:59:59.999999+00:00", 0)
    result = detector.compare(instant(), 1000)
    assert result.adjustment_ns == 0
    assert result.discontinuity is None


@settings(max_examples=50)
@given(st.lists(st.integers(-10_000_000, 10_000_000), min_size=1, max_size=50))
def test_property_cycles_are_strictly_increasing_and_bound_wall(readings):
    cycle = CycleClock(instant())
    previous = parse_instant(instant())
    for index, offset in enumerate(readings):
        wall = instant(microseconds=offset)
        reading = cycle.next_cycle(wall, index * 1_000_000)
        when = parse_instant(reading.when)
        assert when > previous
        assert when >= parse_instant(wall)
        if parse_instant(wall) > previous:
            assert reading.when == wall
        else:
            assert when - previous == timedelta(microseconds=1)
        previous = when


@settings(max_examples=50)
@given(st.integers(0, 1_000_000), st.integers(-5_000_000, 5_000_000))
def test_property_clock_adjustment_ignores_shared_elapsed_time(elapsed_us, correction_us):
    detector = ClockDiscontinuityDetector()
    detector.compare(instant(), 0)
    reading = detector.compare(instant(microseconds=elapsed_us + correction_us), elapsed_us * 1000)
    assert reading.adjustment_ns == correction_us * 1000
    expected = (
        "forward"
        if correction_us > 1_000_000
        else "backward"
        if correction_us < -1_000_000
        else None
    )
    assert reading.discontinuity == expected


def test_clock_import_resolves_to_active_source_tree():
    assert Path(clock.__file__).resolve().is_relative_to(Path.cwd() / "custom_components")


def test_ca498_backward_without_freeze_has_exact_gap_and_diagnostic():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    reading = cycle.next_cycle(instant(58), 60_000_000_000)
    comparison = reading.comparison
    assert comparison.detection_point == "cycle_start"
    assert comparison.wall_behind_floor is False
    assert comparison.requires_clock_regression is True
    assert comparison.requires_wall_clock_rearm is True
    assert comparison.gap.start == instant()
    assert comparison.gap.end == instant(58)
    assert comparison.gap.await_floor_recovery is False
    with pytest.raises(FrozenInstanceError):
        comparison.gap.start = instant(1)
    assert comparison.gap.finish(reading) is comparison.gap


def test_ca498_periodic_detection_opens_pending_gap_and_is_not_repeated():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    periodic = cycle.compare(instant(58), 60_000_000_000)
    assert periodic.detection_point == "periodic_check"
    assert periodic.requires_clock_regression is True
    assert periodic.requires_wall_clock_rearm is True
    assert periodic.gap.start == instant()
    assert periodic.gap.end is None
    reading = cycle.next_cycle(instant(59), 61_000_000_000)
    assert reading.comparison.discontinuity is None
    assert reading.comparison.requires_clock_regression is False
    assert reading.comparison.gap is None
    closed = periodic.gap.finish(reading)
    assert closed.start == instant()
    assert closed.end == instant(59)
    assert periodic.gap.end is None  # Immutable boundary intent, no durable acknowledgement.


@pytest.mark.parametrize(
    "wall,mono,expected",
    [
        (-0.4, 100_000_000, True),
        (0, 0, False),
        (0.5, 1_000_000_000, False),
        (1, 1_000_000_000, False),
    ],
)
def test_ca498_small_correction_diagnostic_mcdc(wall, mono, expected):
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    comparison = cycle.next_cycle(instant(wall), mono).comparison
    assert comparison.requires_clock_regression is expected
    assert comparison.discontinuity is None
    assert comparison.requires_wall_clock_rearm is False
    assert comparison.gap is None


def test_ca498_frozen_gap_starts_at_first_frozen_cycle_and_waits_for_recovery():
    cycle = CycleClock(instant(10))
    first = cycle.next_cycle(instant(8), 0)
    gap = first.comparison.gap
    assert first.comparison.bootstrap_offset_ns == -2_000_000_000
    assert gap.start == instant(10, 1)
    assert gap.end is None
    assert gap.finish(first) is gap
    still_frozen = cycle.next_cycle(instant(9), 1_000_000_000)
    assert gap.finish(still_frozen).end is None
    at_floor = cycle.next_cycle(instant(10, 3), 2_000_000_000)
    assert at_floor.wall_behind_floor is False
    assert gap.finish(at_floor).end is None
    recovered = cycle.next_cycle(instant(11), 3_000_000_000)
    assert gap.finish(recovered).end == instant(11)


def test_ca4102_periodic_forward_gap_ends_even_if_next_correction_freezes():
    cycle = CycleClock()
    first = cycle.next_cycle(instant(10), 0)
    periodic = cycle.compare(instant(12), 0)
    assert periodic.discontinuity == "forward"
    assert periodic.gap.await_floor_recovery is False
    # A subsequent correction can put the first detecting-cycle wall below the floor.
    frozen = cycle.next_cycle(instant(9), 1_000_000_000)
    pending = periodic.gap.finish(frozen)
    assert pending.start == first.when
    assert pending.end == frozen.when
    assert pending.await_floor_recovery is False
    assert frozen.comparison.gap.await_floor_recovery is True
    assert frozen.comparison.gap.end is None
    recovered = cycle.next_cycle(instant(11), 2_000_000_000)
    assert pending.finish(recovered) is pending
    assert frozen.comparison.gap.finish(recovered).end == instant(11)


def test_ca498_periodic_small_regression_without_freeze_has_no_diagnostic():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    periodic = cycle.compare(instant(59.5), 60_000_000_000)
    assert periodic.adjustment_ns == -500_000_000
    assert periodic.requires_clock_regression is False
    assert periodic.gap is None


def test_ca498_positive_discontinuity_has_no_regression_diagnostic():
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    comparison = cycle.next_cycle(instant(600), 0).comparison
    assert comparison.requires_clock_regression is False
    assert comparison.gap.start == instant()
    assert comparison.gap.end == instant(600)


@settings(max_examples=50)
@given(st.integers(3, 1000), st.integers(2, 100))
def test_property_ca498_backward_above_floor_closes_on_adjacent_cycles(elapsed, correction):
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    elapsed += correction
    reading = cycle.next_cycle(instant(elapsed - correction), elapsed * 1_000_000_000)
    assert reading.comparison.gap.start == instant()
    assert reading.comparison.gap.end == reading.when
    assert reading.comparison.requires_clock_regression is True


def test_ca498_empty_bootstrap_periodic_observation_is_metadata_only():
    cycle = CycleClock()
    comparison = cycle.compare(instant(), 0)
    assert comparison.requires_clock_regression is False
    assert comparison.wall_behind_floor is False
    assert comparison.gap is None
    assert cycle.previous_instant is None


@pytest.mark.parametrize("offset,behind", [(-1, True), (0, True), (1, False), (2, False)])
def test_ca498_periodic_floor_metadata_at_microsecond_boundaries(offset, behind):
    cycle = CycleClock()
    cycle.next_cycle(instant(), 0)
    comparison = cycle.compare(instant(microseconds=offset), 0)
    assert comparison.wall_behind_floor is behind
    assert comparison.detection_point == "periodic_check"


def test_ca498_periodic_backward_below_floor_waits_and_does_not_repeat():
    cycle = CycleClock()
    cycle.next_cycle(instant(10), 0)
    comparison = cycle.compare(instant(9), 1_000_000_000)
    assert comparison.wall_behind_floor is True
    assert comparison.requires_clock_regression is True
    assert comparison.gap.start == instant(10)
    assert comparison.gap.await_floor_recovery is True
    tick = cycle.next_cycle(instant(9.1), 1_100_000_000)
    assert tick.comparison.discontinuity is None
    pending = comparison.gap.finish(tick)
    assert pending.end is None
    recovered = cycle.next_cycle(instant(11), 3_000_000_000)
    assert pending.finish(recovered).end == instant(11)


def test_review_forward_jump_while_still_frozen_uses_adjacent_cycle_bounds():
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(90), 0)
    original_gap = first.comparison.gap
    second = cycle.next_cycle(instant(93), 1_000_000_000)
    assert second.wall_behind_floor is True
    assert second.comparison.discontinuity == "forward"
    assert second.comparison.requires_clock_regression is False
    assert second.comparison.gap.start == first.when
    assert second.comparison.gap.end == second.when
    assert second.comparison.gap.await_floor_recovery is False
    # The earlier backward gap remains open: closing this new gap does not close it.
    assert original_gap.finish(second).end is None


@settings(max_examples=50)
@given(st.integers(2, 8), st.integers(100, 1000))
def test_property_review_forward_jump_gap_bounds_do_not_depend_on_freeze(correction, floor):
    cycle = CycleClock(instant(floor))
    first = cycle.next_cycle(instant(floor - 10), 0)
    second = cycle.next_cycle(instant(floor - 9 + correction), 1_000_000_000)
    assert second.comparison.discontinuity == "forward"
    assert second.wall_behind_floor is True
    assert second.comparison.gap.start == first.when
    assert second.comparison.gap.end == second.when


def test_execution_reading_validation_and_immutability():
    from custom_components.heima.v3.runtime.clock import ExecutionClockReading

    value = ExecutionClockReading(instant(98), instant(100))
    assert value.wall == instant(98)
    assert value.cycle_instant == instant(100)
    with pytest.raises(FrozenInstanceError):
        value.wall = instant()
    for wall, cycle_instant in [
        ("invalid", instant()),
        (instant(), "invalid"),
        (instant(100), instant(98)),
    ]:
        with pytest.raises(ValueError):
            ExecutionClockReading(wall, cycle_instant)


def test_execution_read_between_cycles_does_not_consume_clock_state():
    cycle = CycleClock(instant(100))
    first = cycle.read_execution(instant(98))
    second = cycle.read_execution(instant(98))
    assert first == second
    assert first.wall == instant(98)
    assert first.cycle_instant == instant(100.000001)
    assert cycle.previous_instant == instant(100)
    comparison = cycle.compare(instant(98), 0)
    assert comparison.bootstrap_offset_ns == -2_000_000_000
    assert comparison.execution_clock == first
    assert cycle.previous_instant == instant(100)
    tick = cycle.next_cycle(instant(98), 0)
    assert tick.comparison.adjustment_ns == 0
    assert tick.comparison.execution_clock == first
    assert tick.when == first.cycle_instant


@settings(max_examples=50)
@given(st.integers(-1000, 1000))
def test_property_execution_reading_preserves_wall_and_applies_floor_without_cycle(offset):
    cycle = CycleClock(instant())
    reading = cycle.read_execution(instant(microseconds=offset))
    assert reading.wall == instant(microseconds=offset)
    assert reading.cycle_instant >= reading.wall
    if offset <= 0:
        assert reading.cycle_instant == instant(microseconds=1)
    else:
        assert reading.cycle_instant == reading.wall
    assert cycle.previous_instant == instant()


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
@pytest.mark.parametrize(
    "baseline,wall,mono,mode,direction",
    [
        (90, 94, 1_000_000_000, False, "forward"),
        (100, 104, 1_000_000_000, False, "forward"),
        (90, 86, 1_000_000_000, True, "backward"),
        (100, 105, 10_000_000_000, False, "backward"),
    ],
)
def test_ca4102_gap_mode_decision_table_and_mcdc(detection, baseline, wall, mono, mode, direction):
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(baseline), 0)
    if detection == "cycle_start":
        tick = cycle.next_cycle(instant(wall), mono)
        comparison = tick.comparison
    else:
        comparison = cycle.compare(instant(wall), mono)
        tick = cycle.next_cycle(instant(wall), mono)
        assert tick.comparison.discontinuity is None
    gap = comparison.gap
    assert comparison.discontinuity == direction
    assert comparison.detection_point == detection
    assert gap.await_floor_recovery is mode
    finished = gap.finish(tick)
    assert finished.await_floor_recovery is mode
    assert finished.end == (None if mode else tick.when)
    if mode:
        assert gap.start == (tick.when if detection == "cycle_start" else first.when)
    else:
        assert gap.start == first.when
    recovered = cycle.next_cycle(instant(110), mono + 1_000_000_000)
    assert finished.finish(recovered).end == (recovered.when if mode else tick.when)


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
def test_ca4102_exact_reproducer_and_independent_bootstrap_gap(detection):
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(90), 0)
    original = first.comparison.gap
    if detection == "cycle_start":
        tick = cycle.next_cycle(instant(94), 1_000_000_000)
        gap = tick.comparison.gap
    else:
        comparison = cycle.compare(instant(94), 1_000_000_000)
        assert comparison.gap.await_floor_recovery is False
        tick = cycle.next_cycle(instant(95), 2_000_000_000)
        assert tick.comparison.discontinuity is None
        gap = comparison.gap.finish(tick)
    assert gap.start == instant(100, 1)
    assert gap.end == instant(100, 2)
    assert gap.await_floor_recovery is False
    assert original.finish(tick).end is None
    recovered = cycle.next_cycle(instant(100.5), 3_000_000_000)
    assert original.finish(recovered).end == instant(100.5)
    assert gap.finish(recovered) is gap
    assert original.end is None  # Neither an updated intent nor a durable acknowledgement.


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
def test_ca4102_forward_recovery_closes_both_independent_gaps(detection):
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(90), 0)
    if detection == "cycle_start":
        tick = cycle.next_cycle(instant(101), 1_000_000_000)
        forward = tick.comparison.gap
    else:
        comparison = cycle.compare(instant(101), 1_000_000_000)
        tick = cycle.next_cycle(instant(101), 1_000_000_000)
        forward = comparison.gap.finish(tick)
    old = first.comparison.gap.finish(tick)
    assert old.start == instant(100, 1)
    assert forward.start == first.when
    assert old.end == forward.end == instant(101)
    assert old.await_floor_recovery is True
    assert forward.await_floor_recovery is False
    assert old is not forward


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
def test_ca4102_further_backward_gap_does_not_extend_earlier_gap(detection):
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(90), 0)
    old = first.comparison.gap
    if detection == "cycle_start":
        tick = cycle.next_cycle(instant(86), 1_000_000_000)
        new = tick.comparison.gap
    else:
        comparison = cycle.compare(instant(86), 1_000_000_000)
        tick = cycle.next_cycle(instant(87), 2_000_000_000)
        new = comparison.gap
    assert new.await_floor_recovery is True
    assert new.start == (tick.when if detection == "cycle_start" else first.when)
    assert old.finish(tick).end is None
    assert new.finish(tick).end is None
    recovered = cycle.next_cycle(instant(101), 3_000_000_000)
    assert old.finish(recovered).end == new.finish(recovered).end == instant(101)
    assert old.start == first.when
    assert old.end is new.end is None


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
def test_ca4102_small_backward_while_frozen_is_diagnostic_only(detection):
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(90), 0)
    if detection == "cycle_start":
        comparison = cycle.next_cycle(instant(90.5), 1_000_000_000).comparison
    else:
        comparison = cycle.compare(instant(90.5), 1_000_000_000)
    assert comparison.adjustment_ns == -500_000_000
    assert comparison.requires_clock_regression is True
    assert comparison.requires_wall_clock_rearm is False
    assert comparison.gap is None
    assert first.comparison.gap.end is None


def test_ca4102_backward_ahead_gap_is_not_promoted_by_small_regression():
    cycle = CycleClock()
    first = cycle.next_cycle(instant(100), 0)
    comparison = cycle.compare(instant(100, 1), 2_000_000_000)
    assert comparison.discontinuity == "backward"
    assert comparison.wall_behind_floor is False
    assert comparison.gap.await_floor_recovery is False
    tick = cycle.next_cycle(instant(99.5, 1), 2_000_000_000)
    assert tick.comparison.adjustment_ns == -500_000_000
    assert tick.comparison.discontinuity is None
    assert tick.comparison.requires_clock_regression is True
    finished = comparison.gap.finish(tick)
    assert finished.start == first.when
    assert finished.end == tick.when == instant(100, 1)
    assert finished.await_floor_recovery is False


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
@pytest.mark.parametrize("direction,baseline", [("forward", 90), ("backward", 110)])
@pytest.mark.parametrize("floor_offset,behind", [(-1, True), (0, False), (1, False)])
def test_ca4102_open_floor_boundaries(detection, direction, baseline, floor_offset, behind):
    cycle = CycleClock(instant(100))
    cycle.compare(instant(baseline), 0)
    wall = instant(100, 1 + floor_offset)
    if detection == "cycle_start":
        tick = cycle.next_cycle(wall, 1_000_000_000)
        comparison = tick.comparison
    else:
        comparison = cycle.compare(wall, 1_000_000_000)
        tick = cycle.next_cycle(wall, 1_000_000_000)
    assert comparison.discontinuity == direction
    assert comparison.wall_behind_floor is behind
    expected_mode = direction == "backward" and behind
    assert comparison.gap.await_floor_recovery is expected_mode
    assert comparison.gap.finish(tick).end == (None if expected_mode else tick.when)


@pytest.mark.parametrize("detection", ["cycle_start", "periodic_check"])
@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("magnitude", [999_999, 1_000_000, 1_000_001])
def test_ca4102_discontinuity_threshold_boundaries(detection, direction, magnitude):
    cycle = CycleClock()
    cycle.next_cycle(instant(100), 0)
    wall = instant(101, direction * magnitude)
    comparison = (
        cycle.next_cycle(wall, 1_000_000_000).comparison
        if detection == "cycle_start"
        else cycle.compare(wall, 1_000_000_000)
    )
    assert comparison.adjustment_ns == direction * magnitude * 1000
    assert (comparison.gap is not None) is (magnitude > 1_000_000)
    assert comparison.discontinuity == (
        ("backward" if direction < 0 else "forward") if magnitude > 1_000_000 else None
    )


@pytest.mark.parametrize("floor_offset", [-1, 0, 1])
def test_ca4102_frozen_gap_finish_requires_wall_strictly_above_floor(floor_offset):
    cycle = CycleClock(instant(100))
    first = cycle.next_cycle(instant(90), 0)
    tick = cycle.next_cycle(instant(100, 2 + floor_offset), 1_000_000_000)
    finished = first.comparison.gap.finish(tick)
    assert finished.await_floor_recovery is True
    assert finished.end == (tick.when if floor_offset > 0 else None)


@settings(max_examples=100)
@given(st.lists(st.integers(-6_000_000, 6_000_000), min_size=1, max_size=35))
def test_property_ca4102_gap_ends_independent_of_detection_path(corrections):
    direct = CycleClock(instant(100))
    periodic = CycleClock(instant(100))
    initial_direct = direct.next_cycle(instant(90), 0)
    initial_periodic = periodic.next_cycle(instant(90), 0)
    gaps = [(initial_direct.comparison.gap, initial_periodic.comparison.gap)]
    wall_us = 90_000_000
    for index, correction in enumerate(corrections, 1):
        wall_us += 1_000_000 + correction
        wall = instant(microseconds=wall_us)
        mono = index * 1_000_000_000
        a = direct.next_cycle(wall, mono)
        comparison = periodic.compare(wall, mono)
        b = periodic.next_cycle(wall, mono)
        assert a.when == b.when
        assert a.comparison.discontinuity == comparison.discontinuity
        assert b.comparison.discontinuity is None
        if a.comparison.gap is not None:
            assert comparison.gap is not None
            gaps.append((a.comparison.gap, comparison.gap))
        updated = []
        for left, right in gaps:
            finished_left, finished_right = left.finish(a), right.finish(b)
            assert finished_left.await_floor_recovery is left.await_floor_recovery
            assert finished_right.await_floor_recovery is right.await_floor_recovery
            assert finished_left.await_floor_recovery is finished_right.await_floor_recovery
            assert finished_left.end == finished_right.end
            updated.append((finished_left, finished_right))
        gaps = updated
    recovery = instant(microseconds=max(wall_us, 100_000_000) + 100_000_000)
    a = direct.next_cycle(recovery, (len(corrections) + 1) * 1_000_000_000)
    b = periodic.next_cycle(recovery, (len(corrections) + 1) * 1_000_000_000)
    for left, right in gaps:
        assert left.finish(a).end == right.finish(b).end
        assert left.finish(a).end is not None


def test_ca4102_first_cycle_end_excludes_the_start_cycle_itself():
    cycle = CycleClock()
    first = cycle.next_cycle(instant(100), 0)
    comparison = cycle.compare(instant(104), 1_000_000_000)
    gap = comparison.gap
    assert gap.await_floor_recovery is False
    assert gap.start == first.when
    assert gap.finish(first) is gap
    later = cycle.next_cycle(instant(105), 2_000_000_000)
    assert gap.finish(later).end == instant(105)
