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
    context_id: str | None = None,
) -> dict:
    """Build state_changed event data dict."""
    new = MagicMock()
    new.state = new_state
    new.attributes = attributes or {}
    new.last_changed = _LAST_CHANGED
    new.context = MagicMock(id=context_id) if context_id else None

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
    apply_state: dict | None = None,
) -> LightingRecorderBehavior:
    """Build behavior with mocked entity→room map and snapshot pre-set."""
    b = LightingRecorderBehavior(
        hass,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeContextBuilder(),  # type: ignore[arg-type]
        _FakeEntry(),  # type: ignore[arg-type]
        lambda: apply_state or {"rooms": {}, "entities": {}},
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
    assert e.domain == "lighting"
    assert e.subject_type == "entity"
    assert e.subject_id == "light.living_main"
    assert e.room_id == "living"
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
    recent_apply_state = {"rooms": {"living": time.monotonic() - 2.0}, "entities": {}}
    b = _behavior(hass, store, apply_state=recent_apply_state)

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_records_after_heima_ttl_expired():
    """If Heima apply was more than 5s ago, the change is attributed to user."""
    import time
    hass = _FakeHass()
    store = _FakeStore()
    stale_apply_state = {"rooms": {"living": time.monotonic() - 10.0}, "entities": {}}
    b = _behavior(hass, store, apply_state=stale_apply_state)

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


async def test_lighting_recorder_uses_context_id_as_correlation_id():
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store)

    event_data = _state_event(
        "light.living_main",
        "on",
        old_state="off",
        context_id="ctx-abc",
    )
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert store.events[0].correlation_id == "ctx-abc"


async def test_lighting_recorder_ignores_recent_heima_entity_apply():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(
        hass,
        store,
        apply_state={
            "rooms": {},
            "entities": {
                "light.living_main": {
                    "room_id": "living",
                    "action": "light.turn_on",
                    "applied_ts": time.monotonic() - 2.0,
                    "correlation_id": "lighting-apply:1",
                }
            },
        },
    )

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_recent_scene_entity_apply():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(
        hass,
        store,
        apply_state={
            "rooms": {"living": time.monotonic() - 1.0},
            "entities": {
                "light.living_main": {
                    "room_id": "living",
                    "action": "scene.turn_on",
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "lighting-apply:scene-1",
                }
            },
        },
    )

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_ignores_recent_script_batch_apply():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(
        hass,
        store,
        apply_state={
            "rooms": {},
            "entities": {},
            "scripts": {
                "script.preheat_home": {
                    "target": "script.preheat_home",
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "script-apply:1",
                }
            },
        },
    )

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


async def test_lighting_recorder_does_not_ignore_script_batch_for_other_room():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(
        hass,
        store,
        apply_state={
            "rooms": {},
            "entities": {},
            "scripts": {
                "script.bathroom_fan": {
                    "target": "script.bathroom_fan",
                    "room_id": "bathroom",
                    "expected_entity_ids": ["light.bathroom_main"],
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "script-apply:2",
                }
            },
        },
    )

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 1
    assert store.events[0].source == "user"


async def test_lighting_recorder_uses_expected_domains_with_room_scope():
    import time

    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(
        hass,
        store,
        entity_to_room={"light.living_main": "living", "switch.living_fan": "living"},
        apply_state={
            "rooms": {},
            "entities": {},
            "scripts": {
                "script.living_lights": {
                    "target": "script.living_lights",
                    "room_id": "living",
                    "expected_domains": ["light"],
                    "expected_subject_ids": [],
                    "expected_entity_ids": [],
                    "applied_ts": time.monotonic() - 1.0,
                    "correlation_id": "script-apply:3",
                }
            },
        },
    )

    event_data = _state_event("light.living_main", "on", old_state="off")
    await b._handle_state_changed(_FakeEvent(event_data))
    await hass.flush()

    assert len(store.events) == 0


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


async def test_lighting_recorder_on_options_reloaded_subscribes_when_map_becomes_non_empty():
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store, entity_to_room={})
    b._unsub = None
    b._build_entity_room_map = lambda: {"light.new_entity": "new_room"}

    b.on_options_reloaded({})

    assert b._entity_to_room == {"light.new_entity": "new_room"}
    assert b._unsub is not None


async def test_lighting_recorder_on_options_reloaded_unsubscribes_when_map_becomes_empty():
    hass = _FakeHass()
    store = _FakeStore()
    b = _behavior(hass, store, entity_to_room={"light.old_entity": "old_room"})
    unsub_called: list[bool] = []
    b._unsub = lambda: unsub_called.append(True)
    b._build_entity_room_map = lambda: {}

    b.on_options_reloaded({})

    assert b._entity_to_room == {}
    assert unsub_called == [True]
    assert b._unsub is None
