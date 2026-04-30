"""Tests for WeekdayStateModule and HeatingPreferenceModule."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from custom_components.heima.runtime.inference import (
    HeatingPreferenceModule,
    HouseSnapshot,
    Importance,
    InferenceContext,
    WeekdayStateModule,
)


def _context(
    *,
    weekday: int = 0,
    minute_of_day: int = 600,
    previous_house_state: str = "home",
    previous_heating_setpoint: float | None = 20.0,
) -> InferenceContext:
    return InferenceContext(
        now_local=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
        weekday=weekday,
        minute_of_day=minute_of_day,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy={"kitchen": True},
        previous_house_state=previous_house_state,
        previous_heating_setpoint=previous_heating_setpoint,
        previous_lighting_scenes={},
    )


def _snapshot(
    *,
    weekday: int = 0,
    minute_of_day: int = 600,
    house_state: str = "home",
    heating_setpoint: float | None = 20.5,
) -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-04-30T10:00:00+00:00",
        weekday=weekday,
        minute_of_day=minute_of_day,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy={},
        detected_activities=(),
        house_state=house_state,
        heating_setpoint=heating_setpoint,
        lighting_scenes={},
        security_armed=False,
    )


class _FakeStore:
    def __init__(self, snapshots: list[HouseSnapshot]) -> None:
        self._snapshots = snapshots

    def snapshots(self) -> list[HouseSnapshot]:
        return self._snapshots


# ─── WeekdayStateModule ───────────────────────────────────────────────────────


def test_weekday_state_returns_empty_before_analyze() -> None:
    module = WeekdayStateModule()
    assert module.infer(_context()) == []


@pytest.mark.asyncio
async def test_weekday_state_emits_signal_with_enough_support() -> None:
    module = WeekdayStateModule()
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))

    assert len(signals) == 1
    assert signals[0].predicted_state == "home"
    assert signals[0].source_id == "weekday_state"
    assert signals[0].confidence > 0.0


@pytest.mark.asyncio
async def test_weekday_state_no_signal_below_min_support() -> None:
    module = WeekdayStateModule()
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 5
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    assert signals == []


@pytest.mark.asyncio
async def test_weekday_state_no_signal_for_unknown_slot() -> None:
    module = WeekdayStateModule()
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=1, minute_of_day=600))
    assert signals == []


@pytest.mark.asyncio
async def test_weekday_state_importance_observe_range() -> None:
    module = WeekdayStateModule()
    # 10 snapshots split 5 home / 5 away → probability=0.5, confidence = 0.5 * 1.0 = 0.50 → OBSERVE
    snapshots = [
        _snapshot(weekday=0, minute_of_day=600, house_state="home"),
        _snapshot(weekday=0, minute_of_day=600, house_state="away"),
    ] * 5
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    # majority (home or away, both 5 each — max picks first alphabetically or by dict iteration)
    # Either way: probability=0.5, confidence=0.5, importance=OBSERVE
    assert len(signals) == 1
    assert signals[0].importance == Importance.OBSERVE


@pytest.mark.asyncio
async def test_weekday_state_importance_suggest_range() -> None:
    module = WeekdayStateModule()
    # 10 snapshots: 7 home / 3 away → probability=0.7, confidence = 0.7 * 1.0 = 0.70 → SUGGEST
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 7 + [
        _snapshot(weekday=0, minute_of_day=600, house_state="away")
    ] * 3
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    assert len(signals) == 1
    assert signals[0].importance == Importance.SUGGEST
    assert signals[0].predicted_state == "home"


@pytest.mark.asyncio
async def test_weekday_state_importance_assert_range() -> None:
    module = WeekdayStateModule()
    # 10 snapshots: 9 home / 1 away → probability=0.9, confidence = 0.9 → ASSERT
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 9 + [
        _snapshot(weekday=0, minute_of_day=600, house_state="away")
    ] * 1
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    assert len(signals) == 1
    assert signals[0].importance == Importance.ASSERT


@pytest.mark.asyncio
async def test_weekday_state_infer_completes_under_1ms() -> None:
    module = WeekdayStateModule()
    snapshots = [
        _snapshot(weekday=wd, minute_of_day=h * 60, house_state="home")
        for wd in range(7)
        for h in range(24)
        for _ in range(10)
    ]
    await module.analyze(_FakeStore(snapshots))

    start = time.perf_counter()
    module.infer(_context(weekday=3, minute_of_day=660))
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 1.0


@pytest.mark.asyncio
async def test_weekday_state_diagnostics() -> None:
    module = WeekdayStateModule()
    await module.analyze(_FakeStore([_snapshot()] * 10))
    diag = module.diagnostics()
    assert diag["module_id"] == "weekday_state"
    assert diag["ready"] is True
    assert diag["slot_count"] >= 1


# ─── HeatingPreferenceModule ──────────────────────────────────────────────────


def test_heating_preference_returns_empty_before_analyze() -> None:
    module = HeatingPreferenceModule()
    assert module.infer(_context()) == []


@pytest.mark.asyncio
async def test_heating_preference_emits_signal_with_enough_support() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert len(signals) == 1
    assert abs(signals[0].predicted_setpoint - 20.5) < 0.01
    assert signals[0].house_state_context == "home"
    assert signals[0].source_id == "heating_preference"


@pytest.mark.asyncio
async def test_heating_preference_no_signal_below_min_support() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 5
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert signals == []


@pytest.mark.asyncio
async def test_heating_preference_no_signal_for_unknown_state() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="away"))
    assert signals == []


@pytest.mark.asyncio
async def test_heating_preference_skips_snapshots_without_setpoint() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=None)] * 5 + [
        _snapshot(house_state="home", heating_setpoint=21.0)
    ] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert len(signals) == 1
    assert abs(signals[0].predicted_setpoint - 21.0) < 0.01


@pytest.mark.asyncio
async def test_heating_preference_mean_setpoint() -> None:
    module = HeatingPreferenceModule()
    setpoints = [19.0, 20.0, 21.0, 22.0, 19.5, 20.5, 21.5, 19.0, 20.0, 21.0]
    snapshots = [_snapshot(house_state="home", heating_setpoint=sp) for sp in setpoints]
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert len(signals) == 1
    assert abs(signals[0].predicted_setpoint - (sum(setpoints) / len(setpoints))) < 0.001


@pytest.mark.asyncio
async def test_heating_preference_infer_completes_under_1ms() -> None:
    module = HeatingPreferenceModule()
    snapshots = [
        _snapshot(house_state=state, heating_setpoint=sp)
        for state, sp in [("home", 20.5), ("away", 16.0), ("night", 18.0), ("vacation", 14.0)]
        for _ in range(10)
    ]
    await module.analyze(_FakeStore(snapshots))

    start = time.perf_counter()
    module.infer(_context(previous_house_state="home"))
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 1.0


@pytest.mark.asyncio
async def test_heating_preference_diagnostics() -> None:
    module = HeatingPreferenceModule()
    await module.analyze(_FakeStore([_snapshot(house_state="home")] * 10))
    diag = module.diagnostics()
    assert diag["module_id"] == "heating_preference"
    assert diag["ready"] is True
    assert diag["state_count"] >= 1
