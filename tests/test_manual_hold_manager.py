"""Tests for the shared manual-hold manager."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.contracts import ApplyPlan, ApplyStep
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.manual_hold import (
    ManualHoldManager,
    ManualHoldReason,
    ManualHoldScope,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_manual_hold_scope_key_is_stable() -> None:
    scope = ManualHoldScope("switch", "entity", "switch.front_door_privacy")

    assert scope.key == "switch:entity:switch.front_door_privacy"


def test_manual_hold_manager_reports_empty_diagnostics() -> None:
    manager = ManualHoldManager(monotonic=_Clock())

    assert manager.diagnostics() == {
        "active_holds": [],
        "pending_applies": {"total": 0, "by_domain": {}, "items": []},
    }


def test_manual_hold_manager_activates_and_expires_hold() -> None:
    clock = _Clock()
    manager = ManualHoldManager(monotonic=clock)
    scope = ManualHoldScope("switch", "entity", "switch.front_door_privacy")

    manager.activate_hold(
        scope,
        ManualHoldReason("external_off", "switch.front_door_privacy"),
        expires_in_s=10,
        release_policy="timer",
    )

    assert manager.held_reason_for_scope(scope) == (
        "manual_hold:switch:entity:switch.front_door_privacy:external_off"
    )
    clock.advance(11)
    assert manager.held_reason_for_scope(scope) == ""


def test_manual_hold_manager_registers_and_consumes_light_pending_apply() -> None:
    clock = _Clock()
    manager = ManualHoldManager(monotonic=clock)
    step = ApplyStep(
        domain="light",
        target="light.studio_main",
        action="light.turn_on",
        params={
            "entity_id": "light.studio_main",
            "brightness": 144,
            "color_temp_kelvin": 3000,
        },
        source="reaction:smart-studio",
    )

    manager.register_pending_apply(step)

    pending = manager.diagnostics()["pending_applies"]
    assert pending["total"] == 1
    assert pending["by_domain"] == {"light": 1}
    assert pending["items"][0]["entity_id"] == "light.studio_main"
    assert pending["items"][0]["expected_state"] == "on"
    assert manager.consume_pending_apply(
        "light.studio_main",
        SimpleNamespace(
            state="on",
            attributes={"brightness": 148, "color_temp_kelvin": 3050},
        ),
    )
    assert manager.diagnostics()["pending_applies"] == {"total": 0, "by_domain": {}, "items": []}


def test_manual_hold_manager_classifies_owned_and_external_light_changes() -> None:
    clock = _Clock()
    manager = ManualHoldManager(monotonic=clock)
    step = ApplyStep(
        domain="light",
        target="light.studio_main",
        action="light.turn_off",
        params={"entity_id": "light.studio_main"},
    )
    manager.register_pending_apply(step)

    assert (
        manager.classify_state_change(
            "light.studio_main",
            SimpleNamespace(state="off", attributes={}),
        )
        == "heima_owned"
    )
    assert (
        manager.classify_state_change(
            "light.studio_main",
            SimpleNamespace(state="off", attributes={}),
        )
        == "external"
    )


def test_manual_hold_manager_rejects_expired_pending_apply() -> None:
    clock = _Clock()
    manager = ManualHoldManager(monotonic=clock)
    step = ApplyStep(
        domain="switch",
        target="switch.front_door_privacy",
        action="switch.turn_off",
        params={"entity_id": "switch.front_door_privacy"},
    )

    manager.register_pending_apply(step)
    clock.advance(6)

    assert not manager.consume_pending_apply(
        "switch.front_door_privacy",
        SimpleNamespace(state="off", attributes={}),
    )
    assert manager.diagnostics()["pending_applies"] == {"total": 0, "by_domain": {}, "items": []}


def test_manual_hold_manager_returns_step_hold_reason_for_entity_scope() -> None:
    manager = ManualHoldManager(monotonic=_Clock())
    scope = ManualHoldScope("switch", "entity", "switch.front_door_privacy")
    manager.activate_hold(scope, ManualHoldReason("helper_on", "input_boolean.privacy_hold"))
    step = ApplyStep(
        domain="switch",
        target="switch.front_door_privacy",
        action="switch.turn_on",
        params={"entity_id": "switch.front_door_privacy"},
    )

    assert manager.held_reason_for_step(step) == (
        "manual_hold:switch:entity:switch.front_door_privacy:helper_on"
    )


def test_engine_diagnostics_include_manual_hold_manager() -> None:
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._manual_hold_manager = ManualHoldManager(monotonic=_Clock())
    engine._snapshot = DecisionSnapshot.empty()
    engine._active_constraints = set()
    engine._apply_plan = ApplyPlan.empty()
    engine._calendar_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._lighting_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._heating_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._security_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._house_state_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._people_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._occupancy_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._events_domain = SimpleNamespace(diagnostics=lambda: {})
    engine._normalizer = SimpleNamespace(diagnostics=lambda: {})
    engine._behaviors = []
    engine._reactions = []
    engine._muted_reactions = set()
    engine._last_signal_buckets = {}
    engine._health = SimpleNamespace(as_dict=lambda: {})
    engine._current_security_camera_evidence = None

    assert engine.diagnostics()["manual_hold"] == {
        "active_holds": [],
        "pending_applies": {"total": 0, "by_domain": {}, "items": []},
    }


def test_engine_manual_hold_filter_blocks_held_entity_step() -> None:
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._manual_hold_manager = ManualHoldManager(monotonic=_Clock())
    scope = ManualHoldScope("switch", "entity", "switch.front_door_privacy")
    engine._manual_hold_manager.activate_hold(
        scope,
        ManualHoldReason("helper_on", "input_boolean.front_door_privacy_hold"),
    )
    plan = ApplyPlan(
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.front_door_privacy",
                action="switch.turn_on",
                params={"entity_id": "switch.front_door_privacy"},
            )
        ]
    )

    filtered = engine._dispatch_manual_hold_filter(plan)

    assert filtered.plan_id == plan.plan_id
    assert filtered.steps[0].blocked_by == (
        "manual_hold:switch:entity:switch.front_door_privacy:helper_on"
    )


def test_engine_manual_hold_filter_does_not_overwrite_existing_blocker() -> None:
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._manual_hold_manager = ManualHoldManager(monotonic=_Clock())
    scope = ManualHoldScope("switch", "entity", "switch.front_door_privacy")
    engine._manual_hold_manager.activate_hold(scope, ManualHoldReason("helper_on", "hold"))
    plan = ApplyPlan(
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.front_door_privacy",
                action="switch.turn_on",
                params={"entity_id": "switch.front_door_privacy"},
                blocked_by="security.armed_away",
            )
        ]
    )

    filtered = engine._dispatch_manual_hold_filter(plan)

    assert filtered.steps[0].blocked_by == "security.armed_away"


def _privacy_engine(*, hold_state: str | None = None) -> HeimaEngine:
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._manual_hold_manager = ManualHoldManager(monotonic=_Clock())
    engine._entry = SimpleNamespace(
        options={
            "security": {
                "camera_evidence_sources": [
                    {
                        "id": "front",
                        "role": "entry",
                        "privacy_entity": "switch.front_privacy",
                        "manual_hold_entity": "input_boolean.front_privacy_hold",
                    }
                ]
            }
        }
    )
    states = {}
    if hold_state is not None:
        states["input_boolean.front_privacy_hold"] = SimpleNamespace(state=hold_state)
    engine._hass = MagicMock()
    engine._hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
    engine._state = SimpleNamespace(get_binary=lambda _key: False)
    engine._behaviors = []
    return engine


def test_engine_camera_privacy_manual_hold_entity_blocks_switch_step() -> None:
    engine = _privacy_engine(hold_state="on")
    plan = ApplyPlan(
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.front_privacy",
                action="switch.turn_on",
                params={"entity_id": "switch.front_privacy"},
            )
        ]
    )

    filtered = engine._dispatch_apply_filter(plan, DecisionSnapshot.empty())

    assert (
        filtered.steps[0].blocked_by == "manual_hold:switch:entity:switch.front_privacy:helper_on"
    )


def test_engine_camera_privacy_heima_owned_switch_change_does_not_hold() -> None:
    engine = _privacy_engine(hold_state="off")
    step = ApplyStep(
        domain="switch",
        target="switch.front_privacy",
        action="switch.turn_on",
        params={"entity_id": "switch.front_privacy"},
    )
    engine._register_pending_apply_for_step(step)

    engine.handle_camera_privacy_state_changed(
        SimpleNamespace(
            data={
                "entity_id": "switch.front_privacy",
                "new_state": SimpleNamespace(state="on", attributes={}),
            }
        )
    )

    scope = ManualHoldScope("switch", "entity", "switch.front_privacy")
    assert engine._manual_hold_manager.held_reason_for_scope(scope) == ""


def test_engine_camera_privacy_initial_switch_state_does_not_hold() -> None:
    engine = _privacy_engine(hold_state="off")

    engine.handle_camera_privacy_state_changed(
        SimpleNamespace(
            data={
                "entity_id": "switch.front_privacy",
                "old_state": None,
                "new_state": SimpleNamespace(state="on", attributes={}),
            }
        )
    )

    scope = ManualHoldScope("switch", "entity", "switch.front_privacy")
    assert engine._manual_hold_manager.held_reason_for_scope(scope) == ""


def test_engine_camera_privacy_restored_switch_state_does_not_hold() -> None:
    engine = _privacy_engine(hold_state="off")

    engine.handle_camera_privacy_state_changed(
        SimpleNamespace(
            data={
                "entity_id": "switch.front_privacy",
                "old_state": SimpleNamespace(state="unavailable", attributes={"restored": True}),
                "new_state": SimpleNamespace(state="on", attributes={}),
            }
        )
    )

    scope = ManualHoldScope("switch", "entity", "switch.front_privacy")
    assert engine._manual_hold_manager.held_reason_for_scope(scope) == ""


def test_engine_camera_privacy_external_switch_change_holds_entity() -> None:
    engine = _privacy_engine(hold_state="off")

    engine.handle_camera_privacy_state_changed(
        SimpleNamespace(
            data={
                "entity_id": "switch.front_privacy",
                "old_state": SimpleNamespace(state="on", attributes={}),
                "new_state": SimpleNamespace(state="off", attributes={}),
            }
        )
    )

    scope = ManualHoldScope("switch", "entity", "switch.front_privacy")
    assert engine._manual_hold_manager.held_reason_for_scope(scope) == (
        "manual_hold:switch:entity:switch.front_privacy:external_off"
    )


def test_engine_heating_manual_hold_blocks_heating_step() -> None:
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._manual_hold_manager = ManualHoldManager(monotonic=_Clock())
    engine._state = SimpleNamespace(get_binary=lambda key: key == "heima_heating_manual_hold")
    engine._entry = SimpleNamespace(options={})
    engine._hass = MagicMock()
    engine._behaviors = []
    plan = ApplyPlan(
        steps=[
            ApplyStep(
                domain="heating",
                target="climate.living",
                action="climate.set_temperature",
                params={"entity_id": "climate.living", "temperature": 19},
            )
        ]
    )

    filtered = engine._dispatch_apply_filter(plan, DecisionSnapshot.empty())

    assert filtered.steps[0].blocked_by == "manual_hold:climate:domain:heating:helper_on"


def test_engine_lighting_room_manual_hold_blocks_lighting_step() -> None:
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._manual_hold_manager = ManualHoldManager(monotonic=_Clock())
    engine._entry = SimpleNamespace(
        options={"lighting_rooms": [{"room_id": "living", "enable_manual_hold": True}]}
    )
    engine._state = SimpleNamespace(get_binary=lambda key: key == "heima_lighting_hold_living")
    engine._hass = MagicMock()
    engine._behaviors = []
    plan = ApplyPlan(
        steps=[
            ApplyStep(
                domain="lighting",
                target="living",
                action="scene.turn_on",
                params={"entity_id": "scene.living"},
            )
        ]
    )

    filtered = engine._dispatch_apply_filter(plan, DecisionSnapshot.empty())

    assert filtered.steps[0].blocked_by == "manual_hold:lighting:room:living:helper_on"
