"""Notification/event pipeline helpers."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound, ServiceValidationError

from ..const import EVENT_HEIMA_EVENT
from .contracts import HeimaEvent

_LOGGER = logging.getLogger(__name__)
_MAX_DEFERRED_ROUTE_DELIVERIES = 128


@dataclass
class EventPipelineStats:
    """Simple runtime counters for event pipeline behavior."""

    emitted: int = 0
    dropped_dedup: int = 0
    dropped_rate_limited: int = 0
    notify_route_unavailable: int = 0
    notify_route_errors: int = 0
    notify_target_resolution_errors: int = 0
    notify_route_deferred_dropped: int = 0
    notify_route_delivered: int = 0
    notify_route_retried: int = 0
    notify_actionable_no_route: int = 0
    notify_actionable_delivered: int = 0
    notify_actionable_errors: int = 0
    last_event: HeimaEvent | None = None
    suppressed_by_key: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "dropped_dedup": self.dropped_dedup,
            "dropped_rate_limited": self.dropped_rate_limited,
            "notify_route_unavailable": self.notify_route_unavailable,
            "notify_route_errors": self.notify_route_errors,
            "notify_target_resolution_errors": self.notify_target_resolution_errors,
            "notify_route_deferred_dropped": self.notify_route_deferred_dropped,
            "notify_route_delivered": self.notify_route_delivered,
            "notify_route_retried": self.notify_route_retried,
            "notify_actionable_no_route": self.notify_actionable_no_route,
            "notify_actionable_delivered": self.notify_actionable_delivered,
            "notify_actionable_errors": self.notify_actionable_errors,
            "last_event": self.last_event.as_dict() if self.last_event else None,
            "suppressed_by_key": dict(self.suppressed_by_key),
        }


@dataclass(frozen=True)
class NotificationAction:
    """Provider-neutral actionable notification button."""

    action_id: str
    label: str


@dataclass(frozen=True)
class ActionableNotification:
    """Provider-neutral actionable notification payload."""

    title: str
    message: str
    actions: tuple[NotificationAction, ...]
    request_id: str
    category: str = "runtime_confirmation"


@dataclass(frozen=True)
class ActionableDeliveryResult:
    """Result of attempting actionable notification delivery."""

    delivered_routes: tuple[str, ...] = ()
    unresolved_targets: tuple[str, ...] = ()
    skipped_non_actionable_routes: tuple[str, ...] = ()
    failure_reason: str = ""

    @property
    def delivered(self) -> bool:
        return bool(self.delivered_routes)


@dataclass(frozen=True)
class ActionableNotificationResponse:
    """Parsed response from an actionable notification event."""

    action_id: str
    request_id: str
    raw: dict[str, Any] = field(default_factory=dict)


class HeimaEventPipeline:
    """Deduplicates, rate-limits, and emits Heima events."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._last_seen_ts: dict[str, float] = {}
        self._last_emitted_ts: dict[str, float] = {}
        self._stats = EventPipelineStats()
        self._schema_incompatible_routes: set[str] = set()
        self._deferred_route_deliveries: deque[tuple[HeimaEvent, str]] = deque(
            maxlen=_MAX_DEFERRED_ROUTE_DELIVERIES
        )

    @property
    def stats(self) -> EventPipelineStats:
        return self._stats

    async def async_emit(
        self,
        event: HeimaEvent,
        *,
        routes: list[str] | None = None,
        recipients: dict[str, list[str]] | None = None,
        recipient_groups: dict[str, list[str]] | None = None,
        route_targets: list[str] | None = None,
        dedup_window_s: int,
        rate_limit_per_key_s: int,
    ) -> bool:
        now = time.monotonic()

        if dedup_window_s > 0:
            last_seen = self._last_seen_ts.get(event.key)
            if last_seen is not None and (now - last_seen) < dedup_window_s:
                self._stats.dropped_dedup += 1
                self._stats.suppressed_by_key[event.key] = (
                    self._stats.suppressed_by_key.get(event.key, 0) + 1
                )
                self._last_seen_ts[event.key] = now
                return False
            self._last_seen_ts[event.key] = now

        if rate_limit_per_key_s > 0:
            last_emit = self._last_emitted_ts.get(event.key)
            if last_emit is not None and (now - last_emit) < rate_limit_per_key_s:
                self._stats.dropped_rate_limited += 1
                self._stats.suppressed_by_key[event.key] = (
                    self._stats.suppressed_by_key.get(event.key, 0) + 1
                )
                return False

        self._last_emitted_ts[event.key] = now
        self._stats.emitted += 1
        self._stats.last_event = event

        payload = event.as_dict()
        self._hass.bus.async_fire(EVENT_HEIMA_EVENT, payload)

        await self._flush_deferred_route_deliveries()

        effective_routes = self._resolve_routes(
            routes=routes or [],
            recipients=recipients or {},
            recipient_groups=recipient_groups or {},
            route_targets=route_targets or [],
        )
        for route in effective_routes:
            if not route:
                continue
            await self._deliver_or_defer_route(event=event, route=route, is_retry=False)

        return True

    async def async_send_actionable(
        self,
        notification: ActionableNotification,
        *,
        recipients: dict[str, list[str]] | None = None,
        recipient_groups: dict[str, list[str]] | None = None,
        route_targets: list[str] | None = None,
        notification_service_capabilities: dict[str, dict[str, Any]] | None = None,
    ) -> ActionableDeliveryResult:
        """Send an actionable notification through routes that support actions.

        This method is intentionally separate from `async_emit`: actionable
        runtime confirmations fail closed instead of degrading to text-only
        notification delivery.
        """
        route_resolution = self._resolve_route_targets(
            recipients=recipients or {},
            recipient_groups=recipient_groups or {},
            route_targets=route_targets or [],
        )
        actionable_routes: list[str] = []
        skipped_non_actionable: list[str] = []
        capabilities = notification_service_capabilities or {}
        for route in route_resolution.routes:
            if _route_supports_actions(route, capabilities):
                actionable_routes.append(route)
            else:
                skipped_non_actionable.append(route)

        if not actionable_routes:
            self._stats.notify_actionable_no_route += 1
            return ActionableDeliveryResult(
                unresolved_targets=tuple(route_resolution.unresolved_targets),
                skipped_non_actionable_routes=tuple(skipped_non_actionable),
                failure_reason="no_actionable_route",
            )

        payload = self._actionable_payload(notification)
        delivered: list[str] = []
        for route in actionable_routes:
            if await self._try_deliver_actionable_payload(route=route, payload=payload):
                delivered.append(route)

        if not delivered:
            self._stats.notify_actionable_errors += 1
            return ActionableDeliveryResult(
                unresolved_targets=tuple(route_resolution.unresolved_targets),
                skipped_non_actionable_routes=tuple(skipped_non_actionable),
                failure_reason="delivery_failed",
            )

        self._stats.notify_actionable_delivered += len(delivered)
        return ActionableDeliveryResult(
            delivered_routes=tuple(delivered),
            unresolved_targets=tuple(route_resolution.unresolved_targets),
            skipped_non_actionable_routes=tuple(skipped_non_actionable),
        )

    async def _flush_deferred_route_deliveries(self) -> None:
        if not self._deferred_route_deliveries:
            return

        remaining: deque[tuple[HeimaEvent, str]] = deque(maxlen=_MAX_DEFERRED_ROUTE_DELIVERIES)
        while self._deferred_route_deliveries:
            event, route = self._deferred_route_deliveries.popleft()
            delivered = await self._try_deliver_route(event=event, route=route, is_retry=True)
            if not delivered:
                if len(remaining) == remaining.maxlen:
                    self._stats.notify_route_deferred_dropped += 1
                    continue
                remaining.append((event, route))

        self._deferred_route_deliveries = remaining

    async def _deliver_or_defer_route(
        self, *, event: HeimaEvent, route: str, is_retry: bool
    ) -> None:
        delivered = await self._try_deliver_route(event=event, route=route, is_retry=is_retry)
        if delivered:
            return
        self._defer_route_delivery(event, route)

    async def _try_deliver_route(self, *, event: HeimaEvent, route: str, is_retry: bool) -> bool:
        if route in self._schema_incompatible_routes:
            return True

        if not self._notify_service_available(route):
            self._stats.notify_route_unavailable += 1
            _LOGGER.debug("Heima notify route unavailable (deferred): notify.%s", route)
            return False

        payload = self._notify_payload(event)
        try:
            await self._hass.services.async_call(
                "notify",
                route,
                payload,
                blocking=True,
            )
        except ServiceNotFound:
            # Race condition: service disappeared between availability check and call.
            self._stats.notify_route_unavailable += 1
            _LOGGER.warning(
                "Heima notify route missing at dispatch time (deferred): notify.%s", route
            )
            return False
        except (vol.Invalid, ServiceValidationError):
            # Some notify services use strict schemas. Try progressively smaller payloads.
            fallback_payloads = [
                {"title": payload.get("title", ""), "message": payload.get("message", "")},
                {"message": payload.get("message", "")},
            ]
            for fallback in fallback_payloads:
                try:
                    await self._hass.services.async_call(
                        "notify",
                        route,
                        fallback,
                        blocking=True,
                    )
                    _LOGGER.debug(
                        "Heima notify route delivered with fallback payload for notify.%s", route
                    )
                    self._stats.notify_route_delivered += 1
                    if is_retry:
                        self._stats.notify_route_retried += 1
                    return True
                except Exception:
                    continue

            self._schema_incompatible_routes.add(route)
            self._stats.notify_route_errors += 1
            _LOGGER.warning("Heima notify route disabled due incompatible schema: notify.%s", route)
            return True
        except Exception:  # pragma: no cover - defensive runtime protection
            self._stats.notify_route_errors += 1
            _LOGGER.exception("Heima notify route dispatch failed for notify.%s", route)
            return (
                True  # considered handled; do not block setup or loop forever on persistent errors
            )

        self._stats.notify_route_delivered += 1
        if is_retry:
            self._stats.notify_route_retried += 1
        return True

    def _defer_route_delivery(self, event: HeimaEvent, route: str) -> None:
        item = (event, route)
        # Keep latest attempts; bounded queue avoids unbounded growth during long outages.
        if len(self._deferred_route_deliveries) == self._deferred_route_deliveries.maxlen:
            self._stats.notify_route_deferred_dropped += 1
        self._deferred_route_deliveries.append(item)

    def _notify_service_available(self, route: str) -> bool:
        services_obj = getattr(self._hass, "services", None)
        if services_obj is None:
            return False
        async_services = getattr(services_obj, "async_services", None)
        if not callable(async_services):
            return False
        notify_services = async_services().get("notify", {})
        return route in notify_services

    def _notify_payload(self, event: HeimaEvent) -> dict[str, Any]:
        return {
            "title": event.title,
            "message": event.message,
        }

    def _actionable_payload(self, notification: ActionableNotification) -> dict[str, Any]:
        return {
            "title": notification.title,
            "message": notification.message,
            "data": {
                "tag": notification.request_id,
                "category": notification.category,
                "action_data": {"request_id": notification.request_id},
                "actions": [
                    {"action": action.action_id, "title": action.label}
                    for action in notification.actions
                    if action.action_id and action.label
                ],
            },
        }

    async def _try_deliver_actionable_payload(self, *, route: str, payload: dict[str, Any]) -> bool:
        if not self._notify_service_available(route):
            self._stats.notify_route_unavailable += 1
            return False
        try:
            await self._hass.services.async_call(
                "notify",
                route,
                payload,
                blocking=True,
            )
        except ServiceNotFound:
            self._stats.notify_route_unavailable += 1
            return False
        except (vol.Invalid, ServiceValidationError):
            self._stats.notify_route_errors += 1
            _LOGGER.warning(
                "Heima actionable notify route rejected payload schema: notify.%s", route
            )
            return False
        except Exception:  # pragma: no cover - defensive runtime protection
            self._stats.notify_route_errors += 1
            _LOGGER.exception("Heima actionable notify dispatch failed for notify.%s", route)
            return False
        return True

    def _resolve_routes(
        self,
        *,
        routes: list[str],
        recipients: dict[str, list[str]],
        recipient_groups: dict[str, list[str]],
        route_targets: list[str],
    ) -> list[str]:
        resolved: list[str] = []
        seen: set[str] = set()

        def add_route(route: str) -> None:
            if not route or route in seen:
                return
            seen.add(route)
            resolved.append(route)

        for route in routes:
            add_route(route)

        resolution = self._resolve_route_targets(
            recipients=recipients,
            recipient_groups=recipient_groups,
            route_targets=route_targets,
        )
        for route in resolution.routes:
            add_route(route)
        for target in resolution.unresolved_targets:
            self._stats.notify_target_resolution_errors += 1
            _LOGGER.warning("Heima notification target is undefined and was ignored: %s", target)

        return resolved

    def _resolve_route_targets(
        self,
        *,
        recipients: dict[str, list[str]],
        recipient_groups: dict[str, list[str]],
        route_targets: list[str],
    ) -> "_RouteResolution":
        resolved: list[str] = []
        unresolved: list[str] = []
        seen: set[str] = set()

        def add_route(route: str) -> None:
            normalized = _normalize_notify_service_name(route)
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            resolved.append(normalized)

        for target in route_targets:
            if target in recipients:
                for route in recipients[target]:
                    add_route(route)
                continue
            if target in recipient_groups:
                for recipient_id in recipient_groups[target]:
                    for route in recipients.get(recipient_id, []):
                        add_route(route)
                continue
            unresolved.append(target)

        return _RouteResolution(
            routes=tuple(resolved),
            unresolved_targets=tuple(unresolved),
        )


@dataclass(frozen=True)
class _RouteResolution:
    routes: tuple[str, ...]
    unresolved_targets: tuple[str, ...] = ()


def _normalize_notify_service_name(route: str) -> str:
    normalized = str(route or "").strip()
    if normalized.startswith("notify."):
        normalized = normalized.split(".", 1)[1]
    return normalized


def _route_supports_actions(route: str, capabilities: dict[str, dict[str, Any]]) -> bool:
    normalized = _normalize_notify_service_name(route)
    raw = capabilities.get(normalized)
    return isinstance(raw, dict) and bool(raw.get("supports_actions", False))


def parse_actionable_notification_response(
    event_data: dict[str, Any],
) -> ActionableNotificationResponse | None:
    """Parse Home Assistant mobile_app actionable notification event data."""
    action_id = str(event_data.get("action") or "").strip()
    if not action_id:
        return None
    action_data = event_data.get("action_data")
    request_id = ""
    if isinstance(action_data, dict):
        request_id = str(action_data.get("request_id") or "").strip()
    if not request_id:
        request_id = str(event_data.get("tag") or "").strip()
    if not request_id:
        return None
    return ActionableNotificationResponse(
        action_id=action_id,
        request_id=request_id,
        raw=dict(event_data),
    )
