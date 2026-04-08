"""Tests for Behavior Framework v1.1 infrastructure."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.heima.runtime.behaviors.base import HeimaBehavior
from custom_components.heima.runtime.contracts import ApplyPlan, ApplyStep
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# HeimaBehavior base class
# ---------------------------------------------------------------------------


def test_behavior_id_defaults_to_class_name():
    class MyBehavior(HeimaBehavior):
        pass

    assert MyBehavior().behavior_id == "MyBehavior"


def test_on_snapshot_is_noop():
    snapshot = DecisionSnapshot.empty()
    HeimaBehavior().on_snapshot(snapshot)  # must not raise


def test_apply_filter_returns_plan_unchanged():
    plan = ApplyPlan(steps=[ApplyStep(domain="lighting", target="x", action="scene.turn_on")])
    snapshot = DecisionSnapshot.empty()
    result = HeimaBehavior().apply_filter(plan, snapshot)
    assert result is plan


def test_on_options_reloaded_is_noop():
    HeimaBehavior().on_options_reloaded({})  # must not raise


def test_reset_learning_state_is_noop():
    HeimaBehavior().reset_learning_state()  # must not raise


def test_diagnostics_returns_empty_dict():
    assert HeimaBehavior().diagnostics() == {}


# ---------------------------------------------------------------------------
# Engine behavior dispatch (integration-light)
# ---------------------------------------------------------------------------


class _SnapshotCapture(HeimaBehavior):
    def __init__(self) -> None:
        self.snapshots: list[DecisionSnapshot] = []
        self.plans: list[ApplyPlan] = []

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        self.snapshots.append(snapshot)

    def apply_filter(self, plan: ApplyPlan, snapshot: DecisionSnapshot) -> ApplyPlan:
        self.plans.append(plan)
        return plan


class _FaultyBehavior(HeimaBehavior):
    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        raise RuntimeError("boom")

    def apply_filter(self, plan: ApplyPlan, snapshot: DecisionSnapshot) -> ApplyPlan:
        raise RuntimeError("boom")


def _make_engine():
    """Return a minimal HeimaEngine with mocked HA dependencies."""
    from custom_components.heima.runtime.engine import HeimaEngine

    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.async_services.return_value = {}
    entry = MagicMock()
    entry.entry_id = "test"
    entry.options = {}
    return HeimaEngine(hass, entry)


def test_register_behavior_appended():
    engine = _make_engine()
    b = _SnapshotCapture()
    engine.register_behavior(b)
    assert b in engine._behaviors


def test_dispatch_on_snapshot_called(event_loop):
    engine = _make_engine()
    b = _SnapshotCapture()
    engine.register_behavior(b)
    snapshot = DecisionSnapshot.empty()
    engine._dispatch_on_snapshot(snapshot)
    assert len(b.snapshots) == 1
    assert b.snapshots[0] is snapshot


def test_dispatch_apply_filter_called(event_loop):
    engine = _make_engine()
    b = _SnapshotCapture()
    engine.register_behavior(b)
    plan = ApplyPlan.empty()
    snapshot = DecisionSnapshot.empty()
    result = engine._dispatch_apply_filter(plan, snapshot)
    assert len(b.plans) == 1
    assert result is plan


def test_faulty_behavior_does_not_propagate_exception():
    engine = _make_engine()
    engine.register_behavior(_FaultyBehavior())
    snapshot = DecisionSnapshot.empty()
    engine._dispatch_on_snapshot(snapshot)  # must not raise
    engine._dispatch_apply_filter(ApplyPlan.empty(), snapshot)  # must not raise


def test_multiple_behaviors_all_called():
    engine = _make_engine()
    b1, b2 = _SnapshotCapture(), _SnapshotCapture()
    engine.register_behavior(b1)
    engine.register_behavior(b2)
    engine._dispatch_on_snapshot(DecisionSnapshot.empty())
    assert len(b1.snapshots) == 1
    assert len(b2.snapshots) == 1


def test_diagnostics_includes_behaviors():
    engine = _make_engine()
    engine.register_behavior(_SnapshotCapture())
    diag = engine.diagnostics()
    assert "_SnapshotCapture" in diag["behaviors"]
