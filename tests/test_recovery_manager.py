"""Tests for runtime recovery classification."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.runtime.checkpoint_store import (
    CheckpointEntityState,
    RuntimeCheckpoint,
)
from custom_components.heima.runtime.contracts import ApplyPlan, ApplyStep
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.manual_hold import ManualHoldReason, ManualHoldScope
from custom_components.heima.runtime.plugin_contracts import InvariantViolation
from custom_components.heima.runtime.reactions.base import HeimaReaction
from custom_components.heima.runtime.recovery import (
    CheckpointRecoveryStatus,
    CriticalEntityState,
    RecoveryConfig,
    RecoveryContext,
    RecoveryEvaluationInput,
    RecoveryManager,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot
from custom_components.heima.runtime.state_store import CanonicalState


def _entity(entity_id: str, state: str) -> CriticalEntityState:
    return CriticalEntityState(entity_id=entity_id, domain=entity_id.split(".", 1)[0], state=state)


class _FakeStates:
    def __init__(self, states=None):
        self._states = states or {}

    def get(self, _entity_id: str):
        return self._states.get(_entity_id)

    def set(self, entity_id: str, state: str) -> None:
        self._states[entity_id] = SimpleNamespace(state=state, attributes={})


class _FakeBus:
    def async_fire(self, _event_type: str, _data: dict) -> None:
        return None


class _FakeServices:
    def async_services(self) -> dict[str, dict]:
        return {}


class _FakeSnapshotStore:
    def __init__(self) -> None:
        self.appended = 0

    async def async_append_if_changed(self, _snapshot) -> bool:
        self.appended += 1
        return True


class _AlwaysViolatesCheck:
    check_id = "unit_violation"
    default_debounce_s = 0.0
    default_re_emit_interval_s = 0.0

    def check(self, _snapshot, _domain_results):
        return InvariantViolation(
            check_id=self.check_id,
            severity="critical",
            anomaly_type="unit_violation",
            description="Unit violation",
        )


class _FakeReaction(HeimaReaction):
    @property
    def reaction_id(self) -> str:
        return "fake_reaction"


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

    assert engine._runtime_context["runtime.recovery.state"] == "startup_recovery"
    assert engine._runtime_context["runtime.recovery.reason"] == "startup_requested"
    assert engine._runtime_context["runtime.recovery.active"] is True
    assert engine._runtime_context["runtime.recovery.checkpoint.reason"] == "store_not_configured"
    assert "recovery.stabilization" in engine.scheduled_runtime_jobs()


def test_engine_classifies_fresh_checkpoint_differences() -> None:
    checkpoint = RuntimeCheckpoint(
        entry_id="entry-a",
        reason="unit",
        critical_entities=(
            CheckpointEntityState(
                entity_id="light.desk",
                domain="light",
                state="off",
            ),
        ),
    )
    hass = SimpleNamespace(
        states=_FakeStates({"light.desk": SimpleNamespace(state="on", attributes={})}),
        bus=_FakeBus(),
        services=_FakeServices(),
    )
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(
            entry_id="entry-a", options={"rooms": [{"motion_sensor": "light.desk"}]}
        ),
    )
    engine.set_runtime_checkpoint_store(
        SimpleNamespace(checkpoint_for_entry=lambda _entry_id: checkpoint)
    )

    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.checkpoint.usable"] is True
    assert engine._runtime_context["runtime.recovery.checkpoint.difference_count"] == 1
    diff = engine._recovery_manager.context.checkpoint_status.differences[0]
    assert diff.entity_id == "light.desk"
    assert diff.kind == "power_restore_candidate"


def test_engine_reports_missing_checkpoint_from_loaded_store() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(entry_id="entry-a", options={}),
    )
    engine.set_runtime_checkpoint_store(
        SimpleNamespace(checkpoint_for_entry=lambda _entry_id: None)
    )

    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.state"] == "startup_recovery"
    assert engine._runtime_context["runtime.recovery.checkpoint.available"] is False
    assert engine._runtime_context["runtime.recovery.checkpoint.reason"] == "missing"


def test_engine_marks_stale_checkpoint_unusable() -> None:
    checkpoint = RuntimeCheckpoint(
        entry_id="entry-a",
        reason="unit",
        created_at="2026-01-01T00:00:00+00:00",
    )
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(entry_id="entry-a", options={}),
    )
    engine.set_runtime_checkpoint_store(
        SimpleNamespace(checkpoint_for_entry=lambda _entry_id: checkpoint)
    )

    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.checkpoint.available"] is True
    assert engine._runtime_context["runtime.recovery.checkpoint.usable"] is False
    assert engine._runtime_context["runtime.recovery.checkpoint.stale"] is True
    assert engine._runtime_context["runtime.recovery.checkpoint.reason"] == "stale"


def test_engine_marks_invalid_checkpoint_unusable() -> None:
    checkpoint = RuntimeCheckpoint(
        entry_id="entry-a",
        reason="unit",
        created_at="not-a-date",
    )
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(entry_id="entry-a", options={}),
    )
    engine.set_runtime_checkpoint_store(
        SimpleNamespace(checkpoint_for_entry=lambda _entry_id: checkpoint)
    )

    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.checkpoint.available"] is True
    assert engine._runtime_context["runtime.recovery.checkpoint.usable"] is False
    assert engine._runtime_context["runtime.recovery.checkpoint.reason"] == "invalid_created_at"


def test_engine_detects_online_power_recovery_with_configured_targets() -> None:
    states = _FakeStates()
    for entity_id, state in {
        "binary_sensor.camera_motion": "off",
        "climate.boiler": "unavailable",
        "switch.camera_privacy": "unavailable",
        "switch.pump": "unavailable",
    }.items():
        states.set(entity_id, state)
    hass = SimpleNamespace(states=states, bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(
            entry_id="entry-a",
            options={
                "heating": {"climate_entity": "climate.boiler"},
                "security": {
                    "camera_evidence_sources": [
                        {
                            "motion_entity": "binary_sensor.camera_motion",
                            "privacy_entity": "switch.camera_privacy",
                        }
                    ]
                },
                "reactions": {
                    "configured": {
                        "pump_off": {
                            "steps": [
                                {
                                    "domain": "switch",
                                    "target": "switch.pump",
                                    "action": "switch.turn_off",
                                    "params": {"entity_id": "switch.pump"},
                                }
                            ]
                        }
                    }
                },
            },
        ),
    )
    engine._startup_recovery_pending = False

    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.state"] == "power_recovery"
    assert engine._runtime_context["runtime.recovery.reason"] == "critical_entities_unavailable"
    critical_ids = {
        entity.entity_id for entity in engine._recovery_manager.context.critical_entities
    }
    assert {
        "binary_sensor.camera_motion",
        "climate.boiler",
        "switch.camera_privacy",
        "switch.pump",
    }.issubset(critical_ids)
    assert "recovery.stabilization" in engine.scheduled_runtime_jobs()

    states.set("climate.boiler", "heat")
    states.set("switch.camera_privacy", "on")
    states.set("switch.pump", "off")
    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.state"] == "recovery_settling"
    assert engine._runtime_context["runtime.recovery.reason"] == "critical_entities_restored"

    states.set("switch.pump", "unavailable")
    states.set("switch.camera_privacy", "unavailable")
    engine._compute_recovery_context()

    assert engine._runtime_context["runtime.recovery.state"] == "power_recovery"
    assert engine._runtime_context["runtime.recovery.reason"] == "critical_entities_flapping"


@pytest.mark.asyncio
async def test_engine_suppresses_learning_snapshots_during_recovery() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    store = _FakeSnapshotStore()
    engine.set_snapshot_store(store)  # type: ignore[arg-type]
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }

    await engine._record_snapshot_if_changed(DecisionSnapshot.empty())

    assert store.appended == 0


def test_engine_suppresses_invariants_during_recovery() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    engine.register_invariant_check(_AlwaysViolatesCheck())  # type: ignore[arg-type]
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }

    engine._run_invariant_checks(DecisionSnapshot.empty())

    assert engine._events_domain._pending_events == []


def test_engine_blocks_apply_steps_before_manual_hold_during_recovery() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }
    engine._manual_hold_manager.activate_hold(
        ManualHoldScope("switch", "entity", "switch.camera_privacy"),
        ManualHoldReason(kind="external_on", source_entity="switch.camera_privacy"),
    )
    plan = ApplyPlan(
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.camera_privacy",
                action="switch.turn_off",
                params={"entity_id": "switch.camera_privacy"},
            )
        ]
    )

    filtered = engine._dispatch_apply_filter(plan, DecisionSnapshot.empty())

    assert filtered.steps[0].blocked_by == "recovery:power_recovery"


def test_engine_does_not_create_camera_privacy_hold_during_recovery() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(
            entry_id="entry-a",
            options={
                "security": {
                    "camera_evidence_sources": [
                        {
                            "privacy_entity": "switch.camera_privacy",
                        }
                    ]
                }
            },
        ),
    )
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }
    event = SimpleNamespace(
        data={
            "entity_id": "switch.camera_privacy",
            "old_state": SimpleNamespace(state="off"),
            "new_state": SimpleNamespace(state="on"),
        }
    )

    engine.handle_camera_privacy_state_changed(event)  # type: ignore[arg-type]

    assert engine._manual_hold_manager.diagnostics()["active_holds"] == []


def test_engine_does_not_create_runtime_confirmation_during_recovery() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }
    engine.set_runtime_confirmation_request_handler(
        lambda _request: (_ for _ in ()).throw(AssertionError("should not create request"))
    )

    handled = engine._maybe_create_runtime_confirmation_request(
        _FakeReaction(),
        [
            ApplyStep(
                domain="light",
                target="light.desk",
                action="light.turn_on",
                params={"entity_id": "light.desk"},
            )
        ],
        DecisionSnapshot.empty(),
    )

    assert handled is False


def test_engine_recovery_guard_prevents_away_from_sensor_silence() -> None:
    checkpoint = RuntimeCheckpoint(
        entry_id="entry-a",
        reason="unit",
        runtime={"snapshot": {"house_state": "working"}},
    )
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(entry_id="entry-a", options={}),
    )
    engine.set_runtime_checkpoint_store(
        SimpleNamespace(checkpoint_for_entry=lambda _entry_id: checkpoint)
    )
    engine._runtime_context = {
        "runtime.recovery.state": "startup_recovery",
        "runtime.recovery.active": True,
    }

    state, reason = engine._recovery_guard_house_state(
        house_state="away",
        house_reason="presence_absent",
        previous_house_state="unknown",
        anyone_home=False,
        occupied_rooms=[],
    )

    assert state == "working"
    assert reason == "recovery_guard:no_away_from_sensor_silence:presence_absent"


def test_engine_recovery_guard_prefers_previous_non_away_house_state() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }

    state, _reason = engine._recovery_guard_house_state(
        house_state="away",
        house_reason="presence_absent",
        previous_house_state="home",
        anyone_home=False,
        occupied_rooms=[],
    )

    assert state == "home"


def test_engine_restores_heating_vacation_curve_runtime_from_checkpoint() -> None:
    checkpoint = RuntimeCheckpoint(
        entry_id="entry-a",
        reason="unit",
        heating={
            "selected_branch": "vacation_curve",
            "vacation_curve_start_temp": 20.5,
            "vacation_curve_started_at": "2026-07-01T10:00:00+00:00",
        },
    )
    hass = SimpleNamespace(
        states=_FakeStates(
            {
                "climate.boiler": SimpleNamespace(
                    state="heat",
                    attributes={"temperature": 18.0},
                )
            }
        ),
        bus=_FakeBus(),
        services=_FakeServices(),
    )
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    engine.set_runtime_checkpoint_store(
        SimpleNamespace(checkpoint_for_entry=lambda _entry_id: checkpoint)
    )

    engine._heating_domain.compute_policy(
        house_state="vacation",
        heating_cfg={
            "climate_entity": "climate.boiler",
            "override_branches": {
                "vacation": {
                    "branch": "vacation_curve",
                    "vacation_ramp_down_h": 8,
                    "vacation_ramp_up_h": 8,
                    "vacation_min_temp": 16,
                    "vacation_comfort_temp": 20,
                    "vacation_min_total_hours_for_ramp": 24,
                }
            },
        },
        state=CanonicalState(),
        events=engine._events_domain,
        schedule_recheck=lambda **_kwargs: None,
    )

    trace = engine._heating_domain.diagnostics()
    assert trace["selected_branch"] == "vacation_curve"
    assert trace["vacation_curve_start_temp"] == 20.5
    assert trace["vacation_curve_started_at"] == "2026-07-01T10:00:00+00:00"


def test_engine_emits_security_unavailable_mismatch_during_recovery_once() -> None:
    states = _FakeStates()
    states.set("alarm_control_panel.home", "unavailable")
    hass = SimpleNamespace(states=states, bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    engine._runtime_context = {
        "runtime.recovery.state": "power_recovery",
        "runtime.recovery.active": True,
    }
    options = {
        "security": {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
        }
    }

    engine._queue_security_state_unavailable_recovery_event(
        options=options,
        security_state="unknown",
        security_reason="unavailable",
    )
    engine._queue_security_state_unavailable_recovery_event(
        options=options,
        security_state="unknown",
        security_reason="unavailable",
    )

    pending = engine._events_domain._pending_events
    assert len(pending) == 1
    assert pending[0].type == "security.mismatch"
    assert pending[0].key == "security.mismatch.security_state_unavailable"
    assert pending[0].context["subtype"] == "security_state_unavailable"


def test_engine_queues_recovery_lifecycle_events_for_transitions() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))

    engine._queue_recovery_transition_events(
        RecoveryContext(state="power_recovery", reason="critical_entities_unavailable"),
        RecoveryContext(state="recovery_settling", reason="critical_entities_restored"),
    )

    assert [event.type for event in engine._events_domain._pending_events] == [
        "system.recovery_power_restored",
        "system.recovery_stabilization_started",
    ]


def test_engine_queues_checkpoint_invalid_event_once_per_invalid_checkpoint() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(entry_id="entry-a", options={}))
    status = CheckpointRecoveryStatus(
        available=True,
        usable=False,
        stale=True,
        checkpoint_id="checkpoint.one",
        reason="stale",
        age_s=3600,
    )

    engine._queue_checkpoint_invalid_event(status)
    engine._queue_checkpoint_invalid_event(status)

    pending = engine._events_domain._pending_events
    assert len(pending) == 1
    assert pending[0].type == "system.recovery_checkpoint_invalid"
    assert pending[0].context["checkpoint"]["reason"] == "stale"


def test_recovery_manager_enters_startup_recovery_on_startup_request() -> None:
    manager = RecoveryManager(
        RecoveryConfig(startup_stabilization_s=120.0, power_restore_stabilization_s=60.0)
    )

    context = manager.evaluate(RecoveryEvaluationInput(now_monotonic=100.0, startup_requested=True))

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
