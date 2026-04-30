"""Tests for v2 inference foundation contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.heima.runtime.inference import (
    ActivitySignal,
    HeatingSignal,
    HeimaLearningModule,
    HouseSnapshot,
    HouseStateSignal,
    Importance,
    InferenceContext,
    LightingSignal,
    OccupancySignal,
    SnapshotStore,
)


class _FakeStore:
    payload: dict | None = None
    saved: dict | None = None
    delayed: list[tuple[dict, int]] = []

    def __init__(self, hass, *, version: int, key: str) -> None:  # noqa: ANN001
        del hass
        self.version = version
        self.key = key

    async def async_load(self) -> dict | None:
        return type(self).payload

    async def async_save(self, data: dict) -> None:
        type(self).saved = data

    def async_delay_save(self, serializer, delay: int) -> None:  # noqa: ANN001
        type(self).delayed.append((serializer(), delay))


@pytest.fixture(autouse=True)
def reset_fake_store() -> None:
    _FakeStore.payload = None
    _FakeStore.saved = None
    _FakeStore.delayed = []


def _snapshot(
    *,
    ts: str = "2026-04-30T10:00:00+00:00",
    anyone_home: bool = True,
    house_state: str = "home",
) -> HouseSnapshot:
    return HouseSnapshot(
        ts=ts,
        weekday=3,
        minute_of_day=600,
        anyone_home=anyone_home,
        named_present=("alice",),
        room_occupancy={"kitchen": True},
        detected_activities=(),
        house_state=house_state,
        heating_setpoint=20.5,
        lighting_scenes={"kitchen": "bright"},
        security_armed=False,
    )


def test_inference_context_and_signals_are_typed() -> None:
    context = InferenceContext(
        now_local=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        weekday=3,
        minute_of_day=720,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy={"kitchen": True},
        previous_house_state="home",
        previous_heating_setpoint=20.0,
        previous_lighting_scenes={"kitchen": "bright"},
        previous_activity_names=("cooking",),
    )
    assert context.previous_activity_names == ("cooking",)

    base_kwargs = {
        "source_id": "module",
        "confidence": 0.7,
        "importance": Importance.SUGGEST,
        "ttl_s": 600,
        "label": "test",
    }
    assert HouseStateSignal(**base_kwargs, predicted_state="home").predicted_state == "home"
    assert (
        HeatingSignal(
            **base_kwargs, predicted_setpoint=20.5, house_state_context="home"
        ).predicted_setpoint
        == 20.5
    )
    assert LightingSignal(**base_kwargs, room_id="kitchen", predicted_scene="bright").room_id
    assert ActivitySignal(**base_kwargs, activity_name="cooking", room_id="kitchen").context == {}
    assert OccupancySignal(
        **base_kwargs, room_id="kitchen", predicted_occupied=True
    ).predicted_occupied


@pytest.mark.asyncio
async def test_learning_module_base_returns_no_signals_before_analysis() -> None:
    module = HeimaLearningModule()
    context = InferenceContext(
        now_local=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        weekday=3,
        minute_of_day=720,
        anyone_home=True,
        named_present=(),
        room_occupancy={},
        previous_house_state="home",
        previous_heating_setpoint=None,
        previous_lighting_scenes={},
    )

    await module.analyze(object())

    assert module.infer(context) == []
    assert module.diagnostics() == {"module_id": "heima_learning_module", "ready": False}


def test_house_snapshot_serialization_and_semantic_key() -> None:
    first = _snapshot(ts="2026-04-30T10:00:00+00:00")
    second = _snapshot(ts="2026-04-30T10:01:00+00:00")

    restored = HouseSnapshot.from_dict(first.as_dict())

    assert restored == first
    assert first.semantic_key() == second.semantic_key()


@pytest.mark.asyncio
async def test_snapshot_store_loads_saves_and_uses_expected_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.heima.runtime.inference import snapshot_store

    monkeypatch.setattr(snapshot_store, "Store", _FakeStore)
    _FakeStore.payload = {"data": {"snapshots": [_snapshot().as_dict(), {"bad": "record"}]}}
    store = SnapshotStore(object())  # type: ignore[arg-type]

    await store.async_load()
    await store.async_flush()

    assert store.diagnostics()["storage_key"] == "heima_snapshots"
    assert len(store.snapshots()) == 1
    assert store._store.key == "heima_snapshots"  # noqa: SLF001
    assert _FakeStore.saved == {"data": {"snapshots": [_snapshot().as_dict()]}}


@pytest.mark.asyncio
async def test_snapshot_store_appends_only_on_semantic_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.heima.runtime.inference import snapshot_store

    monkeypatch.setattr(snapshot_store, "Store", _FakeStore)
    store = SnapshotStore(object())  # type: ignore[arg-type]

    first_written = await store.async_append_if_changed(_snapshot(ts="2026-04-30T10:00:00+00:00"))
    duplicate_written = await store.async_append_if_changed(
        _snapshot(ts="2026-04-30T10:01:00+00:00")
    )
    changed_written = await store.async_append_if_changed(
        _snapshot(ts="2026-04-30T10:02:00+00:00", house_state="away")
    )

    assert first_written is True
    assert duplicate_written is False
    assert changed_written is True
    assert len(store.snapshots()) == 2


@pytest.mark.asyncio
async def test_snapshot_store_prunes_ttl_and_max_records(monkeypatch: pytest.MonkeyPatch) -> None:
    from custom_components.heima.runtime.inference import snapshot_store

    monkeypatch.setattr(snapshot_store, "Store", _FakeStore)
    monkeypatch.setattr(SnapshotStore, "MAX_RECORDS", 3)
    store = SnapshotStore(object())  # type: ignore[arg-type]
    old = _snapshot(ts="2025-12-01T10:00:00+00:00")
    fresh = _snapshot(ts="2026-04-30T10:00:00+00:00", house_state="away")

    await store.async_append(old)
    await store.async_append(fresh)
    store._evict_ttl(now=datetime(2026, 4, 30, 12, 0, tzinfo=UTC))  # noqa: SLF001

    assert store.snapshots() == [fresh]

    for index in range(SnapshotStore.MAX_RECORDS + 2):
        await store.async_append(
            _snapshot(
                ts=f"2026-04-30T10:{index % 60:02d}:00+00:00",
                house_state=f"state_{index}",
            )
        )

    assert len(store.snapshots()) == SnapshotStore.MAX_RECORDS
