"""Weekly next-due contract: civil transitions, UTC boundaries and invariants."""

import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.timing import (
    CronEntry,
    IntervalRecurrence,
    WeeklyRecurrence,
    Window,
)
from custom_components.heima.v3.runtime.clock import ExecutionClockReading
from custom_components.heima.v3.runtime.recurrence import plan_weekly_job


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
        plan("2026-10-17T23:59:00.000000+00:00", "Asia/Tokyo", hour=9, minute=0).due
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
        ).due
        == "2026-10-18T06:59:00.000000+00:00"
    )


def test_normal_minute_has_no_gap_shift():
    assert (
        plan("2026-10-18T00:00:00.000000+00:00", "Europe/Rome", hour=7, minute=0).due
        == "2026-10-18T05:00:00.000000+00:00"
    )


def plan(wall, zone="UTC", weekdays=frozenset({6}), hour=2, minute=30, floor=None):
    entry = CronEntry("routine", "owner", WeeklyRecurrence(weekdays, hour, minute), "label")
    return plan_weekly_job(entry, ExecutionClockReading(wall, floor or wall), ZoneInfo(zone))


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
    assert plan(wall, "Europe/Rome").due == expected


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
    assert plan(wall, zone, frozenset(days), hour, minute).due == expected


@pytest.mark.parametrize(
    "wall,hours",
    [
        ("2026-03-22T06:00:00.000000+00:00", 167),
        ("2026-10-18T05:00:00.000000+00:00", 169),
    ],
)
def test_local_hour_stays_fixed_across_dst(wall, hours):
    due = parse_instant(plan(wall, "Europe/Rome", hour=7, minute=0).due)
    assert due - parse_instant(wall) == timedelta(hours=hours)
    assert due.astimezone(ZoneInfo("Europe/Rome")).hour == 7


def test_history_matches_both_folds_but_future_scheduling_skips_second():
    pattern = WeeklyRecurrence(frozenset({6}), 2, 30)
    zone = ZoneInfo("Europe/Rome")
    assert pattern.matches("2026-10-25T00:30:00.000000+00:00", zone)
    assert pattern.matches("2026-10-25T01:30:00.000000+00:00", zone)
    assert (
        plan("2026-10-25T01:00:00.000000+00:00", zone.key).due == "2026-11-01T01:30:00.000000+00:00"
    )


@pytest.mark.parametrize("offset,expected", [(-1, 0), (0, 7), (1, 7)])
def test_exact_due_is_not_replayed(offset, expected):
    anchor = datetime(2026, 10, 19, 7, 30, tzinfo=UTC)
    wall = format_instant(anchor + timedelta(microseconds=offset))
    assert plan(wall, weekdays=frozenset({0}), hour=7).due == format_instant(
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
def test_utc_future_matching_and_floor_independence(wall, days, hour, minute):
    entry = CronEntry("id", "owner", WeeklyRecurrence(days, hour, minute), "label")
    current = format_instant(wall)
    job = plan_weekly_job(entry, ExecutionClockReading(current, current), ZoneInfo("UTC"))
    due = parse_instant(job.due)
    assert wall < due <= wall + timedelta(days=7)
    assert entry.pattern.matches(job.due, ZoneInfo("UTC"))
    assert due.second == due.microsecond == 0
    assert (job.job_id, job.owner, job.label, job.basis) == ("id", "owner", "label", "wall_clock")
    assert (
        plan_weekly_job(
            entry,
            ExecutionClockReading(current, format_instant(wall + timedelta(days=30))),
            ZoneInfo("UTC"),
        )
        == job
    )


@pytest.mark.parametrize(
    "entry,reading,zone",
    [
        (None, None, None),
        (CronEntry("id", "owner", IntervalRecurrence(Window(30)), "label"), None, None),
        (
            CronEntry("id", "owner", WeeklyRecurrence(frozenset({0}), 0), "label"),
            None,
            ZoneInfo("UTC"),
        ),
        (
            CronEntry("id", "owner", WeeklyRecurrence(frozenset({0}), 0), "label"),
            ExecutionClockReading(
                "2026-01-01T00:00:00.000000+00:00", "2026-01-01T00:00:00.000000+00:00"
            ),
            "UTC",
        ),
    ],
)
def test_rejects_wrong_boundary_shapes(entry, reading, zone):
    with pytest.raises(TypeError):
        plan_weekly_job(entry, reading, zone)


def test_calendar_exhaustion_is_explicit():
    with pytest.raises(ValueError):
        plan("9999-12-31T23:59:59.999999+00:00", weekdays=frozenset(range(7)))
