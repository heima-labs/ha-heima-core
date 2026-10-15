"""History endpoint tables, discrete boundaries and independent set oracle."""

from dataclasses import FrozenInstanceError
from datetime import timedelta
from itertools import product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.history_intervals import (
    HistoryInterval,
    intersect_history_intervals,
)
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant

ANCHOR = "2026-10-15T12:00:00.000000+00:00"


def instant(us):
    return format_instant(parse_instant(ANCHOR) + timedelta(microseconds=us))


def interval(start, end, left=True, right=True):
    return HistoryInterval(instant(start), instant(end), left, right)


@pytest.mark.parametrize("left_end,right_start", list(product([False, True], repeat=2)))
def test_touching_boundary_requires_both_inclusions(left_end, right_start):
    result = intersect_history_intervals(
        interval(0, 1, True, left_end), interval(1, 2, right_start, True)
    )
    assert result == (interval(1, 1) if left_end and right_start else None)


@pytest.mark.parametrize("a,b", list(product([False, True], repeat=2)))
def test_equal_start_inclusion_is_independent_conjunction(a, b):
    result = intersect_history_intervals(interval(0, 10, a, True), interval(0, 5, b, True))
    assert result == interval(0, 5, a and b, True)


@pytest.mark.parametrize("a,b", list(product([False, True], repeat=2)))
def test_equal_end_inclusion_is_independent_conjunction(a, b):
    result = intersect_history_intervals(interval(0, 10, True, a), interval(5, 10, True, b))
    assert result == interval(5, 10, True, a and b)


@pytest.mark.parametrize(
    "width,left,right,empty",
    [
        (0, True, True, False),
        (0, False, True, True),
        (0, True, False, True),
        (0, False, False, True),
        (1, False, False, True),
        (1, False, True, False),
        (1, True, False, False),
        (2, False, False, False),
    ],
)
def test_microsecond_grid_empty_boundary(width, left, right, empty):
    span = interval(0, width, left, right)
    assert span.empty is empty
    assert intersect_history_intervals(span, span) == (None if empty else span)


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (interval(0, 5), interval(6, 10), None),
        (interval(6, 10), interval(0, 5), None),
        (interval(0, 10), interval(2, 5, False, True), interval(2, 5, False, True)),
        (interval(2, 5, True, False), interval(0, 10), interval(2, 5, True, False)),
        (interval(0, 5), interval(2, 10, False, True), interval(2, 5, False, True)),
    ],
)
def test_clipping_and_disjoint_table(left, right, expected):
    assert intersect_history_intervals(left, right) == expected


def test_extreme_calendar_points_do_not_require_overflowing_successor():
    for value in ("0001-01-01T00:00:00.000000+00:00", "9999-12-31T23:59:59.999999+00:00"):
        point = HistoryInterval(value, value, True, True)
        assert not point.empty
        assert intersect_history_intervals(point, point) == point
        excluded = HistoryInterval(value, value, False, False)
        assert excluded.empty
        assert intersect_history_intervals(point, excluded) is None


@pytest.mark.parametrize(
    "args,error",
    [
        ((instant(1), instant(0), True, True), ValueError),
        (("2026-10-15T12:00:00Z", instant(1), True, True), ValueError),
        ((instant(0), None, True, True), TypeError),
        ((instant(0), instant(1), 1, True), TypeError),
        ((instant(0), instant(1), True, None), TypeError),
    ],
)
def test_invalid_shape_rejected_without_normalizing(args, error):
    with pytest.raises(error):
        HistoryInterval(*args)


def test_immutability_and_independent_intersection_validation():
    valid = interval(0, 10)
    with pytest.raises(FrozenInstanceError):
        valid.include_end = False
    with pytest.raises(TypeError):
        intersect_history_intervals(None, valid)
    invalid = object.__new__(HistoryInterval)
    for field, value in (
        ("start", instant(10)),
        ("end", instant(0)),
        ("include_start", True),
        ("include_end", True),
    ):
        object.__setattr__(invalid, field, value)
    with pytest.raises(ValueError):
        intersect_history_intervals(valid, invalid)


spans = st.builds(
    lambda pair, a, b: interval(*sorted(pair), a, b),
    st.tuples(st.integers(-10, 10), st.integers(-10, 10)),
    st.booleans(),
    st.booleans(),
)


def points(span):
    if span is None:
        return set()
    return {
        value
        for value in range(-10, 11)
        if (instant(value) > span.start or (instant(value) == span.start and span.include_start))
        and (instant(value) < span.end or (instant(value) == span.end and span.include_end))
    }


@given(left=spans, right=spans)
def test_intersection_matches_independent_finite_set_oracle(left, right):
    actual = intersect_history_intervals(left, right)
    assert points(actual) == points(left) & points(right)
    assert actual == intersect_history_intervals(right, left)
    assert left.empty == (not points(left))
    assert intersect_history_intervals(left, left) == (None if left.empty else left)
