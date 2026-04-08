from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.runtime.behaviors.base import HeimaBehavior
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


class _BoomBehavior(HeimaBehavior):
    @property
    def behavior_id(self) -> str:
        return "boom_behavior"

    def on_snapshot(self, snapshot) -> None:
        raise RuntimeError("boom")


def _engine() -> HeimaEngine:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    entry = SimpleNamespace(options={"notifications": {}})
    engine = HeimaEngine(hass=hass, entry=entry)
    engine._build_default_state()
    return engine


@pytest.mark.asyncio
async def test_behavior_exception_emits_system_behavior_error_event():
    engine = _engine()
    engine.register_behavior(_BoomBehavior())

    await engine.async_evaluate(reason="test_behavior_error")

    emitted = [evt for evt_type, evt in engine._hass.bus.events if evt_type == "heima_event"]
    assert emitted, "expected at least one heima_event"
    last = emitted[-1]
    assert last["type"] == "system.behavior_error"
    assert last["context"]["component"] == "behavior"
    assert last["context"]["behavior"] == "boom_behavior"
    assert last["context"]["hook"] == "on_snapshot"
