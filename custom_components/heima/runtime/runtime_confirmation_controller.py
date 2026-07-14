"""Home Assistant integration layer for runtime confirmation requests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .notifications import (
    ActionableDeliveryResult,
    ActionableNotification,
    ActionableNotificationResponse,
    HeimaEventPipeline,
    NotificationAction,
    parse_actionable_notification_response,
)
from .runtime_confirmation import (
    FAILURE_NO_ACTIONABLE_ROUTE,
    FAILURE_VALIDATION_FAILED,
    RuntimeActionRequest,
    RuntimeActionRequestRegistry,
    RuntimeApplyResult,
    RuntimeRequestStatus,
)

ACTION_RUNTIME_REQUEST_APPROVE = "heima.runtime_request.approve"
ACTION_RUNTIME_REQUEST_DISMISS = "heima.runtime_request.dismiss"
EVENT_MOBILE_APP_NOTIFICATION_ACTION = "mobile_app_notification_action"
SKIP_TIMEOUT_SKIPPED = "timeout_skipped"

RuntimeApplyHandler = Callable[
    [RuntimeActionRequest, RuntimeRequestStatus], Awaitable[RuntimeActionRequest]
]
NotificationsConfigProvider = Callable[[], dict[str, Any]]


class RuntimeConfirmationController:
    """Owns in-memory runtime requests, HA action responses, and timeout scheduling."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        apply_handler: RuntimeApplyHandler | None = None,
        event_pipeline: HeimaEventPipeline | None = None,
        notifications_config_provider: NotificationsConfigProvider | None = None,
        registry: RuntimeActionRequestRegistry | None = None,
    ) -> None:
        self._hass = hass
        self._apply_handler = apply_handler
        self._event_pipeline = event_pipeline
        self._notifications_config_provider = notifications_config_provider
        self._registry = registry or RuntimeActionRequestRegistry()
        self._timeout_handles: dict[str, Callable[[], None]] = {}
        self._unsub_action_events: Callable[[], None] | None = None

    @property
    def registry(self) -> RuntimeActionRequestRegistry:
        return self._registry

    async def async_initialize(self) -> None:
        """Subscribe to HA actionable notification response events."""
        self._unsubscribe_action_events()

        @callback
        def _handle(event: Event) -> None:
            self._hass.async_create_task(self.async_handle_action_event(event))

        self._unsub_action_events = self._hass.bus.async_listen(
            EVENT_MOBILE_APP_NOTIFICATION_ACTION,
            _handle,
        )

    async def async_shutdown(self) -> None:
        """Cancel scheduled timeouts and unsubscribe from HA events."""
        self._unsubscribe_action_events()
        for handle in list(self._timeout_handles.values()):
            handle()
        self._timeout_handles.clear()

    def add_request(self, request: RuntimeActionRequest) -> RuntimeActionRequest:
        """Add or reuse a pending runtime request and schedule its timeout."""
        registered = self._registry.add(request)
        if registered.request_id == request.request_id:
            self._schedule_timeout(registered)
        return registered

    async def async_create_request(self, request: RuntimeActionRequest) -> RuntimeActionRequest:
        """Register a runtime request and send its actionable notification."""
        registered = self.add_request(request)
        if registered.request_id != request.request_id:
            return registered

        delivery = await self._async_send_actionable_request(registered)
        if delivery.delivered:
            return registered

        self._cancel_timeout(registered.request_id)
        return (
            self._registry.resolve(
                registered.request_id,
                status="failed",
                failure_reason=delivery.failure_reason or FAILURE_NO_ACTIONABLE_ROUTE,
            )
            or registered
        )

    async def async_handle_action_event(self, event: Event) -> RuntimeActionRequest | None:
        """Handle a Home Assistant mobile app notification action event."""
        response = parse_actionable_notification_response(dict(event.data or {}))
        if response is None:
            return None
        return await self.async_handle_action_response(response)

    async def async_handle_action_response(
        self, response: ActionableNotificationResponse
    ) -> RuntimeActionRequest | None:
        """Resolve a parsed actionable notification response."""
        if response.action_id == ACTION_RUNTIME_REQUEST_DISMISS:
            self._cancel_timeout(response.request_id)
            return self._registry.resolve(response.request_id, status="dismissed")
        if response.action_id == ACTION_RUNTIME_REQUEST_APPROVE:
            return await self._async_process_apply_trigger(
                response.request_id,
                status="approved",
            )
        return None

    async def async_handle_timeout(self, request_id: str) -> RuntimeActionRequest | None:
        """Resolve a request timeout."""
        self._timeout_handles.pop(request_id, None)
        request = self._registry.get(request_id)
        if request is None:
            return None
        if request.on_timeout == "skip":
            return self._registry.resolve(
                request_id,
                status="timeout_skipped",
                apply_result=RuntimeApplyResult(
                    skipped_steps=len(request.apply_steps),
                    skipped_reasons={SKIP_TIMEOUT_SKIPPED: len(request.apply_steps)},
                ),
            )
        return await self._async_process_apply_trigger(request_id, status="timeout_applied")

    def diagnostics(self) -> dict[str, Any]:
        """Return serializable controller diagnostics."""
        data = self._registry.diagnostics().as_dict()
        data["scheduled_timeouts"] = sorted(self._timeout_handles)
        data["action_event_subscription_active"] = self._unsub_action_events is not None
        return data

    async def _async_send_actionable_request(
        self,
        request: RuntimeActionRequest,
    ) -> ActionableDeliveryResult:
        if self._event_pipeline is None or self._notifications_config_provider is None:
            return ActionableDeliveryResult(failure_reason=FAILURE_NO_ACTIONABLE_ROUTE)

        notifications_config = dict(self._notifications_config_provider())
        return await self._event_pipeline.async_send_actionable(
            ActionableNotification(
                title=request.title,
                message=request.message,
                request_id=request.request_id,
                actions=(
                    NotificationAction(ACTION_RUNTIME_REQUEST_APPROVE, "Yes"),
                    NotificationAction(ACTION_RUNTIME_REQUEST_DISMISS, "No"),
                ),
            ),
            recipients=dict(notifications_config.get("recipients", {})),
            recipient_groups=dict(notifications_config.get("recipient_groups", {})),
            route_targets=list(request.confirmation_targets),
            notification_service_capabilities=dict(
                notifications_config.get("notification_service_capabilities", {})
            ),
        )

    async def _async_process_apply_trigger(
        self,
        request_id: str,
        *,
        status: RuntimeRequestStatus,
    ) -> RuntimeActionRequest | None:
        self._cancel_timeout(request_id)
        request = self._registry.get(request_id)
        if request is None:
            return self._registry.resolve(request_id, status=status)

        if self._apply_handler is None:
            return self._registry.resolve(
                request_id,
                status="failed",
                failure_reason=FAILURE_VALIDATION_FAILED,
            )

        completed = await self._apply_handler(request, status)
        return self._registry.mark_completed(completed)

    def _schedule_timeout(self, request: RuntimeActionRequest) -> None:
        self._cancel_timeout(request.request_id)
        delay = max(0.0, (request.expires_at - datetime.now(UTC)).total_seconds())

        @callback
        def _handle(_now) -> None:  # type: ignore[no-untyped-def]
            self._hass.async_create_task(self.async_handle_timeout(request.request_id))

        self._timeout_handles[request.request_id] = async_call_later(
            self._hass,
            delay,
            _handle,
        )

    def _cancel_timeout(self, request_id: str) -> None:
        handle = self._timeout_handles.pop(request_id, None)
        if handle is not None:
            handle()

    def _unsubscribe_action_events(self) -> None:
        if self._unsub_action_events is not None:
            self._unsub_action_events()
            self._unsub_action_events = None
