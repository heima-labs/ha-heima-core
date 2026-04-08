"""Tests for PresencePatternReaction (Phase 7 R4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.presence import (
    PresencePatternReaction,
    _ArrivalRecord,
    _minute_of_day,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snap(anyone_home: bool = False, ts: str | None = None) -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    ts = ts or datetime.now(timezone.utc).isoformat()
    return replace(base, anyone_home=anyone_home, ts=ts)


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step() -> ApplyStep:
    return ApplyStep(domain="heating", target="climate.t", action="climate.set_temperature")


def _reaction(min_arrivals: int = 1, window_half_min: int = 30, pre_condition_min: int = 10) -> PresencePatternReaction:
    return PresencePatternReaction(
        steps=[_step()],
        min_arrivals=min_arrivals,
        window_half_min=window_half_min,
        pre_condition_min=pre_condition_min,
    )


def _local_now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


# ---------------------------------------------------------------------------
# Arrival recording
# ---------------------------------------------------------------------------


def test_records_arrival_on_false_to_true_transition():
    r = _reaction(min_arrivals=1)
    ts = _now_ts()
    r.evaluate([_snap(False, ts), _snap(True, ts)])
    assert len(r._arrivals) == 1


def test_no_arrival_recorded_when_already_home():
    r = _reaction()
    ts = _now_ts()
    r.evaluate([_snap(True, ts), _snap(True, ts)])
    assert len(r._arrivals) == 0


def test_no_arrival_recorded_on_single_snapshot():
    r = _reaction()
    r.evaluate([_snap(True)])
    assert len(r._arrivals) == 0


def test_no_arrival_when_home_to_away():
    r = _reaction()
    ts = _now_ts()
    r.evaluate([_snap(True, ts), _snap(False, ts)])
    assert len(r._arrivals) == 0


def test_arrival_records_correct_weekday():
    r = _reaction()
    ts = _now_ts()
    r.evaluate([_snap(False, ts), _snap(True, ts)])
    expected_weekday = datetime.fromisoformat(ts).astimezone().weekday()
    assert r._arrivals[0].weekday == expected_weekday


def test_arrival_records_correct_minute_of_day():
    r = _reaction()
    ts = _now_ts()
    r.evaluate([_snap(False, ts), _snap(True, ts)])
    expected_dt = datetime.fromisoformat(ts).astimezone()
    assert r._arrivals[0].minute_of_day == _minute_of_day(expected_dt)


def test_max_arrivals_evicts_oldest():
    r = PresencePatternReaction(steps=[], min_arrivals=1, max_arrivals=3)
    ts = _now_ts()
    for _ in range(5):
        r.evaluate([_snap(False, ts), _snap(True, ts)])
    assert len(r._arrivals) == 3


# ---------------------------------------------------------------------------
# _get_typical_window
# ---------------------------------------------------------------------------


def test_window_none_when_below_min_arrivals():
    r = PresencePatternReaction(steps=[], min_arrivals=3)
    r._arrivals = [_ArrivalRecord(0, 1080), _ArrivalRecord(0, 1080)]
    assert r._get_typical_window(0) is None


def test_window_computed_from_median():
    r = PresencePatternReaction(steps=[], min_arrivals=3, window_half_min=15)
    r._arrivals = [
        _ArrivalRecord(0, 1060),
        _ArrivalRecord(0, 1080),
        _ArrivalRecord(0, 1100),
    ]
    start, end = r._get_typical_window(0)
    assert start == 1080 - 15
    assert end == 1080 + 15


def test_window_uses_weekday_filter():
    r = PresencePatternReaction(steps=[], min_arrivals=1, window_half_min=10)
    r._arrivals = [
        _ArrivalRecord(0, 1080),  # Monday
        _ArrivalRecord(2, 600),   # Wednesday
    ]
    # Monday window should exist
    w_mon = r._get_typical_window(0)
    assert w_mon is not None
    # Tuesday has no arrivals
    assert r._get_typical_window(1) is None


def test_window_median_even_count():
    r = PresencePatternReaction(steps=[], min_arrivals=2, window_half_min=10)
    r._arrivals = [
        _ArrivalRecord(0, 1060),
        _ArrivalRecord(0, 1080),
    ]
    # even count: median at index len//2 = 1 → 1080
    start, end = r._get_typical_window(0)
    assert start == 1080 - 10
    assert end == 1080 + 10


# ---------------------------------------------------------------------------
# _should_pre_condition
# ---------------------------------------------------------------------------


def test_pre_condition_triggers_when_in_window():
    now_dt = _local_now()
    if _minute_of_day(now_dt) + 10 >= 1440:
        pytest.skip("too close to midnight — arrival would wrap to next day")
    r = PresencePatternReaction(
        steps=[], min_arrivals=1, window_half_min=60, pre_condition_min=10
    )
    weekday = now_dt.weekday()
    target_minute = _minute_of_day(now_dt) + 10
    r._arrivals = [_ArrivalRecord(weekday=weekday, minute_of_day=target_minute)]
    assert r._should_pre_condition(_now_ts()) is True


def test_pre_condition_false_when_pattern_not_established():
    r = PresencePatternReaction(
        steps=[], min_arrivals=5, window_half_min=30, pre_condition_min=10
    )
    # No arrivals recorded → pattern not established
    assert r._should_pre_condition(_now_ts()) is False


def test_pre_condition_false_when_outside_window():
    r = PresencePatternReaction(
        steps=[], min_arrivals=1, window_half_min=5, pre_condition_min=10
    )
    now_dt = _local_now()
    weekday = now_dt.weekday()
    # Place arrival 120 minutes from now → well outside window_half_min=5
    target_minute = (_minute_of_day(now_dt) + 120) % 1440
    r._arrivals = [_ArrivalRecord(weekday=weekday, minute_of_day=target_minute)]
    assert r._should_pre_condition(_now_ts()) is False


def test_pre_condition_false_wrong_weekday():
    r = PresencePatternReaction(
        steps=[], min_arrivals=1, window_half_min=60, pre_condition_min=10
    )
    now_dt = _local_now()
    # Place arrival on the next weekday
    other_weekday = (now_dt.weekday() + 1) % 7
    target_minute = _minute_of_day(now_dt) + 10
    r._arrivals = [_ArrivalRecord(weekday=other_weekday, minute_of_day=target_minute)]
    # Today's pattern is not established → no fire
    # (next day check only applies near midnight)
    assert r._should_pre_condition(_now_ts()) is False


# ---------------------------------------------------------------------------
# evaluate — full flow
# ---------------------------------------------------------------------------


def test_evaluate_does_not_fire_when_someone_home():
    r = _reaction()
    result = r.evaluate([_snap(True)])
    assert result == []


def test_evaluate_does_not_fire_before_min_arrivals():
    r = PresencePatternReaction(steps=[_step()], min_arrivals=5)
    now_dt = _local_now()
    weekday = now_dt.weekday()
    # Inject 4 arrivals (one less than min_arrivals=5)
    r._arrivals = [_ArrivalRecord(weekday, _minute_of_day(now_dt) + 10)] * 4
    result = r.evaluate([_snap(False)])
    assert result == []


def test_evaluate_fires_when_pre_condition_matches():
    now_dt = _local_now()
    if _minute_of_day(now_dt) + 10 >= 1440:
        pytest.skip("too close to midnight")
    r = PresencePatternReaction(
        steps=[_step()],
        min_arrivals=1,
        window_half_min=60,
        pre_condition_min=10,
    )
    weekday = now_dt.weekday()
    r._arrivals = [_ArrivalRecord(weekday=weekday, minute_of_day=_minute_of_day(now_dt) + 10)]
    result = r.evaluate([_snap(False, _now_ts())])
    assert len(result) == 1


def test_evaluate_returns_empty_when_no_history():
    r = _reaction()
    assert r.evaluate([]) == []


def test_fire_count_increments():
    now_dt = _local_now()
    if _minute_of_day(now_dt) + 10 >= 1440:
        pytest.skip("too close to midnight")
    r = PresencePatternReaction(
        steps=[_step()], min_arrivals=1, window_half_min=60, pre_condition_min=10
    )
    weekday = now_dt.weekday()
    r._arrivals = [_ArrivalRecord(weekday=weekday, minute_of_day=_minute_of_day(now_dt) + 10)]
    ts = _now_ts()
    r.evaluate([_snap(False, ts)])
    r.evaluate([_snap(False, ts)])
    assert r._fire_count == 2


# ---------------------------------------------------------------------------
# arrivals_for_weekday helper
# ---------------------------------------------------------------------------


def test_arrivals_for_weekday_filters_correctly():
    r = _reaction()
    r._arrivals = [
        _ArrivalRecord(0, 1080),
        _ArrivalRecord(0, 1100),
        _ArrivalRecord(2, 600),
    ]
    assert r.arrivals_for_weekday(0) == [1080, 1100]
    assert r.arrivals_for_weekday(2) == [600]
    assert r.arrivals_for_weekday(5) == []


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_initial():
    r = _reaction()
    d = r.diagnostics()
    assert d["arrivals_count"] == 0
    assert d["fire_count"] == 0
    assert d["suppressed_count"] == 0
    assert d["last_fired_ts"] is None


def test_diagnostics_after_arrivals():
    r = _reaction()
    ts = _now_ts()
    r.evaluate([_snap(False, ts), _snap(True, ts)])
    d = r.diagnostics()
    assert d["arrivals_count"] == 1
    assert len(d["arrivals_by_weekday"]) == 1


def test_reset_learning_state_clears_arrivals_and_counters():
    r = PresencePatternReaction(steps=[_step()], min_arrivals=1, window_half_min=60, pre_condition_min=10)
    now_dt = _local_now()
    weekday = now_dt.weekday()
    r._arrivals = [_ArrivalRecord(weekday=weekday, minute_of_day=_minute_of_day(now_dt) + 10)]
    r._fire_count = 2
    r._suppressed_count = 1
    r._last_fired_ts = 123.0

    r.reset_learning_state()

    assert r._arrivals == []
    assert r._fire_count == 0
    assert r._suppressed_count == 0
    assert r._last_fired_ts is None


def test_diagnostics_no_learning_key_without_backend():
    r = _reaction()
    assert "learning" not in r.diagnostics()


def test_diagnostics_has_learning_key_with_backend():
    from custom_components.heima.runtime.reactions.learning import NaiveLearningBackend
    b = NaiveLearningBackend()
    r = PresencePatternReaction(steps=[_step()], learning_backend=b)
    assert "learning" in r.diagnostics()


# ---------------------------------------------------------------------------
# _minute_of_day helper
# ---------------------------------------------------------------------------


def test_minute_of_day_midnight():
    from datetime import timezone as tz_
    dt = datetime(2026, 1, 1, 0, 0, tzinfo=tz_.utc)
    assert _minute_of_day(dt) == 0


def test_minute_of_day_noon():
    from datetime import timezone as tz_
    dt = datetime(2026, 1, 1, 12, 30, tzinfo=tz_.utc)
    assert _minute_of_day(dt) == 12 * 60 + 30


def test_minute_of_day_end_of_day():
    from datetime import timezone as tz_
    dt = datetime(2026, 1, 1, 23, 59, tzinfo=tz_.utc)
    assert _minute_of_day(dt) == 23 * 60 + 59
