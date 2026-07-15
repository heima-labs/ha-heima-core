from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.notifications import (
    ActionableNotificationResponse,
    HeimaEventPipeline,
)
from custom_components.heima.runtime.runtime_confirmation import (
    FAILURE_APPLY_ERROR,
    FAILURE_NO_ACTIONABLE_ROUTE,
    RuntimeActionRequest,
    RuntimeApplyResult,
    resolve_runtime_request,
)
from custom_components.heima.runtime.runtime_confirmation_controller import (
    ACTION_RUNTIME_REQUEST_APPROVE,
    ACTION_RUNTIME_REQUEST_DISMISS,
    EVENT_MOBILE_APP_NOTIFICATION_ACTION,
    RuntimeConfirmationController,
)


class _FakeBus:
    def __init__(self) -> None:
        self.listeners: dict[str, Any] = {}
        self.unsubscribed: list[str] = []

    def async_listen(self, event_type: str, callback):
        self.listeners[event_type] = callback

        def _unsub() -> None:
            self.unsubscribed.append(event_type)
            self.listeners.pop(event_type, None)

        return _unsub


class _FakeHass:
    def __init__(self) -> None:
        self.bus = _FakeBus()
        self.services = _FakeServices()
        self.tasks: list[asyncio.Task] = []

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


class _FakeServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, bool]] = []
        self.available: dict[str, object] = {}

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, dict(data), blocking))

    def async_services(self):
        return {"notify": dict(self.available)}


@pytest.mark.asyncio
async def test_controller_subscribes_and_unsubscribes_action_events() -> None:
    hass = _FakeHass()
    controller = RuntimeConfirmationController(hass)

    await controller.async_initialize()
    await controller.async_shutdown()

    assert EVENT_MOBILE_APP_NOTIFICATION_ACTION in hass.bus.unsubscribed
    assert controller.diagnostics()["action_event_subscription_active"] is False


@pytest.mark.asyncio
async def test_controller_timeout_skip_marks_request_timeout_skipped(monkeypatch) -> None:
    scheduled: list[tuple[float, Any]] = []
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, delay, callback: scheduled.append((delay, callback)) or (lambda: None),
    )
    controller = RuntimeConfirmationController(_FakeHass())
    request = _request(on_timeout="skip")

    controller.add_request(request)
    resolved = await controller.async_handle_timeout(request.request_id)

    assert scheduled
    assert resolved is not None
    assert resolved.status == "timeout_skipped"
    assert resolved.apply_result == RuntimeApplyResult(
        skipped_steps=1,
        skipped_reasons={"timeout_skipped": 1},
    )
    assert controller.diagnostics()["completed_by_status"] == {"timeout_skipped": 1}


@pytest.mark.asyncio
async def test_controller_diagnostics_include_requests_step_counts_and_failure_reasons(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    controller = RuntimeConfirmationController(_FakeHass())
    pending = _request(reaction_id="reaction-pending", occurrence_key="occurrence-pending")
    failed = _request(reaction_id="reaction-failed", occurrence_key="occurrence-failed")
    applied = _request(reaction_id="reaction-applied", occurrence_key="occurrence-applied")

    controller.add_request(pending)
    controller.add_request(failed)
    controller.registry.resolve(
        failed.request_id,
        status="failed",
        failure_reason=FAILURE_NO_ACTIONABLE_ROUTE,
    )
    controller.registry.mark_completed(
        resolve_runtime_request(
            applied,
            status="approved",
            apply_result=RuntimeApplyResult(
                applied_steps=1,
                blocked_steps=1,
                failed_steps=1,
                skipped_steps=1,
                blocked_reasons={"manual_hold_active": 1},
                failed_reasons={"apply_error": 1},
                skipped_reasons={"dependency_blocked": 1},
            ),
        )
    )

    diagnostics = controller.diagnostics()

    assert diagnostics["pending"] == 1
    assert diagnostics["pending_requests"][0]["request_id"] == pending.request_id
    assert diagnostics["recent_completed"] == 2
    assert diagnostics["completed_by_status"] == {"failed": 1, "approved": 1}
    assert diagnostics["failed_request_reasons"] == {FAILURE_NO_ACTIONABLE_ROUTE: 1}
    assert diagnostics["completed_step_counts"] == {
        "applied": 1,
        "blocked": 1,
        "failed": 1,
        "skipped": 1,
    }
    assert diagnostics["completed_blocked_reasons"] == {"manual_hold_active": 1}
    assert diagnostics["completed_failed_reasons"] == {"apply_error": 1}
    assert diagnostics["completed_skipped_reasons"] == {"dependency_blocked": 1}
    assert diagnostics["recent_completed_requests"][1]["apply_result"]["blocked_steps"] == 1


@pytest.mark.asyncio
async def test_controller_timeout_apply_uses_apply_handler(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    calls: list[tuple[str, str]] = []

    async def _apply(request: RuntimeActionRequest, status: str) -> RuntimeActionRequest:
        calls.append((request.request_id, status))
        return resolve_runtime_request(
            request,
            status=status,  # type: ignore[arg-type]
            apply_result=RuntimeApplyResult(applied_steps=1),
        )

    controller = RuntimeConfirmationController(_FakeHass(), apply_handler=_apply)
    request = _request(on_timeout="apply")

    controller.add_request(request)
    resolved = await controller.async_handle_timeout(request.request_id)

    assert calls == [(request.request_id, "timeout_applied")]
    assert resolved is not None
    assert resolved.status == "timeout_applied"


@pytest.mark.asyncio
async def test_controller_apply_handler_exception_marks_request_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )

    async def _apply(_request: RuntimeActionRequest, _status: str) -> RuntimeActionRequest:
        raise RuntimeError("boom")

    controller = RuntimeConfirmationController(_FakeHass(), apply_handler=_apply)
    request = _request()

    controller.add_request(request)
    resolved = await controller.async_handle_action_response(
        ActionableNotificationResponse(
            action_id=ACTION_RUNTIME_REQUEST_APPROVE,
            request_id=request.request_id,
        )
    )

    assert resolved is not None
    assert resolved.status == "failed"
    assert resolved.failure_reason == FAILURE_APPLY_ERROR
    diagnostics = controller.diagnostics()
    assert diagnostics["pending"] == 0
    assert diagnostics["completed_by_status"] == {"failed": 1}
    assert diagnostics["failed_request_reasons"] == {FAILURE_APPLY_ERROR: 1}


@pytest.mark.asyncio
async def test_controller_dismiss_response_cancels_timeout_and_records_stale_duplicate(
    monkeypatch,
) -> None:
    cancelled: list[bool] = []
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: cancelled.append(True),
    )
    controller = RuntimeConfirmationController(_FakeHass())
    request = _request()
    controller.add_request(request)

    first = await controller.async_handle_action_response(
        ActionableNotificationResponse(
            action_id=ACTION_RUNTIME_REQUEST_DISMISS,
            request_id=request.request_id,
        )
    )
    second = await controller.async_handle_action_response(
        ActionableNotificationResponse(
            action_id=ACTION_RUNTIME_REQUEST_DISMISS,
            request_id=request.request_id,
        )
    )

    assert first is not None
    assert first.status == "dismissed"
    assert second is None
    assert cancelled == [True]
    assert controller.diagnostics()["stale_responses"] == 1


@pytest.mark.asyncio
async def test_controller_action_event_dispatches_parsed_approve(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    calls: list[str] = []

    async def _apply(request: RuntimeActionRequest, status: str) -> RuntimeActionRequest:
        calls.append(status)
        return resolve_runtime_request(
            request,
            status=status,  # type: ignore[arg-type]
            apply_result=RuntimeApplyResult(applied_steps=1),
        )

    hass = _FakeHass()
    controller = RuntimeConfirmationController(hass, apply_handler=_apply)
    request = _request()
    controller.add_request(request)

    resolved = await controller.async_handle_action_event(
        SimpleNamespace(
            data={
                "action": ACTION_RUNTIME_REQUEST_APPROVE,
                "action_data": {"request_id": request.request_id},
            }
        )
    )

    assert resolved is not None
    assert resolved.status == "approved"
    assert calls == ["approved"]


@pytest.mark.asyncio
async def test_controller_concurrent_approve_is_first_writer_wins(monkeypatch) -> None:
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


@pytest.mark.asyncio
async def test_controller_create_request_sends_actionable_notification(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    hass = _FakeHass()
    hass.services.available["mobile_app_phone"] = object()
    controller = RuntimeConfirmationController(
        hass,
        event_pipeline=HeimaEventPipeline(hass),
        notifications_config_provider=lambda: {
            "recipients": {"resident": ["mobile_app_phone"]},
            "route_targets": ["resident"],
            "notification_service_capabilities": {"mobile_app_phone": {"supports_actions": True}},
        },
    )
    request = _request()

    resolved = await controller.async_create_request(request)

    assert resolved.status == "pending"
    assert hass.services.calls
    payload = hass.services.calls[-1][2]
    assert payload["data"]["tag"] == request.request_id
    assert payload["data"]["actions"] == [
        {"action": ACTION_RUNTIME_REQUEST_APPROVE, "title": "Yes"},
        {"action": ACTION_RUNTIME_REQUEST_DISMISS, "title": "No"},
    ]


@pytest.mark.asyncio
async def test_controller_create_request_fails_without_actionable_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    hass = _FakeHass()
    hass.services.available["mobile_app_phone"] = object()
    controller = RuntimeConfirmationController(
        hass,
        event_pipeline=HeimaEventPipeline(hass),
        notifications_config_provider=lambda: {
            "recipients": {"resident": ["mobile_app_phone"]},
            "route_targets": ["resident"],
            "notification_service_capabilities": {"mobile_app_phone": {"supports_actions": False}},
        },
    )

    resolved = await controller.async_create_request(_request())

    assert resolved.status == "failed"
    assert resolved.failure_reason == "no_actionable_route"
    assert hass.services.calls == []


@pytest.mark.asyncio
async def test_controller_records_requested_then_failed_for_missing_actionable_route(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.runtime_confirmation_controller.async_call_later",
        lambda _hass, _delay, _callback: lambda: None,
    )
    outcomes: list[str] = []
    hass = _FakeHass()
    controller = RuntimeConfirmationController(
        hass,
        event_pipeline=HeimaEventPipeline(hass),
        notifications_config_provider=lambda: {},
        outcome_handler=lambda _request, status: outcomes.append(status),
    )

    resolved = await controller.async_create_request(_request())

    assert resolved.status == "failed"
    assert outcomes == ["pending", "failed"]


def _request(
    *,
    on_timeout: str = "skip",
    reaction_id: str = "reaction-1",
    occurrence_key: str = "occurrence-1",
) -> RuntimeActionRequest:
    now = datetime.now(timezone.utc)
    return RuntimeActionRequest(
        reaction_id=reaction_id,
        reaction_type="context_conditioned_lighting_scene",
        occurrence_key=occurrence_key,
        title="Apply scene?",
        message="Apply the stored scene.",
        apply_steps=(ApplyStep(domain="light", target="light.studio", action="light.turn_on"),),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        on_timeout=on_timeout,  # type: ignore[arg-type]
        confirmation_targets=("resident",),
    )
