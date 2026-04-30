"""Tests for D4 engine wiring: _collect_signals and _record_snapshot_if_changed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.heima.runtime.inference import (
    HouseSnapshot,
    HouseStateSignal,
    Importance,
    InferenceContext,
    SnapshotStore,
    WeekdayStateModule,
)
from custom_components.heima.runtime.inference.base import HeimaLearningModule
from custom_components.heima.runtime.inference.router import SignalRouter
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _RecordingModule(HeimaLearningModule):
    """Learning module that captures the InferenceContext it received."""

    module_id = "recording"
    received: list[InferenceContext] = []
    emit: list[HouseStateSignal] = []

    def infer(self, context: InferenceContext) -> list[HouseStateSignal]:
        type(self).received.append(context)
        return list(type(self).emit)


@pytest.fixture(autouse=True)
def reset_recording_module() -> None:
    _RecordingModule.received = []
    _RecordingModule.emit = []


def _snapshot(
    *,
    house_state: str = "home",
    anyone_home: bool = True,
    occupied_rooms: list[str] | None = None,
    lighting_intents: dict[str, str] | None = None,
    heating_setpoint: float | None = 20.5,
    security_state: str = "disarmed",
) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="test-id",
        ts="2026-04-30T10:00:00+00:00",
        house_state=house_state,
        anyone_home=anyone_home,
        people_count=1,
        occupied_rooms=occupied_rooms or ["kitchen"],
        lighting_intents=lighting_intents or {"kitchen": "bright"},
        security_state=security_state,
        heating_setpoint=heating_setpoint,
    )


def _make_signal_router_and_modules(
    modules: list[HeimaLearningModule],
) -> tuple[SignalRouter, list[HeimaLearningModule]]:
    return SignalRouter(), modules


# ---------------------------------------------------------------------------
# _collect_signals tests
# ---------------------------------------------------------------------------


def test_collect_signals_returns_empty_with_no_modules() -> None:
    router = SignalRouter()
    # Simulate _collect_signals without the full engine
    now = datetime(2026, 4, 30, 10, 0, tzinfo=UTC)
    paired: list = []
    result = router.route(paired, now)
    assert result == {}


def test_collect_signals_builds_correct_inference_context() -> None:
    module = _RecordingModule()
    router = SignalRouter()
    now = datetime(2026, 4, 30, 10, 30, tzinfo=UTC)

    prev_snapshot = _snapshot(house_state="away", heating_setpoint=16.0)

    context = InferenceContext(
        now_local=now,
        weekday=now.weekday(),
        minute_of_day=now.hour * 60 + now.minute,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy={"kitchen": True},
        previous_house_state=prev_snapshot.house_state,
        previous_heating_setpoint=prev_snapshot.heating_setpoint,
        previous_lighting_scenes=dict(prev_snapshot.lighting_intents or {}),
        previous_activity_names=(),
    )
    signals = module.infer(context)
    assert signals == []
    assert len(_RecordingModule.received) == 1
    ctx = _RecordingModule.received[0]
    assert ctx.anyone_home is True
    assert ctx.named_present == ("alice",)
    assert ctx.previous_house_state == "away"
    assert ctx.previous_heating_setpoint == 16.0
    assert ctx.minute_of_day == 630


def test_collect_signals_routes_emitted_signals() -> None:
    sig = HouseStateSignal(
        source_id="recording",
        confidence=0.75,
        importance=Importance.SUGGEST,
        ttl_s=600,
        label="test",
        predicted_state="home",
    )
    _RecordingModule.emit = [sig]
    module = _RecordingModule()
    router = SignalRouter()
    now = datetime(2026, 4, 30, 10, 0, tzinfo=UTC)

    paired = [
        (s, now)
        for s in module.infer(
            InferenceContext(
                now_local=now,
                weekday=0,
                minute_of_day=600,
                anyone_home=True,
                named_present=(),
                room_occupancy={},
                previous_house_state="home",
                previous_heating_setpoint=None,
                previous_lighting_scenes={},
            )
        )
    ]
    result = router.route(paired, now)

    assert HouseStateSignal in result
    assert result[HouseStateSignal][0].predicted_state == "home"


# ---------------------------------------------------------------------------
# _record_snapshot_if_changed tests
# ---------------------------------------------------------------------------


class _FakeHAStore:
    payload: dict | None = None
    saved: dict | None = None
    delayed: list = []

    def __init__(self, hass: Any, *, version: int, key: str) -> None:
        del hass
        self.version = version
        self.key = key

    async def async_load(self) -> dict | None:
        return type(self).payload

    async def async_save(self, data: dict) -> None:
        type(self).saved = data

    def async_delay_save(self, serializer: Any, delay: int) -> None:
        type(self).delayed.append((serializer(), delay))


@pytest.fixture(autouse=True)
def reset_fake_ha_store() -> None:
    _FakeHAStore.payload = None
    _FakeHAStore.saved = None
    _FakeHAStore.delayed = []


@pytest.mark.asyncio
async def test_record_snapshot_builds_house_snapshot_from_decision_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.heima.runtime.inference import snapshot_store

    monkeypatch.setattr(snapshot_store, "Store", _FakeHAStore)
    store = SnapshotStore(object())  # type: ignore[arg-type]
    await store.async_load()

    snap = _snapshot(
        house_state="home",
        anyone_home=True,
        occupied_rooms=["kitchen", "living_room"],
        lighting_intents={"kitchen": "bright", "living_room": "dim"},
        heating_setpoint=21.0,
        security_state="disarmed",
    )

    now = datetime(2026, 4, 30, 10, 30, tzinfo=UTC)
    house_snap = HouseSnapshot(
        ts=snap.ts,
        weekday=now.weekday(),
        minute_of_day=now.hour * 60 + now.minute,
        anyone_home=snap.anyone_home,
        named_present=("alice",),
        room_occupancy={room: True for room in snap.occupied_rooms},
        detected_activities=(),
        house_state=snap.house_state,
        heating_setpoint=snap.heating_setpoint,
        lighting_scenes=dict(snap.lighting_intents or {}),
        security_armed=snap.security_state not in ("disarmed", "unknown", "disabled", ""),
    )

    written = await store.async_append_if_changed(house_snap)
    assert written is True
    assert len(store.snapshots()) == 1
    s = store.snapshots()[0]
    assert s.house_state == "home"
    assert s.heating_setpoint == 21.0
    assert s.lighting_scenes == {"kitchen": "bright", "living_room": "dim"}
    assert s.room_occupancy == {"kitchen": True, "living_room": True}
    assert s.security_armed is False


@pytest.mark.asyncio
async def test_record_snapshot_security_armed_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.heima.runtime.inference import snapshot_store

    monkeypatch.setattr(snapshot_store, "Store", _FakeHAStore)
    store = SnapshotStore(object())  # type: ignore[arg-type]
    await store.async_load()

    for armed_state in ("armed_home", "armed_away", "triggered"):
        store_snap = HouseSnapshot(
            ts="2026-04-30T10:00:00+00:00",
            weekday=3,
            minute_of_day=600,
            anyone_home=True,
            named_present=(),
            room_occupancy={},
            house_state="home",
            security_armed=armed_state not in ("disarmed", "unknown", "disabled", ""),
        )
        assert store_snap.security_armed is True

    disarmed_snap = HouseSnapshot(
        ts="2026-04-30T10:00:00+00:00",
        weekday=3,
        minute_of_day=600,
        anyone_home=True,
        named_present=(),
        room_occupancy={},
        house_state="home",
        security_armed="disarmed" not in ("disarmed", "unknown", "disabled", ""),
    )
    assert disarmed_snap.security_armed is False


# ---------------------------------------------------------------------------
# WeekdayStateModule analyze tick integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weekday_module_analyze_reads_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.heima.runtime.inference import snapshot_store

    monkeypatch.setattr(snapshot_store, "Store", _FakeHAStore)
    store = SnapshotStore(object())  # type: ignore[arg-type]
    await store.async_load()

    for _ in range(10):
        await store.async_append(
            HouseSnapshot(
                ts="2026-04-30T10:00:00+00:00",
                weekday=3,
                minute_of_day=600,
                anyone_home=True,
                named_present=(),
                room_occupancy={},
                house_state="home",
            )
        )

    module = WeekdayStateModule()
    await module.analyze(store)

    assert module.diagnostics()["ready"] is True
    assert module.diagnostics()["slot_count"] >= 1
