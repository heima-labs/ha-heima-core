"""Tests for runtime EventStore (learning system P1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime import event_store as event_store_module
from custom_components.heima.runtime.event_store import (
    EventStore,
    HeatingEvent,
    HouseStateEvent,
    PresenceEvent,
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


def _presence(ts: str, transition: str = "arrive", weekday: int = 0, minute: int = 480) -> PresenceEvent:
    return PresenceEvent(
        ts=ts,
        event_type="presence",
        transition=transition,  # type: ignore[arg-type]
        weekday=weekday,
        minute_of_day=minute,
    )


async def test_event_store_append_and_query(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    t1 = _iso_now_minus(minutes=3)
    t2 = _iso_now_minus(minutes=2)
    t3 = _iso_now_minus(minutes=1)
    await store.async_append(_presence(t1, "arrive", weekday=1, minute=420))
    await store.async_append(
        HeatingEvent(
            ts=t2, event_type="heating", house_state="home", temperature_set=20.0, source="heima"
        )
    )
    await store.async_append(HouseStateEvent(ts=t3, event_type="house_state", from_state="away", to_state="home"))
    all_events = await store.async_query()
    assert len(all_events) == 3
    assert [e.ts for e in all_events] == [t1, t2, t3]


async def test_event_store_query_by_type(monkeypatch):
    monkeypatch.setattr(event_store_module, "Store", _FakeStore)
    store = EventStore(object())  # type: ignore[arg-type]
    await store.async_load()
    await store.async_append(_presence(_iso_now_minus(minutes=2)))
    await store.async_append(
        HeatingEvent(
            ts=_iso_now_minus(minutes=1),
            event_type="heating",
            house_state="home",
            temperature_set=21.0,
            source="user",
        )
    )
    presence_only = await store.async_query(event_type="presence")
    assert len(presence_only) == 1
    assert presence_only[0].event_type == "presence"


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
    assert result[0].minute_of_day == 200


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

