from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.manual_hold import (
    ManualHoldManager,
    ManualHoldReason,
    ManualHoldScope,
)
from custom_components.heima.runtime.notifications import ActionableNotificationResponse
from custom_components.heima.runtime.runtime_confirmation import (
    RuntimeActionRequest,
    RuntimeApplyResult,
    resolve_runtime_request,
)
from custom_components.heima.runtime.runtime_confirmation_controller import (
    ACTION_RUNTIME_REQUEST_APPROVE,
    RuntimeConfirmationController,
)
from custom_components.heima.runtime.state_store import CanonicalState


class _FakeServices:
    async def async_call(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        return None


class _FakeHass:
    def __init__(self) -> None:
        self.services = _FakeServices()
        self.tasks: list[Any] = []

    def async_create_task(self, coro: Any) -> Any:
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


class _Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _coordinator() -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(entry_id="entry-1")
    coordinator.hass = SimpleNamespace(services=_FakeServices())
    coordinator.engine = SimpleNamespace(
        health=SimpleNamespace(ok=True, reason="initialized"),
        state=CanonicalState(sensors={"heima_health": None}),
        unresolved_invariant_check_ids=lambda: {"security_presence_mismatch"},
    )
    coordinator._last_anomaly = None
    coordinator._last_invariant_violation = None
    coordinator._last_diagnostics = {}
    coordinator._house_state_module = None
    coordinator._house_snapshot_store = SimpleNamespace(diagnostics=lambda: {"total_snapshots": 1})
    coordinator._approval_store = SimpleNamespace(diagnostics=lambda: {"total_records": 0})
    coordinator._proposal_engine = SimpleNamespace(diagnostics=lambda: {"pending": 0})
    coordinator._validation_report = lambda: SimpleNamespace(as_dict=lambda: {})
    return coordinator


def test_health_invariant_transition_reconciles_against_current_engine_state() -> None:
    coordinator = _coordinator()
    event = {
        "type": "anomaly.security_presence_mismatch",
        "key": "anomaly.security_presence_mismatch",
        "severity": "critical",
        "title": "Invariant violation",
        "message": "Security is armed away while someone is home.",
        "context": {
            "check_id": "security_presence_mismatch",
            "anomaly_type": "security_presence_mismatch",
            "security_state": "armed_away",
        },
        "event_id": "evt-1",
        "ts": "2026-07-20T19:33:20+00:00",
    }

    coordinator._record_installer_alert(event)  # noqa: SLF001
    coordinator._sync_health_sensor()  # noqa: SLF001

    assert coordinator.engine.state.get_sensor("heima_health") == "degraded"

    coordinator.engine.unresolved_invariant_check_ids = lambda: set()
    coordinator._sync_health_sensor()  # noqa: SLF001

    assert coordinator.engine.state.get_sensor("heima_health") == "ok"
    assert coordinator.engine.state.get_sensor_attributes("heima_health")[
        "last_invariant_violation"
    ] == {}


def test_manual_hold_transition_owned_apply_external_change_and_release() -> None:
    manager = ManualHoldManager(monotonic=_Clock())
    scope = ManualHoldScope("switch", "entity", "switch.front_privacy")
    step = ApplyStep(
        domain="switch",
        target="switch.front_privacy",
        action="switch.turn_off",
        params={"entity_id": "switch.front_privacy"},
    )

    manager.register_pending_apply(step)
    assert (
        manager.classify_state_change(
            "switch.front_privacy",
            SimpleNamespace(state="off", attributes={}),
        )
        == "heima_owned"
    )
    assert manager.held_reason_for_scope(scope) == ""

    assert (
        manager.classify_state_change(
            "switch.front_privacy",
            SimpleNamespace(state="on", attributes={}),
        )
        == "external"
    )
    manager.activate_hold(
        scope,
        ManualHoldReason("external_on", "switch.front_privacy"),
    )
    assert manager.held_reason_for_scope(scope).endswith(":external_on")

    manager.release_scope(scope, reason_kind="external_on")
    assert manager.held_reason_for_scope(scope) == ""


@pytest.mark.asyncio
async def test_runtime_confirmation_transition_late_second_response_is_stale(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def _apply(request: RuntimeActionRequest, status: str) -> RuntimeActionRequest:
        calls.append(status)
        started.set()
        await release.wait()
        return resolve_runtime_request(
            request,
            status=status,  # type: ignore[arg-type]
            apply_result=RuntimeApplyResult(applied_steps=1),
        )

    controller = RuntimeConfirmationController(_FakeHass(), apply_handler=_apply)
    request = _request()
    controller.add_request(request)

    first_task = asyncio.create_task(
        controller.async_handle_action_response(
            ActionableNotificationResponse(
                action_id=ACTION_RUNTIME_REQUEST_APPROVE,
                request_id=request.request_id,
            )
        )
    )
    await started.wait()
    second = await controller.async_handle_action_response(
        ActionableNotificationResponse(
            action_id=ACTION_RUNTIME_REQUEST_APPROVE,
            request_id=request.request_id,
        )
    )
    release.set()
    first = await first_task

    assert first is not None
    assert first.status == "approved"
    assert second is None
    assert calls == ["approved"]
    assert controller.diagnostics()["stale_responses"] == 1


def _request() -> RuntimeActionRequest:
    now = datetime.now(UTC)
    return RuntimeActionRequest(
        reaction_id="reaction-1",
        reaction_type="context_conditioned_lighting_scene",
        occurrence_key="occurrence-1",
        title="Apply scene?",
        message="Apply the stored scene.",
        apply_steps=(ApplyStep(domain="light", target="light.studio", action="light.turn_on"),),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        on_timeout="skip",
        confirmation_targets=("resident",),
    )
