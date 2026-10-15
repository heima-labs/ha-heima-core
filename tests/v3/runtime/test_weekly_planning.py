"""Weekly next-due contract: civil transitions, UTC boundaries and invariants."""

import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.timing import (
    IntervalRecurrence,
    WeeklyRecurrence,
    Window,
)
from custom_components.heima.v3.runtime.recurrence import next_weekly_occurrence


@pytest.fixture(autouse=True, params=["UTC", "Europe/Rome"])
def ambient_zone(request, monkeypatch):
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    try:
        yield
    finally:
        monkeypatch.undo()
        time.tzset()


def test_local_date_uses_configured_zone():
    assert (
        plan("2026-10-17T23:59:00.000000+00:00", "Asia/Tokyo", hour=9, minute=0).start
        == "2026-10-18T00:00:00.000000+00:00"
    )


def test_local_day_behind_utc_still_has_future_request():
    assert (
        plan(
            "2026-10-18T06:58:00.000000+00:00",
            "America/Los_Angeles",
            weekdays=frozenset({5}),
            hour=23,
            minute=59,
        ).start
        == "2026-10-18T06:59:00.000000+00:00"
    )


def test_normal_minute_has_no_gap_shift():
    assert (
        plan("2026-10-18T00:00:00.000000+00:00", "Europe/Rome", hour=7, minute=0).start
        == "2026-10-18T05:00:00.000000+00:00"
    )


def plan(wall, zone="UTC", weekdays=frozenset({6}), hour=2, minute=30):
    return next_weekly_occurrence(WeeklyRecurrence(weekdays, hour, minute), wall, ZoneInfo(zone))


@pytest.mark.parametrize(
    "wall,expected",
    [
        ("2026-03-29T00:59:59.999999+00:00", "2026-03-29T01:00:00.000000+00:00"),
        ("2026-03-29T01:00:00.000000+00:00", "2026-04-05T00:30:00.000000+00:00"),
        ("2026-03-29T01:00:00.000001+00:00", "2026-04-05T00:30:00.000000+00:00"),
        ("2026-10-25T00:29:59.999999+00:00", "2026-10-25T00:30:00.000000+00:00"),
        ("2026-10-25T00:30:00.000000+00:00", "2026-11-01T01:30:00.000000+00:00"),
        ("2026-10-25T00:30:00.000001+00:00", "2026-11-01T01:30:00.000000+00:00"),
        ("2026-10-25T01:29:59.999999+00:00", "2026-11-01T01:30:00.000000+00:00"),
    ],
)
def test_rome_gap_and_fold_boundaries(wall, expected):
    assert plan(wall, "Europe/Rome").start == expected


@pytest.mark.parametrize(
    "zone,wall,days,hour,minute,expected",
    [
        (
            "Australia/Lord_Howe",
            "2026-10-03T15:15:00.000000+00:00",
            {6},
            2,
            15,
            "2026-10-03T15:30:00.000000+00:00",
        ),
        (
            "Pacific/Apia",
            "2011-12-29T21:00:00.000000+00:00",
            {4},
            4,
            0,
            "2011-12-30T10:00:00.000000+00:00",
        ),
        (
            "Asia/Tokyo",
            "2026-10-18T00:00:00.000000+00:00",
            {6},
            9,
            1,
            "2026-10-18T00:01:00.000000+00:00",
        ),
        ("UTC", "2026-10-18T00:00:00.000000+00:00", {6}, 9, 1, "2026-10-18T09:01:00.000000+00:00"),
    ],
)
def test_explicit_zone_and_non_hour_gaps(zone, wall, days, hour, minute, expected):
    assert plan(wall, zone, frozenset(days), hour, minute).start == expected


@pytest.mark.parametrize(
    "wall,hours",
    [
        ("2026-03-22T06:00:00.000000+00:00", 167),
        ("2026-10-18T05:00:00.000000+00:00", 169),
    ],
)
def test_local_hour_stays_fixed_across_dst(wall, hours):
    due = parse_instant(plan(wall, "Europe/Rome", hour=7, minute=0).start)
    assert due - parse_instant(wall) == timedelta(hours=hours)
    assert due.astimezone(ZoneInfo("Europe/Rome")).hour == 7


def test_history_matches_both_folds_but_future_scheduling_skips_second():
    pattern = WeeklyRecurrence(frozenset({6}), 2, 30)
    zone = ZoneInfo("Europe/Rome")
    assert pattern.matches("2026-10-25T00:30:00.000000+00:00", zone)
    assert pattern.matches("2026-10-25T01:30:00.000000+00:00", zone)
    assert (
        plan("2026-10-25T01:00:00.000000+00:00", zone.key).start
        == "2026-11-01T01:30:00.000000+00:00"
    )


@pytest.mark.parametrize("offset,expected", [(-1, 0), (0, 7), (1, 7)])
def test_exact_due_is_not_replayed(offset, expected):
    anchor = datetime(2026, 10, 19, 7, 30, tzinfo=UTC)
    wall = format_instant(anchor + timedelta(microseconds=offset))
    assert plan(wall, weekdays=frozenset({0}), hour=7).start == format_instant(
        anchor + timedelta(days=expected)
    )


@given(
    wall=st.datetimes(
        min_value=datetime(2000, 1, 1), max_value=datetime(2090, 1, 1), timezones=st.just(UTC)
    ),
    days=st.frozensets(st.integers(0, 6), min_size=1),
    hour=st.integers(0, 23),
    minute=st.integers(0, 59),
)
def test_utc_future_matching_and_requested_date(wall, days, hour, minute):
    pattern = WeeklyRecurrence(days, hour, minute)
    occurrence = next_weekly_occurrence(pattern, format_instant(wall), ZoneInfo("UTC"))
    start = parse_instant(occurrence.start)
    assert wall < start <= wall + timedelta(days=7)
    assert pattern.matches(occurrence.start, ZoneInfo("UTC"))
    assert start.second == start.microsecond == 0
    assert occurrence.requested_date == start.date()


@pytest.mark.parametrize(
    "pattern,now,zone,error",
    [
        (None, None, None, TypeError),
        (IntervalRecurrence(Window(30)), None, ZoneInfo("UTC"), TypeError),
        (WeeklyRecurrence(frozenset({0}), 0), None, ZoneInfo("UTC"), TypeError),
        (WeeklyRecurrence(frozenset({0}), 0), "2026-01-01T00:00:00.000000+00:00", "UTC", TypeError),
        (WeeklyRecurrence(frozenset({0}), 0), "2026-01-01T00:00:00Z", ZoneInfo("UTC"), ValueError),
    ],
)
def test_rejects_wrong_boundary_shapes(pattern, now, zone, error):
    with pytest.raises(error):
        next_weekly_occurrence(pattern, now, zone)


def test_apia_retains_requested_date_instead_of_shifted_start_date():
    occurrence = plan("2011-12-29T21:00:00.000000+00:00", "Pacific/Apia", frozenset({4}), 4, 0)
    assert occurrence.requested_date == date(2011, 12, 30)
    assert occurrence.start == "2011-12-30T10:00:00.000000+00:00"
    assert parse_instant(occurrence.start).astimezone(ZoneInfo("Pacific/Apia")).date() == date(
        2011, 12, 31
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        occurrence.requested_date = date(2011, 12, 31)
    with pytest.raises(FrozenInstanceError):
        occurrence.start = "2011-12-31T10:00:00.000000+00:00"


def test_calendar_exhaustion_is_explicit():
    with pytest.raises(ValueError):
        plan("9999-12-31T23:59:59.999999+00:00", weekdays=frozenset(range(7)))


def test_merged_physical_start_keeps_distinct_requested_dates_for_consumer():
    now = "2011-12-29T21:00:00.000000+00:00"
    friday = plan(now, "Pacific/Apia", frozenset({4}), 0, 0)
    saturday = plan(now, "Pacific/Apia", frozenset({5}), 0, 0)
    assert friday.start == saturday.start == "2011-12-30T10:00:00.000000+00:00"
    assert friday.requested_date == date(2011, 12, 30)
    assert saturday.requested_date == date(2011, 12, 31)


def test_past_candidate_below_calendar_minimum_does_not_hide_next_week():
    occurrence = plan("0001-01-01T00:00:00.000000+00:00", "Etc/GMT-1", frozenset({0}), 0, 0)
    assert occurrence.requested_date == date(1, 1, 8)
    assert occurrence.start == "0001-01-07T23:00:00.000000+00:00"
