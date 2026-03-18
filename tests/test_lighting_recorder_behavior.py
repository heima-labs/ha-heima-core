"""Tests for LightingRecorderBehavior (learning system P8)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

from custom_components.heima.runtime.behaviors.lighting_recorder import LightingRecorderBehavior
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

_TS = "2026-03-10T08:00:00+00:00"
_LAST_CHANGED = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)


class _FakeStore:
    def __init__(self) -> None:
        self.events: list[HeimaEvent] = []

    async def async_append(self, event: HeimaEvent) -> None:
        self.events.append(event)


class _FakeBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}
        self.unsubscribed: list[str] = []

    def async_listen(self, event_type: str, callback) -> callable:
        self._handlers.setdefault(event_type, []).append(callback)

        def _unsub():
            self.unsubscribed.append(event_type)
            handlers = self._handlers.get(event_type, [])
            if callback in handlers:
                handlers.remove(callback)

        return _unsub

    async def fire(self, event_type: str, data: dict) -> None:
        for cb in self._handlers.get(event_type, []):
            result = cb(_FakeEvent(data))
            if asyncio.iscoroutine(result):
                await result


class _FakeEvent:
    def __init__(self, data: dict) -> None:
        self.data = data


class _FakeHass:
    def __init__(self) -> None:
        self.tasks: list = []
        self.bus = _FakeBus()

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def flush(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks)
            self.tasks.clear()


class _FakeEntry:
    def __init__(self, rooms: list | None = None) -> None:
        self.options = {"rooms": rooms or []}


class _FakeContextBuilder:
    def build(self, snapshot: DecisionSnapshot) -> EventContext:
        return EventContext(
            weekday=0,
            minute_of_day=480,
            month=3,
            house_state=snapshot.house_state,
            occupants_count=snapshot.people_count,
            occupied_rooms=tuple(snapshot.occupied_rooms),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        )


def _snapshot(house_state: str = "home") -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="s",
        ts=_TS,
        house_state=house_state,
        anyone_home=True,
        people_count=1,
        occupied_rooms=[],
        lighting_intents={},
        security_state="disarmed",
    )


def _state_event(
    entity_id: str,
    new_state: str,
    old_state: str | None = None,
    attributes: dict | None = None,
) -> dict:
    """Build state_changed event data dict."""
    new = MagicMock()
    new.state = new_state
    new.attributes = attributes or {}
    new.last_changed = _LAST_CHANGED

    old = None
    if old_state is not None:
        old = MagicMock()
        old.state = old_state

    return {
        "entity_id": entity_id,
        "new_state": new,
        "old_state": old,
    }


def _behavior(
    hass: _FakeHass,
    store: _FakeStore,
    entity_to_room: dict[str, str] | None = None,
    apply_ts: dict[str, float] | None = None,
) -> LightingRecorderBehavior:
    """Build behavior with mocked entity→room map and snapshot pre-set."""
    b = LightingRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
        lambda: apply_ts or {},
    )
    b._entity_to_room = entity_to_room or {"light.living_main": "living"}
    b._last_snapshot = _snapshot()
    return b


# ---------------------------------------------------------------------------
# Core recording logic
# ---------------------------------------------------------------------------

async def test_lighting_recorder_records_user_on():
    """User turning a light on → HeimaEvent with action='on'."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 1
    e = store.events[0]
    assert isinstance(e, HeimaEvent)
    assert e.event_type == "lighting"
    assert e.source == "user"
    assert e.data["room_id"] == "living"
    assert e.data["action"] == "on"


async def test_lighting_recorder_records_user_off():
    """User turning a light off → HeimaEvent with action='off'."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event("light.living_main", "off", old_state="on")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].data["action"] == "off"


async def test_lighting_recorder_captures_brightness_and_color_temp():
    """On event captures brightness and color_temp_kelvin from attributes."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event(
        "light.living_main", "on", old_state="off",
        attributes={"brightness": 128, "color_temp_kelvin": 3000},
    )
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert store.events[0].data["brightness"] == 128
    assert store.events[0].data["color_temp_kelvin"] == 3000


async def test_lighting_recorder_captures_rgb_color():
    """On event captures rgb_color tuple/list from attributes."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event(
        "light.living_main", "on", old_state="off",
        attributes={"rgb_color": [255, 100, 50]},
    )
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert store.events[0].data["rgb_color"] == [255, 100, 50]


async def test_lighting_recorder_no_attrs_on_off_action():
    """Off action → brightness/color_temp/rgb all None."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event("light.living_main", "off", old_state="on")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    d = store.events[0].data
    assert d["brightness"] is None
    assert d["color_temp_kelvin"] is None
    assert d["rgb_color"] is None


async def test_lighting_recorder_ignores_non_light_entity():
    """State changes for non-light entities are ignored."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store, entity_to_room={"switch.living": "living"})

    event_data = _state_event("switch.living", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_unknown_room():
    """Light entity not mapped to any room is ignored."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store, entity_to_room={"light.kitchen_spot": "kitchen"})

    event_data = _state_event("light.unmapped_entity", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_no_state_change():
    """State event where old and new state are the same is ignored."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event("light.living_main", "on", old_state="on")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_unavailable_state():
    """States not in ('on', 'off') like 'unavailable' are ignored."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event("light.living_main", "unavailable", old_state="on")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_heima_applied_within_ttl():
    """If Heima applied the room within 5s, state change is attributed to Heima."""
    import time
    hass = _FakeHass()
    store = _FakeStore()
    # Simulate recent Heima apply for "living"
    recent_apply_ts = {"living": time.time() - 2.0}  # 2s ago < 5s TTL
    b = _behavior(hass, store, apply_ts=recent_apply_ts)

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_records_after_heima_ttl_expired():
    """If Heima apply was more than 5s ago, the change is attributed to user."""
    import time
    hass = _FakeHass()
    store = _FakeStore()
    stale_apply_ts = {"living": time.time() - 10.0}  # 10s ago > 5s TTL
    b = _behavior(hass, store, apply_ts=stale_apply_ts)

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].source == "user"


async def test_lighting_recorder_ignores_without_snapshot():
    """No snapshot available → no event recorded."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)
    b._last_snapshot = None  # override

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_none_new_state():
    """event.data['new_state'] is None → no event recorded."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    data = {"entity_id": "light.living_main", "new_state": None, "old_state": None}
    await b._handle_state_changed(_FakeEvent(data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_context_has_house_state():
    """Recorded event context reflects snapshot house_state."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)
    b._last_snapshot = _snapshot(house_state="away")

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert store.events[0].context.house_state == "away"


# ---------------------------------------------------------------------------
# Lifecycle: async_setup / async_teardown
# ---------------------------------------------------------------------------

async def test_lighting_recorder_teardown_unsubscribes():
    """async_teardown cancels the state_changed listener."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)
    # Manually simulate a subscribed unsub callable
    unsub_called = []
    b._unsub = lambda: unsub_called.append(True)

    await b.async_teardown()

    assert unsub_called == [True]
    assert b._unsub is None


async def test_lighting_recorder_teardown_idempotent():
    """async_teardown with no subscription is safe to call."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)
    b._unsub = None  # already torn down

    await b.async_teardown()  # must not raise


async def test_lighting_recorder_on_options_reloaded_rebuilds_map():
    """on_options_reloaded updates entity→room map from new options."""
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store, entity_to_room={"light.old_entity": "old_room"})

    # Patch _build_entity_room_map to return a new map
    b._build_entity_room_map = lambda: {"light.new_entity": "new_room"}
    b.on_options_reloaded({})

    assert b._entity_to_room == {"light.new_entity": "new_room"}
