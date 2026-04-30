"""Tests for runtime invariant checks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima.runtime.contracts import ApplyPlan
from custom_components.heima.runtime.domain_result_bag import DomainResultBag
from custom_components.heima.runtime.domains.heating import HeatingDomainResult
from custom_components.heima.runtime.domains.occupancy import OccupancyResult
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.invariant_check import (
    InvariantCheckState,
    evaluate_invariant_state,
)
from custom_components.heima.runtime.invariants import (
    HeatingHomeEmpty,
    PresenceWithoutOccupancy,
    SecurityPresenceMismatch,
    SensorStuck,
)
from custom_components.heima.runtime.plugin_contracts import InvariantViolation
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _FakeStateObj:
    def __init__(self, state: str) -> None:
        self.state = state


class _FakeStates:
    def get(self, entity_id: str) -> _FakeStateObj | None:  # noqa: ARG002
        return None


class _FakeBus:
    def async_fire(self, event_type: str, data: dict[str, Any]) -> None:  # noqa: ARG002
        return None


class _FakeServices:
    async def async_call(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def async_services(self) -> dict[str, dict[str, Any]]:
        return {"notify": {}}


class _AlwaysViolationCheck:
    @property
    def check_id(self) -> str:
        return "always"

    @property
    def default_debounce_s(self) -> float:
        return 0.0

    def check(
        self,
        snapshot: DecisionSnapshot,
        domain_results: DomainResultBag,
    ) -> InvariantViolation:
        del snapshot, domain_results
        return InvariantViolation(
            check_id=self.check_id,
            severity="warning",
            anomaly_type="always",
            description="Always active.",
        )


def _snapshot(
    *,
    anyone_home: bool = True,
    occupied_rooms: list[str] | None = None,
    house_state: str = "home",
    security_state: str = "disarmed",
) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="snapshot",
        ts="2026-04-30T10:00:00+00:00",
        house_state=house_state,
        anyone_home=anyone_home,
        people_count=1 if anyone_home else 0,
        occupied_rooms=list(occupied_rooms or []),
        lighting_intents={},
        security_state=security_state,
    )


def _heating_result(*, active: bool) -> HeatingDomainResult:
    trace = {
        "state": "delegated" if active else "inactive",
        "apply_allowed": active,
        "target_temperature": 21.0 if active else None,
    }
    return HeatingDomainResult(
        trace=trace,
        current_setpoint=20.0,
        observed_source="user",
        observed_provenance=None,
    )


def _case_data() -> list[
    tuple[Any, DecisionSnapshot, DomainResultBag, DecisionSnapshot, DomainResultBag]
]:
    return [
        (
            PresenceWithoutOccupancy(),
            _snapshot(anyone_home=True, occupied_rooms=[]),
            DomainResultBag.empty().with_result(
                "occupancy", OccupancyResult(occupied_rooms=[], sensorized_room_count=1)
            ),
            _snapshot(anyone_home=False, occupied_rooms=[]),
            DomainResultBag.empty().with_result(
                "occupancy", OccupancyResult(occupied_rooms=[], sensorized_room_count=1)
            ),
        ),
        (
            SecurityPresenceMismatch(),
            _snapshot(anyone_home=True, security_state="armed_away"),
            DomainResultBag.empty(),
            _snapshot(anyone_home=True, security_state="disarmed"),
            DomainResultBag.empty(),
        ),
        (
            HeatingHomeEmpty(),
            _snapshot(anyone_home=False, house_state="away"),
            DomainResultBag.empty().with_result("heating", _heating_result(active=True)),
            _snapshot(anyone_home=False, house_state="away"),
            DomainResultBag.empty().with_result("heating", _heating_result(active=False)),
        ),
        (
            SensorStuck(),
            _snapshot(),
            DomainResultBag.empty().with_result(
                "sensor_status", {"stuck": ["binary_sensor.kitchen_motion"]}
            ),
            _snapshot(),
            DomainResultBag.empty().with_result("sensor_status", {"stuck": []}),
        ),
    ]


@pytest.mark.parametrize(
    ("check", "active_snapshot", "active_results", "clear_snapshot", "clear_results"),
    _case_data(),
)
def test_builtin_invariant_checks_violation_resolution_and_debounce(
    check: Any,
    active_snapshot: DecisionSnapshot,
    active_results: DomainResultBag,
    clear_snapshot: DecisionSnapshot,
    clear_results: DomainResultBag,
) -> None:
    violation = check.check(active_snapshot, active_results)
    assert violation is not None
    assert violation.check_id == check.check_id

    state = InvariantCheckState()
    first = evaluate_invariant_state(
        state=state,
        violation=violation,
        debounce_s=check.default_debounce_s,
        re_emit_interval_s=3600,
        now=0,
    )
    assert first.violation is None
    second = evaluate_invariant_state(
        state=state,
        violation=violation,
        debounce_s=check.default_debounce_s,
        re_emit_interval_s=3600,
        now=check.default_debounce_s,
    )
    assert second.violation == violation

    cleared = check.check(clear_snapshot, clear_results)
    assert cleared is None
    resolved = evaluate_invariant_state(
        state=state,
        violation=cleared,
        debounce_s=check.default_debounce_s,
        re_emit_interval_s=3600,
        now=check.default_debounce_s + 1,
    )
    assert resolved.resolved is True


def test_invariant_state_re_emits_persistent_violation() -> None:
    check = SecurityPresenceMismatch()
    violation = check.check(
        _snapshot(anyone_home=True, security_state="armed_away"), DomainResultBag.empty()
    )
    assert violation is not None
    state = InvariantCheckState()

    first = evaluate_invariant_state(
        state=state,
        violation=violation,
        debounce_s=0,
        re_emit_interval_s=10,
        now=0,
    )
    second = evaluate_invariant_state(
        state=state,
        violation=violation,
        debounce_s=0,
        re_emit_interval_s=10,
        now=5,
    )
    third = evaluate_invariant_state(
        state=state,
        violation=violation,
        debounce_s=0,
        re_emit_interval_s=10,
        now=10,
    )

    assert first.violation == violation
    assert second.violation is None
    assert third.violation == violation


def test_engine_runs_invariant_checks_before_apply_plan() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={"notifications": {}}))
    order: list[str] = []
    snapshot = _snapshot()

    def compute_snapshot(reason: str) -> DecisionSnapshot:
        del reason
        order.append("compute")
        engine._last_domain_results = DomainResultBag.empty()  # noqa: SLF001
        return snapshot

    def run_invariant_checks(current_snapshot: DecisionSnapshot) -> None:
        del current_snapshot
        order.append("invariants")

    def build_apply_plan(current_snapshot: DecisionSnapshot) -> ApplyPlan:
        del current_snapshot
        order.append("apply")
        return ApplyPlan.empty()

    engine._compute_snapshot = compute_snapshot  # type: ignore[method-assign]  # noqa: SLF001
    engine._run_invariant_checks = run_invariant_checks  # type: ignore[method-assign]  # noqa: SLF001
    engine._build_apply_plan = build_apply_plan  # type: ignore[method-assign]  # noqa: SLF001
    engine._calendar_domain.async_maybe_refresh = _noop_async  # type: ignore[method-assign]  # noqa: SLF001

    import asyncio

    asyncio.run(engine.async_evaluate(reason="test"))

    assert order == ["compute", "invariants", "apply"]


def test_engine_invariant_config_defaults() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={"notifications": {}}))

    assert engine._invariant_config() == {  # noqa: SLF001
        "enabled": True,
        "sensor_stuck_threshold_s": 86400,
        "heating_empty_threshold_s": 1800,
        "notify_on_info": False,
        "re_emit_interval_s": 3600,
    }


def test_engine_converts_invariant_violation_to_anomaly_event() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    engine = HeimaEngine(hass=hass, entry=SimpleNamespace(options={"notifications": {}}))
    engine.register_invariant_check(_AlwaysViolationCheck())

    engine._run_invariant_checks(_snapshot())  # noqa: SLF001

    event = engine._events_domain._pending_events[-1]  # noqa: SLF001
    assert event.type == "anomaly.always"
    assert event.key == "anomaly.always"
    assert event.severity == "warning"
    assert event.context == {
        "check_id": "always",
        "anomaly_type": "always",
        "notify": True,
    }


async def _noop_async(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
    return None
