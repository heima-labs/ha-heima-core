"""Tests for runtime EventStore (learning system P1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime import event_store as event_store_module
from custom_components.heima.runtime.event_store import (
    EventContext,
    EventStore,
    HeimaEvent,
)


class _FakeStore:
    """Tiny in-memory replacement for HA Store."""

    def __init__(self, hass, version, key):  # noqa: ANN001, D401
        self._data = None
        self.saved = []

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data
        self.saved.append(data)

    def async_delay_save(self, data_func, delay):  # noqa: ARG002
        self._data = data_func()
        self.saved.append(self._data)


def _iso_now_minus(days: int = 0, minutes: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(days=days, minutes=minutes)).isoformat()


def _ctx(weekday: int = 0, minute: int = 480, house_state: str = "home") -> EventContext:
    return EventContext(
        weekday=weekday,
        minute_of_day=minute,
        month=3,
        house_state=house_state,
        occupants_count=1,
        occupied_rooms=(),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


def _presence(
    ts: str, transition: str = "arrive", weekday: int = 0, minute: int = 480
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="presence",
        context=_ctx(weekday=weekday, minute=minute),
        source=None,
        data={"transition": transition},
    )


def _heating(ts: str, temperature: float = 21.0, house_state: str = "home") -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="heating",
        context=_ctx(house_state=house_state),
        source="heima",
        data={"temperature_set": temperature},
    )


def _house_state(ts: str, from_state: str = "away", to_state: str = "home") -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="house_state",
        context=_ctx(),
        source=None,
        data={"from_state": from_state, "to_state": to_state},
    )


def _lighting(ts: str, entity_id: str = "light.living_main", room_id: str = "living") -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(),
        source="user",
        domain="lighting",
        subject_type="entity",
        subject_id=entity_id,
        room_id=room_id,
        correlation_id="ctx-123",
        data={
            "entity_id": entity_id,
            "room_id": room_id,
            "action": "on",
            "brightness": 128,
        },
    )


async def test_event_store_append_and_query(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    t1 = _iso_now_minus(minutes=3)
    t2 = _iso_now_minus(minutes=2)
    t3 = _iso_now_minus(minutes=1)
    await store.async_append(_presence(t1, "arrive", weekday=1, minute=420))
    await store.async_append(_heating(t2, temperature=20.0))
    await store.async_append(_house_state(t3))
    all_events = await store.async_query()
    assert len(all_events) == 3
    assert [e.ts for e in all_events] == [t1, t2, t3]


async def test_event_store_query_by_type(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    await store.async_append(_presence(_iso_now_minus(minutes=2)))
    await store.async_append(_heating(_iso_now_minus(minutes=1)))
    presence_only = await store.async_query(event_type="presence")
    assert len(presence_only) == 1
    assert presence_only[0].event_type == "presence"


async def test_event_store_query_by_room_and_subject(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    await store.async_append(
        HeimaEvent(
            ts=_iso_now_minus(minutes=2),
            event_type="room_signal_threshold",
            context=_ctx(),
            source=None,
            domain="sensor",
            subject_type="signal",
            subject_id="room_lux",
            room_id="studio",
            data={"from_bucket": "ok", "to_bucket": "dark"},
        )
    )
    await store.async_append(
        HeimaEvent(
            ts=_iso_now_minus(minutes=1),
            event_type="room_signal_threshold",
            context=_ctx(),
            source=None,
            domain="sensor",
            subject_type="signal",
            subject_id="room_humidity",
            room_id="bathroom",
            data={"from_bucket": "ok", "to_bucket": "high"},
        )
    )

    result = await store.async_query(
        event_type="room_signal_threshold",
        room_id="studio",
        subject_id="room_lux",
    )
    assert len(result) == 1
    assert result[0].room_id == "studio"
    assert result[0].subject_id == "room_lux"


async def test_event_store_query_since(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    old_ts = _iso_now_minus(minutes=10)
    mid_ts = _iso_now_minus(minutes=5)
    new_ts = _iso_now_minus(minutes=1)
    await store.async_append(_presence(old_ts))
    await store.async_append(_presence(mid_ts))
    await store.async_append(_presence(new_ts))
    result = await store.async_query(since=mid_ts)
    assert [e.ts for e in result] == [mid_ts, new_ts]


async def test_event_store_limit(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    await store.async_append(_presence(_iso_now_minus(minutes=3)))
    await store.async_append(_presence(_iso_now_minus(minutes=2)))
    await store.async_append(_presence(_iso_now_minus(minutes=1)))
    result = await store.async_query(limit=2)
    assert len(result) == 2


async def test_event_store_evicts_at_max(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    store.MAX_RECORDS = 5
    store._events = event_store_module.deque(maxlen=store.MAX_RECORDS)
    await store.async_load()
    for i in range(7):
        await store.async_append(_presence(_iso_now_minus(minutes=7 - i), minute=400 + i))
    result = await store.async_query()
    assert len(result) == 5


async def test_event_store_ttl_eviction_on_append(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    await store.async_append(_presence(_iso_now_minus(days=61), minute=100))
    await store.async_append(_presence(_iso_now_minus(minutes=1), minute=200))
    result = await store.async_query()
    assert len(result) == 1
    assert result[0].context.minute_of_day == 200


async def test_event_store_persist_and_reload(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store1 = EventStore(object())  # type: ignore[arg-type]
    await store1.async_load()
    event = _presence(_iso_now_minus(minutes=1), minute=333)
    await store1.async_append(event)
    await store1.async_flush()

    store2 = EventStore(object())  # type: ignore[arg-type]
    store2._store._data = store1._store._data  # copy persisted payload
    await store2.async_load()
    result = await store2.async_query()
    assert len(result) == 1
    assert result[0] == event


async def test_event_store_clear(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    await store.async_append(_presence(_iso_now_minus(minutes=1)))
    await store.async_clear()
    assert await store.async_query() == []


async def test_event_store_persists_generic_event_fields(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store1 = EventStore(object())  # type: ignore[arg-type]
    await store1.async_load()
    event = _lighting(_iso_now_minus(minutes=1))
    await store1.async_append(event)
    await store1.async_flush()

    store2 = EventStore(object())  # type: ignore[arg-type]
    store2._store._data = store1._store._data
    await store2.async_load()
    result = await store2.async_query(event_type="lighting")
    assert len(result) == 1
    reloaded = result[0]
    assert reloaded.domain == "lighting"
    assert reloaded.subject_type == "entity"
    assert reloaded.subject_id == "light.living_main"
    assert reloaded.room_id == "living"
    assert reloaded.correlation_id == "ctx-123"


async def test_event_store_backward_compat_legacy_presence(monkeypatch):
    """Old presence records without 'context' key are deserialized correctly."""
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    legacy_raw = {
        "data": {
            "events": [
                {
                    "ts": _iso_now_minus(minutes=5),
                    "event_type": "presence",
                    "transition": "arrive",
                    "weekday": 2,
                    "minute_of_day": 510,
                }
            ]
        }
    }
    store._store._data = legacy_raw
    await store.async_load()
    result = await store.async_query(event_type="presence")
    assert len(result) == 1
    e = result[0]
    assert e.data["transition"] == "arrive"
    assert e.context.weekday == 2
    assert e.context.minute_of_day == 510


async def test_event_store_backward_compat_legacy_heating(monkeypatch):
    """Old heating records with top-level house_state and env are migrated."""
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    legacy_raw = {
        "data": {
            "events": [
                {
                    "ts": _iso_now_minus(minutes=5),
                    "event_type": "heating",
                    "house_state": "home",
                    "temperature_set": 21.5,
                    "source": "user",
                    "env": {"sensor.outdoor_temp": "10"},
                }
            ]
        }
    }
    store._store._data = legacy_raw
    await store.async_load()
    result = await store.async_query(event_type="heating")
    assert len(result) == 1
    e = result[0]
    assert e.data["temperature_set"] == 21.5
    assert e.source == "user"
    assert e.context.house_state == "home"
    assert e.data["signals"]["sensor.outdoor_temp"] == "10"
