"""CA4-100 exact numeric meaning, conservative representation and calendar bounds."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import localcontext
from fractions import Fraction
from math import inf, nextafter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.deadlines import Unrepresentable, derive_instant
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.timing import Window

ANCHOR = "2026-10-14T12:00:00.000000+00:00"


@pytest.mark.parametrize(
    "seconds,us",
    [
        (1e-7, 1),
        (1e-6, 1),
        (1.5e-6, 2),
        (2e-6, 2),
        (0.1, 100000),
        (5e-324, 1),
        (nextafter(1e-6, 0), 1),
        (nextafter(1e-6, inf), 2),
    ],
)
def test_approved_examples_and_microsecond_boundary(seconds, us):
    window = Window(seconds)
    before = window.canonical_bytes()
    assert derive_instant(ANCHOR, window) == format_instant(
        parse_instant(ANCHOR) + timedelta(microseconds=us)
    )
    assert window.canonical_bytes() == before


@pytest.mark.parametrize(
    "strict,seconds,us",
    [(False, 1e-6, 1), (True, 1e-6, 2), (False, 1.5e-6, 2), (True, 1.5e-6, 2), (True, 0.1, 100001)],
)
def test_strict_and_inclusive_decision_pairs(strict, seconds, us):
    assert derive_instant(ANCHOR, Window(seconds), strictly_after=strict) == format_instant(
        parse_instant(ANCHOR) + timedelta(microseconds=us)
    )


@pytest.mark.parametrize(
    "strict,seconds,expected",
    [
        (False, 5e-324, "9999-12-31T23:59:59.999999+00:00"),
        (False, 1e-6, "9999-12-31T23:59:59.999999+00:00"),
        (False, nextafter(1e-6, inf), None),
        (True, 1e-6, None),
        (True, nextafter(1e-6, 0), "9999-12-31T23:59:59.999999+00:00"),
    ],
)
def test_calendar_boundary(strict, seconds, expected):
    anchor = "9999-12-31T23:59:59.999998+00:00"
    window = Window(seconds)
    result = derive_instant(anchor, window, strictly_after=strict)
    if expected is None:
        assert isinstance(result, Unrepresentable)
        assert (result.anchor, result.duration) == (anchor, window)
        with pytest.raises(FrozenInstanceError):
            result.anchor = ANCHOR
    else:
        assert result == expected


@pytest.mark.parametrize("seconds", [5e-324, 1e-7, 1e308])
def test_max_instant_cannot_accept_positive_duration(seconds):
    assert isinstance(
        derive_instant("9999-12-31T23:59:59.999999+00:00", Window(seconds)), Unrepresentable
    )


def test_arithmetic_ignores_decimal_context_and_retains_long_decimal():
    with localcontext() as context:
        context.prec = 2
        assert (
            derive_instant(ANCHOR, Window(123456.123456789)) == "2026-10-15T22:17:36.123457+00:00"
        )
        assert isinstance(derive_instant(ANCHOR, Window(1e308)), Unrepresentable)


@pytest.mark.parametrize(
    "anchor,seconds,expected",
    [
        ("9999-12-31T23:59:58.000000+00:00", 1, "9999-12-31T23:59:59.000000+00:00"),
        ("9999-12-30T23:59:59.999999+00:00", 86400, "9999-12-31T23:59:59.999999+00:00"),
        ("9999-12-30T23:59:59.999999+00:00", 86400.000001, None),
    ],
)
def test_calendar_remaining_seconds_and_days(anchor, seconds, expected):
    result = derive_instant(anchor, Window(seconds))
    if expected is None:
        assert isinstance(result, Unrepresentable)
    else:
        assert result == expected


@pytest.mark.parametrize(
    "anchor,duration,strict,error",
    [
        ("2026-10-14T12:00:00Z", Window(1), False, ValueError),
        (None, Window(1), False, TypeError),
        (ANCHOR, 1, False, TypeError),
        (ANCHOR, Window(1), 1, TypeError),
    ],
)
def test_rejects_invalid_input_instead_of_normalizing(anchor, duration, strict, error):
    with pytest.raises(error):
        derive_instant(anchor, duration, strictly_after=strict)


@given(
    seconds=st.floats(min_value=5e-324, max_value=1e12, allow_nan=False, allow_infinity=False),
    strict=st.booleans(),
    us=st.integers(0, 999999),
)
def test_first_representable_instant_property(seconds, strict, us):
    anchor = format_instant(datetime(2026, 10, 14, 12, tzinfo=UTC) + timedelta(microseconds=us))
    result = derive_instant(anchor, Window(seconds), strictly_after=strict)
    exact = Fraction(canonical_json_bytes(seconds).decode()) * 1000000
    if isinstance(result, Unrepresentable):
        remaining = datetime.max.replace(tzinfo=UTC) - parse_instant(anchor)
        max_us = (remaining.days * 86400 + remaining.seconds) * 1000000 + remaining.microseconds
        assert exact > max_us or (strict and exact == max_us)
    else:
        difference = parse_instant(result) - parse_instant(anchor)
        actual = (difference.days * 86400 + difference.seconds) * 1000000 + difference.microseconds
        assert actual > 0
        if strict:
            assert exact < actual <= exact + 1
        else:
            assert exact <= actual < exact + 1
