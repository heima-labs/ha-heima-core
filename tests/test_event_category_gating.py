from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.runtime.engine import HeimaEngine


class _FakeStateObj:
    def __init__(self, state: str):
        self.state = state


class _FakeStates:
    def __init__(self):
        self._values: dict[str, str] = {}

    def get(self, entity_id: str):
        value = self._values.get(entity_id)
        if value is None:
            return None
        return _FakeStateObj(value)


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, dict(data)))


class _FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, dict(data), blocking))

    def async_services(self):
        return {"notify": {}}


def _engine(notifications: dict | None = None) -> HeimaEngine:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    entry = SimpleNamespace(options={"notifications": dict(notifications or {})})
    engine = HeimaEngine(hass=hass, entry=entry)
    engine._build_default_state()
    return engine


@pytest.mark.asyncio
async def test_house_state_events_disabled_by_default():
    engine = _engine()
    emitted = await engine.async_emit_external_event(
        event_type="house_state.changed",
        key="house_state.changed",
        severity="info",
        title="House state changed",
        message="x",
        context={"from": "away", "to": "home", "reason": "default"},
    )
    assert emitted is True
    assert engine._hass.bus.events[-1][1]["type"] == "house_state.changed"
    assert engine._events_domain.suppressed_event_categories["house_state"] == 1


@pytest.mark.asyncio
async def test_system_events_always_enabled_even_if_not_listed():
    engine = _engine({"enabled_event_categories": []})
    emitted = await engine.async_emit_external_event(
        event_type="system.engine_disabled",
        key="system.engine_disabled",
        severity="info",
        title="Engine disabled",
        message="x",
        context={"reason": "engine_enabled_false"},
    )
    assert emitted is True
    assert engine._hass.bus.events[-1][1]["type"] == "system.engine_disabled"


@pytest.mark.asyncio
async def test_lighting_events_can_be_disabled():
    engine = _engine({"enabled_event_categories": ["people", "security"]})
    emitted = await engine.async_emit_external_event(
        event_type="lighting.scene_missing",
        key="lighting.scene_missing.room.intent",
        severity="warning",
        title="Missing",
        message="x",
        context={"room": "room", "intent": "scene_evening", "expected_scene": "scene_evening"},
    )
    assert emitted is True
    assert engine._hass.bus.events[-1][1]["type"] == "lighting.scene_missing"
    assert engine._events_domain.suppressed_event_categories["lighting"] == 1


@pytest.mark.asyncio
async def test_reaction_events_are_disabled_by_default():
    engine = _engine()
    emitted = await engine.async_emit_external_event(
        event_type="reaction.fired",
        key="reaction.fired.test",
        severity="info",
        title="Reaction fired",
        message="x",
        context={"reaction_id": "test"},
    )
    assert emitted is True
    assert engine._hass.bus.events[-1][1]["type"] == "reaction.fired"
    assert engine._events_domain.suppressed_event_categories["reaction"] == 1


@pytest.mark.asyncio
async def test_reaction_events_can_be_explicitly_enabled():
    engine = _engine({"enabled_event_categories": ["reaction"]})
    emitted = await engine.async_emit_external_event(
        event_type="reaction.fired",
        key="reaction.fired.test",
        severity="info",
        title="Reaction fired",
        message="x",
        context={"reaction_id": "test"},
    )
    assert emitted is True
    assert engine._hass.bus.events[-1][1]["type"] == "reaction.fired"


@pytest.mark.asyncio
async def test_custom_debug_category_remains_enabled():
    engine = _engine({"enabled_event_categories": []})
    emitted = await engine.async_emit_external_event(
        event_type="debug.manual_test",
        key="debug.manual_test",
        severity="info",
        title="Debug",
        message="x",
        context={},
    )
    assert emitted is True
    assert engine._hass.bus.events[-1][1]["type"] == "debug.manual_test"
