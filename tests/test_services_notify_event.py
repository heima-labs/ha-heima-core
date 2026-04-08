from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.heima.const import (
    DOMAIN,
    SERVICE_COMMAND,
    SERVICE_SET_MODE,
    SERVICE_SET_OVERRIDE,
)
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.services import (
    _coordinators_for_target,
    _validate_command,
    async_register_services,
)


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
        return None


class _FakeServicesRegistry:
    def __init__(self):
        self._handlers: dict[tuple[str, str], object] = {}
        self.calls: list[tuple[str, str, dict, bool]] = []

    def async_register(self, domain, service, handler, schema=None):
        self._handlers[(domain, service)] = handler

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, dict(data), blocking))
        return None

    def async_services(self):
        return {
            "notify": {
                "mobile_app_test": object(),
                "mobile_app_alias_test": object(),
            }
        }

    def handler(self, domain, service):
        return self._handlers[(domain, service)]


class _FakeCoordinator:
    def __init__(self, engine, entry_id="entry1"):
        self.engine = engine
        self.entry = SimpleNamespace(entry_id=entry_id)

    async def async_emit_event(self, **kwargs):
        return await self.engine.async_emit_external_event(
            event_type=kwargs["event_type"],
            key=kwargs["key"],
            severity=kwargs["severity"],
            title=kwargs["title"],
            message=kwargs["message"],
            context=kwargs.get("context") or {},
        )

    async def async_request_evaluation(self, reason: str):
        return None

    async def async_upsert_configured_reactions(self, configured_updates, *, label_updates=None):
        self.last_configured_updates = configured_updates
        self.last_label_updates = label_updates
        return None

    async def async_set_house_state_override(self, *, mode: str, enabled: bool):
        action, previous, current = self.engine.set_house_state_override(
            mode=mode,
            enabled=enabled,
            source="service:heima.set_mode",
        )
        await self.engine.async_emit_external_event(
            event_type="system.house_state_override_changed",
            key=(
                "system.house_state_override_changed:"
                f"{previous or 'none'}->{current or 'none'}:{action}"
            ),
            severity="info",
            title="House-state override changed",
            message=f"House-state override {action}: {previous or 'none'} -> {current or 'none'}.",
            context={
                "previous": previous,
                "current": current,
                "source": "service:heima.set_mode",
                "action": action,
            },
        )
        await self.engine.async_evaluate(reason=f"service:set_mode:{mode}:{enabled}")
        return action


def test_validate_command_rejects_unknown_command():
    with pytest.raises(ServiceValidationError):
        _validate_command("definitely_unknown")


def test_coordinators_for_target_filters_by_entry_id(monkeypatch):
    c1 = SimpleNamespace(entry=SimpleNamespace(entry_id="entry-a"))
    c2 = SimpleNamespace(entry=SimpleNamespace(entry_id="entry-b"))
    hass = SimpleNamespace()
    monkeypatch.setattr(
        "custom_components.heima.services._iter_coordinators",
        lambda _hass: iter([c1, c2]),
    )

    assert _coordinators_for_target(hass, {}) == [c1, c2]
    assert _coordinators_for_target(hass, {"entry_id": "entry-b"}) == [c2]


@pytest.mark.asyncio
async def test_heima_command_notify_event_uses_pipeline_and_updates_sensors(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(
        data={DOMAIN: {}},
        services=services,
        bus=_FakeBus(),
        states=_FakeStates(),
    )

    entry = SimpleNamespace(
        options={
            "notifications": {
                "recipients": {"stefano": ["mobile_app_test", "mobile_app_alias_test"]},
                "recipient_groups": {"family": ["stefano"]},
                "route_targets": ["family"],
                "dedup_window_s": 60,
                "rate_limit_per_key_s": 300,
            }
        }
    )
    engine = HeimaEngine(hass=hass, entry=entry)
    engine._build_default_state()
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "notify_event",
                "target": {},
                "params": {
                    "type": "debug.manual_test",
                    "key": "debug.manual_test",
                    "severity": "info",
                    "title": "Test",
                    "message": "hello",
                    "context": {"source": "test"},
                },
            }
        )
    )

    # Event bus fired through pipeline
    assert hass.bus.events
    assert hass.bus.events[-1][0] == "heima_event"
    assert hass.bus.events[-1][1]["type"] == "debug.manual_test"

    # Routed to notify.*
    notify_calls = [c for c in services.calls if c[0] == "notify"]
    called_services = [service for _domain, service, _data, _blocking in notify_calls]
    assert called_services == ["mobile_app_test", "mobile_app_alias_test"]
    _, _, notify_payload, _ = notify_calls[-1]
    assert notify_payload["title"] == "Test"
    assert notify_payload["message"] == "hello"
    assert "data" not in notify_payload  # metadata available on HA event bus, not in notify payload

    # Canonical sensors updated by the same pipeline
    assert engine.state.get_sensor("heima_last_event") == "debug.manual_test"
    last_event_attrs = engine.state.get_sensor_attributes("heima_last_event") or {}
    assert last_event_attrs["type"] == "debug.manual_test"
    assert last_event_attrs["severity"] == "info"
    assert last_event_attrs["title"] == "Test"
    assert last_event_attrs["message"] == "hello"
    assert last_event_attrs["context"] == {"source": "test"}
    stats_state = engine.state.get_sensor("heima_event_stats")
    assert isinstance(stats_state, str)
    assert "emitted=1" in stats_state
    attrs = engine.state.get_sensor_attributes("heima_event_stats") or {}
    assert attrs.get("last_event", {}).get("type") == "debug.manual_test"


@pytest.mark.asyncio
async def test_heima_set_mode_sets_and_clears_final_house_state_override(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(
        data={DOMAIN: {}},
        services=services,
        bus=_FakeBus(),
        states=_FakeStates(),
    )

    entry = SimpleNamespace(options={})
    engine = HeimaEngine(hass=hass, entry=entry)
    engine._build_default_state()
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._iter_coordinators",
        lambda _hass: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_SET_MODE)
    await handler(SimpleNamespace(data={"mode": "vacation", "state": True}))

    assert engine.snapshot.house_state == "vacation"
    assert engine.state.get_sensor("heima_house_state") == "vacation"
    assert engine.state.get_sensor("heima_house_state_reason") == "manual_override:vacation"
    assert engine.diagnostics()["house_state"]["override"]["house_state_override"] == "vacation"
    assert hass.bus.events[-1][1]["type"] == "system.house_state_override_changed"
    assert hass.bus.events[-1][1]["context"]["action"] == "set"

    await handler(SimpleNamespace(data={"mode": "vacation", "state": False}))

    assert engine.snapshot.house_state == "away"
    assert engine.state.get_sensor("heima_house_state") == "away"
    assert engine.diagnostics()["house_state"]["override"]["house_state_override"] is None
    override_events = [
        payload
        for event_type, payload in hass.bus.events
        if event_type == "heima_event" and payload["type"] == "system.house_state_override_changed"
    ]
    assert override_events[-1]["context"]["action"] == "clear"


@pytest.mark.asyncio
async def test_heima_command_learning_run_calls_coordinator(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(
        data={DOMAIN: {}},
        services=services,
        bus=_FakeBus(),
        states=_FakeStates(),
    )

    coordinator = SimpleNamespace(async_run_learning_now=AsyncMock())

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(SimpleNamespace(data={"command": "learning_run", "target": {}, "params": {}}))

    coordinator.async_run_learning_now.assert_awaited_once()


@pytest.mark.asyncio
async def test_heima_command_mute_reaction_type_calls_engine(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(
        data={DOMAIN: {}},
        services=services,
        bus=_FakeBus(),
        states=_FakeStates(),
    )
    coordinator = SimpleNamespace(engine=SimpleNamespace(mute_reactions_by_type=MagicMock(return_value=["sec1"])))

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "mute_reaction_type",
                "target": {},
                "params": {"reaction_type": "vacation_presence_simulation"},
            }
        )
    )

    coordinator.engine.mute_reactions_by_type.assert_called_once_with("vacation_presence_simulation")


@pytest.mark.asyncio
async def test_heima_command_unmute_reaction_type_calls_engine(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(
        data={DOMAIN: {}},
        services=services,
        bus=_FakeBus(),
        states=_FakeStates(),
    )
    coordinator = SimpleNamespace(engine=SimpleNamespace(unmute_reactions_by_type=MagicMock(return_value=["sec1"])))

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "unmute_reaction_type",
                "target": {},
                "params": {"reaction_type": "vacation_presence_simulation"},
            }
        )
    )

    coordinator.engine.unmute_reactions_by_type.assert_called_once_with("vacation_presence_simulation")


@pytest.mark.asyncio
async def test_heima_command_upsert_configured_reactions_calls_coordinator(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(
        data={DOMAIN: {}},
        services=services,
        bus=_FakeBus(),
        states=_FakeStates(),
    )
    entry = SimpleNamespace(options={})
    engine = HeimaEngine(hass=hass, entry=entry)
    engine._build_default_state()
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "upsert_configured_reactions",
                "target": {},
                "params": {
                    "configured": {
                        "r-collision": {
                            "reaction_class": "LightingScheduleReaction",
                            "room_id": "living",
                        }
                    },
                    "labels": {"r-collision": "Collision reaction"},
                },
            }
        )
    )

    assert coordinator.last_configured_updates == {
        "r-collision": {
            "reaction_class": "LightingScheduleReaction",
            "room_id": "living",
        }
    }
    assert coordinator.last_label_updates == {"r-collision": "Collision reaction"}


@pytest.mark.asyncio
async def test_heima_command_recompute_now_requests_evaluation(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    coordinator = SimpleNamespace(async_request_evaluation=AsyncMock())

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(SimpleNamespace(data={"command": "recompute_now", "target": {}, "params": {}}))

    coordinator.async_request_evaluation.assert_awaited_once_with(reason="service:recompute_now")


@pytest.mark.asyncio
async def test_heima_command_set_lighting_intent_updates_matching_select(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={}))
    engine._build_default_state()
    engine.state.set_select("heima_lighting_intent_living", "auto")
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "set_lighting_intent",
                "target": {"zone_id": "living"},
                "params": {"intent": "scene_evening"},
            }
        )
    )

    assert engine.state.get_select("heima_lighting_intent_living") == "scene_evening"


@pytest.mark.asyncio
async def test_heima_command_set_security_intent_updates_select(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={"security": {"enabled": True}}))
    engine._build_default_state()
    engine.state.set_select("heima_security_intent", "disarmed")
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "set_security_intent",
                "target": {},
                "params": {"intent": "armed_away"},
            }
        )
    )

    assert engine.state.get_select("heima_security_intent") == "armed_away"


@pytest.mark.asyncio
async def test_heima_command_set_room_lighting_hold_updates_binary(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={"lighting_zones": [{"zone_id": "living", "rooms": ["studio"]}]}))
    engine._build_default_state()
    engine.state.set_binary("heima_lighting_hold_studio", False)
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    await handler(
        SimpleNamespace(
            data={
                "command": "set_room_lighting_hold",
                "target": {"room_id": "studio"},
                "params": {"state": True},
            }
        )
    )

    assert engine.state.get_binary("heima_lighting_hold_studio") is True


@pytest.mark.asyncio
async def test_heima_command_seed_lighting_events_rejects_invalid_action(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    coordinator = SimpleNamespace(async_seed_lighting_events=AsyncMock(return_value=0))

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    with pytest.raises(ServiceValidationError):
        await handler(
            SimpleNamespace(
                data={
                    "command": "seed_lighting_events",
                    "target": {},
                    "params": {
                        "entity_id": "light.living_main",
                        "room_id": "living",
                        "action": "blink",
                    },
                }
            )
        )


@pytest.mark.asyncio
async def test_heima_command_upsert_configured_reactions_rejects_invalid_payload(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    coordinator = SimpleNamespace(async_upsert_configured_reactions=AsyncMock())

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._coordinators_for_target",
        lambda _hass, _target: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_COMMAND)
    with pytest.raises(ServiceValidationError):
        await handler(
            SimpleNamespace(
                data={
                    "command": "upsert_configured_reactions",
                    "target": {},
                    "params": {"configured": {}, "labels": []},
                }
            )
        )


@pytest.mark.asyncio
async def test_heima_set_override_person_updates_override_select(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={"people_named": [{"slug": "alex", "presence_method": "manual"}]}))
    engine._build_default_state()
    engine.state.set_select("heima_person_alex_override", "auto")
    coordinator = _FakeCoordinator(engine)

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._iter_coordinators",
        lambda _hass: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_SET_OVERRIDE)
    await handler(SimpleNamespace(data={"scope": "person", "id": "alex", "override": "force_home"}))

    assert engine.state.get_select("heima_person_alex_override") == "force_home"


@pytest.mark.asyncio
async def test_heima_set_override_rejects_unknown_scope(monkeypatch):
    services = _FakeServicesRegistry()
    hass = SimpleNamespace(data={DOMAIN: {}}, services=services, bus=_FakeBus(), states=_FakeStates())
    coordinator = SimpleNamespace()

    await async_register_services(hass)
    monkeypatch.setattr(
        "custom_components.heima.services._iter_coordinators",
        lambda _hass: [coordinator],
    )

    handler = services.handler(DOMAIN, SERVICE_SET_OVERRIDE)
    with pytest.raises(ServiceValidationError):
        await handler(SimpleNamespace(data={"scope": "unknown", "id": "x", "override": True}))
