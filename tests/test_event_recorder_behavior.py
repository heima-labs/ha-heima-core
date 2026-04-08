"""Tests for EventRecorderBehavior (learning system P1b)."""

from __future__ import annotations

import asyncio

from custom_components.heima.runtime.behaviors.event_recorder import EventRecorderBehavior
from custom_components.heima.runtime.event_store import EventContext
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _FakeStore:
    def __init__(self) -> None:
        self.events = []

    async def async_append(self, event):
        self.events.append(event)


class _FakeHass:
    def __init__(self) -> None:
        self.tasks = []
        self.states = type("_S", (), {"get": lambda self, _: None})()

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


def _minimal_ctx() -> EventContext:
    return EventContext(
        weekday=0, minute_of_day=480, month=3,
        house_state="home", occupants_count=1, occupied_rooms=(),
        outdoor_lux=None, outdoor_temp=None, weather_condition=None, signals={},
    )


class _FakeContextBuilder:
    def build(self, snapshot):  # noqa: ARG002
        return _minimal_ctx()


def _snapshot(*, ts: str, anyone_home: bool, house_state: str) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="s",
        ts=ts,
        house_state=house_state,
        anyone_home=anyone_home,
        people_count=1 if anyone_home else 0,
        occupied_rooms=[],
        lighting_intents={},
        security_state="disarmed",
    )


async def test_event_recorder_presence_arrive_and_depart():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = EventRecorderBehavior(hass, store, _FakeContextBuilder())  # type: ignore[arg-type]

    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T06:00:00+00:00", anyone_home=False, house_state="away")
    )
    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T06:05:00+00:00", anyone_home=True, house_state="home")
    )
    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T06:10:00+00:00", anyone_home=False, house_state="away")
    )
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    transitions = [e.data["transition"] for e in store.events if e.event_type == "presence"]
    assert transitions == ["arrive", "depart"]


async def test_event_recorder_house_state_transition():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = EventRecorderBehavior(hass, store, _FakeContextBuilder())  # type: ignore[arg-type]

    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T08:00:00+00:00", anyone_home=True, house_state="home")
    )
    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T08:30:00+00:00", anyone_home=True, house_state="working")
    )
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    changes = [e for e in store.events if e.event_type == "house_state"]
    assert len(changes) == 1
    assert changes[0].data["from_state"] == "home"
    assert changes[0].data["to_state"] == "working"


async def test_event_recorder_no_events_for_stable_snapshot():
    hass = _FakeHass()
    store = _FakeStore()
    behavior = EventRecorderBehavior(hass, store, _FakeContextBuilder())  # type: ignore[arg-type]

    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T09:00:00+00:00", anyone_home=True, house_state="home")
    )
    behavior.on_snapshot(
        _snapshot(ts="2026-03-10T09:10:00+00:00", anyone_home=True, house_state="home")
    )
    if hass.tasks:
        await asyncio.gather(*hass.tasks)

    assert store.events == []

