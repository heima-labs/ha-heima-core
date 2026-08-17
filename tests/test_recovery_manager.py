"""Tests for runtime recovery classification."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.recovery import (
    CriticalEntityState,
    RecoveryConfig,
    RecoveryEvaluationInput,
    RecoveryManager,
)


def _entity(entity_id: str, state: str) -> CriticalEntityState:
    return CriticalEntityState(entity_id=entity_id, domain=entity_id.split(".", 1)[0], state=state)


class _FakeStates:
    def get(self, _entity_id: str):
        return None


class _FakeBus:
    def async_fire(self, _event_type: str, _data: dict) -> None:
        return None


class _FakeServices:
    def async_services(self) -> dict[str, dict]:
        return {}


def test_recovery_manager_starts_normal_with_no_critical_entities() -> None:
    manager = RecoveryManager()

    context = manager.evaluate(RecoveryEvaluationInput(now_monotonic=10.0))

    assert context.state == "normal"
    assert context.active is False
    assert context.unavailable_ratio == 0.0
    assert context.as_runtime_context()["runtime.recovery.state"] == "normal"


def test_engine_computes_recovery_context_before_runtime_consumers() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={}))

    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.state"] == "normal"
    assert engine._runtime_context["runtime.recovery.active"] is False


def test_recovery_manager_enters_startup_recovery_on_startup_request() -> None:
    manager = RecoveryManager(
        RecoveryConfig(startup_stabilization_s=120.0, power_restore_stabilization_s=60.0)
    )

    context = manager.evaluate(
        RecoveryEvaluationInput(now_monotonic=100.0, startup_requested=True)
    )

    assert context.state == "startup_recovery"
    assert context.reason == "startup_requested"
    assert context.active is True
    assert context.started_at_monotonic == 100.0
    assert context.parent_state == "startup_recovery"
    assert context.stabilization_deadline_monotonic == 220.0


def test_recovery_manager_enters_power_recovery_when_unavailable_ratio_crosses_threshold() -> None:
    manager = RecoveryManager(RecoveryConfig(critical_entity_unavailable_ratio=0.35))

    context = manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=10.0,
            critical_entities=(
                _entity("light.a", "unavailable"),
                _entity("light.b", "unknown"),
                _entity("switch.c", "on"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )

    assert context.state == "power_recovery"
    assert context.reason == "critical_entities_unavailable"
    assert context.unavailable_count == 2
    assert context.critical_entity_count == 4
    assert context.unavailable_ratio == 0.5


def test_recovery_manager_stays_normal_below_unavailable_threshold() -> None:
    manager = RecoveryManager(RecoveryConfig(critical_entity_unavailable_ratio=0.35))

    context = manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=10.0,
            critical_entities=(
                _entity("light.a", "unavailable"),
                _entity("light.b", "on"),
                _entity("switch.c", "on"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )

    assert context.state == "normal"
    assert context.unavailable_ratio == 0.25


def test_recovery_manager_enters_degraded_after_stabilization_window_elapsed() -> None:
    manager = RecoveryManager(
        RecoveryConfig(critical_entity_unavailable_ratio=0.5, power_restore_stabilization_s=60.0)
    )
    entities = (
        _entity("light.a", "unavailable"),
        _entity("switch.b", "unavailable"),
        _entity("alarm_control_panel.home", "disarmed"),
    )
    manager.evaluate(RecoveryEvaluationInput(now_monotonic=100.0, critical_entities=entities))

    context = manager.evaluate(
        RecoveryEvaluationInput(now_monotonic=161.0, critical_entities=entities)
    )

    assert context.state == "degraded_recovery"
    assert context.reason == "degraded_timeout"
    assert context.stabilization_deadline_monotonic is None


def test_recovery_manager_moves_to_settling_then_normal_after_stable_snapshot() -> None:
    manager = RecoveryManager(
        RecoveryConfig(critical_entity_unavailable_ratio=0.5, power_restore_stabilization_s=60.0)
    )
    manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=100.0,
            critical_entities=(
                _entity("light.a", "unavailable"),
                _entity("switch.b", "unavailable"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )

    settling = manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=120.0,
            critical_entities=(
                _entity("light.a", "on"),
                _entity("switch.b", "off"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )
    assert settling.state == "recovery_settling"
    assert settling.reason == "critical_entities_restored"
    assert settling.stabilization_deadline_monotonic == 180.0

    context = manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=181.0,
            critical_entities=(
                _entity("light.a", "on"),
                _entity("switch.b", "off"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
            stable_snapshot_available=True,
        )
    )
    assert context.state == "normal"
    assert context.reason == "stabilized"
    assert context.active is False


def test_recovery_manager_settling_reverts_on_flapping() -> None:
    manager = RecoveryManager(
        RecoveryConfig(critical_entity_unavailable_ratio=0.5, power_restore_stabilization_s=60.0)
    )
    manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=100.0,
            critical_entities=(
                _entity("light.a", "unavailable"),
                _entity("switch.b", "unavailable"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )
    manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=120.0,
            critical_entities=(
                _entity("light.a", "on"),
                _entity("switch.b", "off"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )

    context = manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=130.0,
            critical_entities=(
                _entity("light.a", "unavailable"),
                _entity("switch.b", "unavailable"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )

    assert context.state == "power_recovery"
    assert context.reason == "critical_entities_flapping"
    assert context.settling_started_at_monotonic is None


def test_recovery_manager_does_not_exit_settling_while_reconciliation_pending() -> None:
    manager = RecoveryManager(
        RecoveryConfig(critical_entity_unavailable_ratio=0.5, power_restore_stabilization_s=60.0)
    )
    manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=100.0,
            critical_entities=(
                _entity("light.a", "unavailable"),
                _entity("switch.b", "unavailable"),
                _entity("alarm_control_panel.home", "disarmed"),
            ),
        )
    )
    available = (
        _entity("light.a", "on"),
        _entity("switch.b", "off"),
        _entity("alarm_control_panel.home", "disarmed"),
    )
    manager.evaluate(RecoveryEvaluationInput(now_monotonic=120.0, critical_entities=available))

    context = manager.evaluate(
        RecoveryEvaluationInput(
            now_monotonic=181.0,
            critical_entities=available,
            stable_snapshot_available=True,
            reconciliation_pending=True,
        )
    )

    assert context.state == "recovery_settling"
    assert context.reason == "critical_entities_restored"
    assert context.reconciliation_pending is True
