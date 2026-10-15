"""Temporal construction and comparison contracts, Layer 0 §§3.1–3.4."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, tzinfo
from enum import StrEnum
from math import inf, nan
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import (
    format_instant,
    parse_instant,
    validate_instant,
)
from custom_components.heima.v3.contracts.timing import (
    AtJob,
    CalendarWindow,
    CronEntry,
    IntervalRecurrence,
    WeeklyRecurrence,
    Window,
    validate_duration,
)

T = "2026-10-12T05:30:00.000000+00:00"


@pytest.mark.parametrize("value", [1, 0.5, 5e-324, 1.7976931348623157e308, 2**60])
def test_duration_valid_and_canonical(value):
    window = Window(value)
    assert type(window.seconds) is float
    assert window.seconds == float(value)
    assert validate_duration(value) == window.seconds
    assert window.canonical_bytes().startswith(b'{"seconds":')
    assert Window(1).canonical_bytes() == b'{"seconds":1}'
    assert Window(0.25).canonical_bytes() == b'{"seconds":0.25}'
    with pytest.raises(FrozenInstanceError):
        window.seconds = 0


@pytest.mark.parametrize(
    "value",
    [True, False, None, "1", timedelta(seconds=1), 0, -0.0, -1, -5e-324, nan, inf, -inf, 10**400],
)
def test_invalid_duration_never_corrected(value):
    with pytest.raises((TypeError, ValueError)):
        Window(value)
    with pytest.raises((TypeError, ValueError)):
        validate_duration(value)


@pytest.mark.parametrize(
    "value",
    [
        T,
        "0001-01-01T00:00:00.000000+00:00",
        "9999-12-31T23:59:59.999999+00:00",
        "2024-02-29T00:00:00.000001+00:00",
    ],
)
def test_instant_valid_calendar_and_exact_precision(value):
    result = parse_instant(value)
    assert result.tzinfo == UTC
    assert format_instant(result) == value
    assert validate_instant(value) == value
    assert type(validate_instant(value)) is str


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        datetime(2026, 10, 12, tzinfo=UTC),
        "2026-10-12T05:30:00Z",
        "2026-10-12T05:30:00.000000Z",
        "2026-10-12T05:30:00.000000+01:00",
        "2026-10-12T05:30:00.00000+00:00",
        "2026-10-12T05:30:00.0000000+00:00",
        "2026-10-12 05:30:00.000000+00:00",
        T + "\n",
        " " + T,
        "2026-02-29T00:00:00.000000+00:00",
        "2026-10-12T24:00:00.000000+00:00",
        "2026-10-12T05:30:60.000000+00:00",
        "0000-01-01T00:00:00.000000+00:00",
        "２０２６-10-12T05:30:00.000000+00:00",
    ],
)
def test_instant_invalid_no_alias_or_silent_repair(value):
    with pytest.raises((TypeError, ValueError)):
        parse_instant(value)
    with pytest.raises((TypeError, ValueError)):
        validate_instant(value)


def test_producer_timezone_normalization_and_naive_rejection():
    local = datetime(2026, 10, 12, 7, 30, 0, 9, tzinfo=ZoneInfo("Europe/Rome"))
    assert format_instant(local) == "2026-10-12T05:30:00.000009+00:00"
    for value in [T, datetime(2026, 10, 12)]:
        with pytest.raises((TypeError, ValueError)):
            format_instant(value)

    class NoOffset(tzinfo):
        def utcoffset(self, dt):
            return None

    with pytest.raises(ValueError):
        format_instant(datetime(2026, 1, 1, tzinfo=NoOffset()))
    with pytest.raises(ValueError):
        format_instant(datetime(1, 1, 1, tzinfo=ZoneInfo("Etc/GMT-1")))


@pytest.mark.parametrize("basis", ["elapsed", "wall_clock"])
def test_job_and_cron_definitions_immutable(basis):
    job = AtJob("a", "engine", validate_instant(T), "  original label  ", basis)
    assert job.label == "  original label  "
    assert AtJob("a", "engine", validate_instant(T), job.label, basis) == job
    with pytest.raises(FrozenInstanceError):
        job.due = "other"
    for pattern in [IntervalRecurrence(Window(1))]:
        cron = CronEntry("a", "engine", pattern, "label")
        assert cron.pattern is pattern
        with pytest.raises(FrozenInstanceError):
            cron.pattern = None


class Basis(StrEnum):
    ELAPSED = "elapsed"


@pytest.mark.parametrize("basis", [None, "wrong", Basis.ELAPSED, 1])
def test_invalid_job_basis(basis):
    with pytest.raises(ValueError):
        AtJob("a", "engine", T, "label", basis)


@pytest.mark.parametrize("field", ["job_id", "owner", "label"])
def test_job_and_cron_text_fields_validated(field):
    job = dict(job_id="a", owner="engine", due=T, label="label", basis="elapsed")
    job[field] = None
    with pytest.raises(TypeError):
        AtJob(**job)
    cron = dict(job_id="a", owner="engine", pattern=IntervalRecurrence(Window(1)), label="label")
    cron[field] = None
    with pytest.raises(TypeError):
        CronEntry(**cron)


def test_invalid_job_due_and_recurrence_shapes():
    with pytest.raises(ValueError):
        AtJob("a", "engine", "2026-10-12T05:30:00Z", "label", "elapsed")
    for value in [1, None, True]:
        with pytest.raises(TypeError):
            IntervalRecurrence(value)
        with pytest.raises(TypeError):
            CronEntry("a", "engine", value, "label")


def test_cron_rejects_weekly_pattern_in_initial_v3():
    with pytest.raises(TypeError):
        CronEntry("a", "engine", WeeklyRecurrence(frozenset({0}), 7), "label")


@pytest.mark.parametrize("day", [0, 1, 5, 6])
@pytest.mark.parametrize("hour,minute", [(0, 0), (1, 1), (22, 58), (23, 59)])
def test_weekly_bounds_valid(day, hour, minute):
    pattern = WeeklyRecurrence(frozenset({day}), hour, minute)
    assert pattern.weekdays == frozenset({day})
    assert pattern.hour == hour and pattern.minute == minute
    with pytest.raises(FrozenInstanceError):
        pattern.hour = 1


@pytest.mark.parametrize(
    "days,hour,minute",
    [
        (frozenset(), 7, 0),
        ({0}, 7, 0),
        (frozenset({True}), 7, 0),
        (frozenset({-1}), 7, 0),
        (frozenset({7}), 7, 0),
        (frozenset({"0"}), 7, 0),
        (frozenset({0}), -1, 0),
        (frozenset({0}), 24, 0),
        (frozenset({0}), True, 0),
        (frozenset({0}), 7, -1),
        (frozenset({0}), 7, 60),
        (frozenset({0}), 7, True),
        (frozenset({0}), 7, 0.5),
    ],
)
def test_weekly_bounds_invalid(days, hour, minute):
    with pytest.raises((TypeError, ValueError)):
        WeeklyRecurrence(days, hour, minute)


# MC/DC: baseline all three conditions true; change weekday/hour/minute independently.
@pytest.mark.parametrize(
    "instant,expected",
    [
        (T, True),
        ("2026-10-13T05:30:00.000000+00:00", False),
        ("2026-10-12T06:30:00.000000+00:00", False),
        ("2026-10-12T05:31:00.000000+00:00", False),
        ("2026-10-12T05:30:59.999999+00:00", True),
    ],
)
def test_weekly_matches_mcdc(instant, expected):
    pattern = WeeklyRecurrence(frozenset({0}), 7, 30)
    assert pattern.matches(validate_instant(instant), ZoneInfo("Europe/Rome")) is expected


def test_weekly_both_dst_occurrences_classify_without_execution():
    pattern = WeeklyRecurrence(frozenset({6}), 2, 30)
    for instant in ["2026-10-25T00:30:00.000000+00:00", "2026-10-25T01:30:00.000000+00:00"]:
        assert pattern.matches(validate_instant(instant), ZoneInfo("Europe/Rome"))
    with pytest.raises(TypeError):
        pattern.matches(validate_instant(T), "Europe/Rome")


def test_calendar_half_open_boundaries_and_summary_preserved():
    end = "2026-10-12T06:30:00.000000+00:00"
    window = CalendarWindow(
        validate_instant(T), validate_instant(end), "  raw SUMMary\n", "calendar.work"
    )
    assert window.summary == "  raw SUMMary\n"
    assert window.source_entity == "calendar.work"
    # MC/DC lower and upper comparison, independent at either boundary.
    for instant, expected in [
        ("2026-10-12T05:29:59.999999+00:00", False),
        (T, True),
        ("2026-10-12T06:29:59.999999+00:00", True),
        (end, False),
        ("2026-10-12T06:30:00.000001+00:00", False),
    ]:
        assert window.contains(validate_instant(instant)) is expected
    with pytest.raises(FrozenInstanceError):
        window.summary = "changed"
    with pytest.raises(ValueError):
        window.contains("wrong")


@pytest.mark.parametrize("end", [T, "2026-10-12T05:29:59.999999+00:00", "wrong"])
def test_calendar_invalid_end(end):
    with pytest.raises(ValueError):
        CalendarWindow(T, end, "raw", "calendar.work")


def test_calendar_invalid_start_and_nontext_fields():
    end = "2026-10-12T06:30:00.000000+00:00"
    with pytest.raises(ValueError):
        CalendarWindow("wrong", end, "raw", "calendar.work")
    for summary, source in [(None, "calendar.work"), ("raw", None)]:
        with pytest.raises(TypeError):
            CalendarWindow(T, end, summary, source)


@settings(max_examples=50)
@given(
    st.datetimes(
        min_value=datetime(2, 1, 1), max_value=datetime(9998, 12, 31), timezones=st.just(UTC)
    )
)
def test_property_instant_round_trip(value):
    encoded = format_instant(value)
    assert parse_instant(encoded) == value
    assert len(encoded) == 32
    assert encoded.endswith("+00:00")


@settings(max_examples=50)
@given(
    st.floats(
        min_value=5e-324, max_value=1.7976931348623157e308, allow_nan=False, allow_infinity=False
    )
)
def test_property_duration_preserved(value):
    assert Window(value).seconds == value
    assert Window(value).canonical_bytes() == Window(float(value)).canonical_bytes()


def test_weekly_uses_explicit_zone_not_host_zone():
    utc_pattern = WeeklyRecurrence(frozenset({0}), 5, 30)
    tokyo_pattern = WeeklyRecurrence(frozenset({0}), 14, 30)
    assert utc_pattern.matches(validate_instant(T), ZoneInfo("UTC"))
    assert tokyo_pattern.matches(validate_instant(T), ZoneInfo("Asia/Tokyo"))
    interval = IntervalRecurrence(Window(1))
    with pytest.raises(FrozenInstanceError):
        interval.interval = Window(2)


class ReconstructedWindow(Window):
    """Model a Window subtype whose loader bypasses base post-init validation."""

    def __post_init__(self):
        pass


@pytest.mark.parametrize("value", [True, False, "1", 0, -5e-324, -1, nan, inf, -inf, 10**400])
def test_interval_validates_nested_duration_independently(value):
    with pytest.raises((TypeError, ValueError)):
        IntervalRecurrence(ReconstructedWindow(value))


@pytest.mark.parametrize("value", [5e-324, 1, 0.5, 1.7976931348623157e308])
def test_interval_normalizes_nested_duration_without_changing_input(value):
    source = ReconstructedWindow(value)
    recurrence = IntervalRecurrence(source)
    assert type(recurrence.interval.seconds) is float
    assert recurrence.interval.seconds == value
    assert type(source.seconds) is type(value)


@settings(max_examples=50)
@given(st.floats(allow_nan=True, allow_infinity=True))
def test_property_interval_admission_matches_duration_contract(value):
    source = ReconstructedWindow(value)
    if value > 0 and value < inf:
        recurrence = IntervalRecurrence(source)
        assert recurrence.interval.seconds == value
        assert type(recurrence.interval.seconds) is float
    else:
        with pytest.raises(ValueError):
            IntervalRecurrence(source)
