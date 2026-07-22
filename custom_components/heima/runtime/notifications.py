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

AUDIENCE_TARGET_ADMINS = "admins"
AUDIENCE_TARGET_RESIDENTS = "residents"
AUDIENCE_TARGET_ROLES = (AUDIENCE_TARGET_ADMINS, AUDIENCE_TARGET_RESIDENTS)

AUDIENCE_POLICY_DISABLED = "disabled"
AUDIENCE_POLICY_OBSERVABILITY = "observability"
AUDIENCE_POLICY_ADMINS = "admins"
AUDIENCE_POLICY_RESIDENTS = "residents"
AUDIENCE_POLICY_RESIDENTS_AND_ADMINS = "residents_and_admins"
AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE = "admins_after_persistence"
AUDIENCE_POLICY_RESIDENTS_AND_ADMINS_AFTER_PERSISTENCE = (
    "residents_and_admins_after_persistence"
)
AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE = (
    "residents_and_admins_when_critical_else_admins_after_persistence"
)

AUDIENCE_POLICY_VALUES = frozenset(
    {
        AUDIENCE_POLICY_DISABLED,
        AUDIENCE_POLICY_OBSERVABILITY,
        AUDIENCE_POLICY_ADMINS,
        AUDIENCE_POLICY_RESIDENTS,
        AUDIENCE_POLICY_RESIDENTS_AND_ADMINS,
        AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE,
        AUDIENCE_POLICY_RESIDENTS_AND_ADMINS_AFTER_PERSISTENCE,
        AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE,
    }
)

DEFAULT_AUDIENCE_TARGETS = {
    AUDIENCE_TARGET_ADMINS: [AUDIENCE_TARGET_ADMINS],
    AUDIENCE_TARGET_RESIDENTS: [AUDIENCE_TARGET_RESIDENTS],
}

DEFAULT_AUDIENCE_POLICY = {
    "people": {"push": AUDIENCE_POLICY_OBSERVABILITY},
    "house_state": {"push": AUDIENCE_POLICY_OBSERVABILITY},
    "reaction": {"push": AUDIENCE_POLICY_OBSERVABILITY},
    "occupancy_mismatch": {"push": AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE},
    "security_critical": {"push": AUDIENCE_POLICY_RESIDENTS_AND_ADMINS},
    "security_presence_mismatch": {
        "push": AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE
    },
    "system_config_issue": {"push": AUDIENCE_POLICY_ADMINS},
}

DEFAULT_STARTUP_NOTIFICATION_GRACE_S = 300
DEFAULT_PERSISTENCE_THRESHOLDS = {
    "occupancy_mismatch": 600,
    "security_presence_mismatch": 300,
    "installation_config_issue": 300,
}
DEFAULT_AGGREGATION = {
    "presence_transition_window_s": 120,
    "mismatch_window_s": 300,
    "global_burst_limit": {
        "max_notifications": 2,
        "window_s": 60,
    },
}


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


@dataclass(frozen=True)
class NotificationDeliveryDecision:
    """Structured Notification Delivery Policy decision for an informational event."""

    outcome: str
    event_family: str
    push_policy: str
    target_roles: tuple[str, ...] = ()
    route_targets: tuple[str, ...] = ()
    security_critical: bool = False
    reason: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def should_deliver(self) -> bool:
        return self.outcome == "deliver" and bool(self.route_targets)


class NotificationDeliveryPolicy:
    """Pure decision engine for informational event push delivery.

    AP2 intentionally does not send notifications and does not mutate runtime
    state. Stateful controls such as persistence, aggregation, deduplication,
    rate limiting, and burst limits are integrated in later AP phases.
    """

    OUTCOME_DELIVER = "deliver"
    OUTCOME_OBSERVABILITY_ONLY = "observability_only"
    OUTCOME_DISABLED = "disabled"
    OUTCOME_STARTUP_GRACE = "startup_grace"
    OUTCOME_WAITING_PERSISTENCE = "waiting_persistence"
    OUTCOME_SUPPRESSED_AGGREGATION = "suppressed_aggregation"
    OUTCOME_SUPPRESSED_CATEGORY = "suppressed_category"
    OUTCOME_SUPPRESSED_DEDUP = "suppressed_dedup"
    OUTCOME_SUPPRESSED_RATE_LIMIT = "suppressed_rate_limit"
    OUTCOME_SUPPRESSED_BURST = "suppressed_burst"
    OUTCOME_MISSING_AUDIENCE_TARGET = "missing_audience_target"

    def decide(
        self,
        event: HeimaEvent,
        notifications_config: dict[str, Any] | None,
        *,
        category_enabled: bool = True,
    ) -> NotificationDeliveryDecision:
        config = normalize_notification_policy_config(notifications_config)
        family = classify_notification_event_family(event)
        security_critical = is_security_critical_event(event)
        policy = _policy_for_event(
            family=family,
            security_critical=security_critical,
            audience_policy=config["audience_policy"],
        )
        diagnostics = {
            "event_type": event.type,
            "event_key": event.key,
            "event_severity": event.severity,
            "event_family": family,
            "push_policy": policy,
            "security_critical": security_critical,
        }

        if not category_enabled:
            return NotificationDeliveryDecision(
                outcome=self.OUTCOME_SUPPRESSED_CATEGORY,
                event_family=family,
                push_policy=policy,
                security_critical=security_critical,
                reason="event_category_disabled",
                diagnostics=diagnostics,
            )

        if policy == AUDIENCE_POLICY_DISABLED:
            return NotificationDeliveryDecision(
                outcome=self.OUTCOME_DISABLED,
                event_family=family,
                push_policy=policy,
                security_critical=security_critical,
                reason="policy_disabled",
                diagnostics=diagnostics,
            )
        if policy == AUDIENCE_POLICY_OBSERVABILITY:
            return NotificationDeliveryDecision(
                outcome=self.OUTCOME_OBSERVABILITY_ONLY,
                event_family=family,
                push_policy=policy,
                security_critical=security_critical,
                reason="policy_observability_only",
                diagnostics=diagnostics,
            )

        target_roles = _target_roles_for_policy(policy)
        if _policy_requires_persistence(policy) and not security_critical:
            return NotificationDeliveryDecision(
                outcome=self.OUTCOME_WAITING_PERSISTENCE,
                event_family=family,
                push_policy=policy,
                target_roles=target_roles,
                security_critical=security_critical,
                reason="persistence_required",
                diagnostics=diagnostics,
            )

        route_targets = _route_targets_for_roles(
            config["audience_targets"],
            target_roles=target_roles,
        )
        if not route_targets:
            return NotificationDeliveryDecision(
                outcome=self.OUTCOME_MISSING_AUDIENCE_TARGET,
                event_family=family,
                push_policy=policy,
                target_roles=target_roles,
                security_critical=security_critical,
                reason="missing_audience_target",
                diagnostics=diagnostics,
            )

        return NotificationDeliveryDecision(
            outcome=self.OUTCOME_DELIVER,
            event_family=family,
            push_policy=policy,
            target_roles=target_roles,
            route_targets=route_targets,
            security_critical=security_critical,
            reason="policy_deliver",
            diagnostics=diagnostics,
        )


def normalize_notification_policy_config(
    notifications_config: dict[str, Any] | None,
    *,
    sanitize_unresolved_targets: bool = False,
) -> dict[str, Any]:
    """Return notification config with normalized AP policy fields.

    This function is intentionally side-effect free. AP1 only materializes and
    sanitizes the Notification Delivery Policy model; delivery decisions are
    introduced by later AP phases.
    """
    config = dict(notifications_config or {})
    recipients = _normalize_recipient_mapping(config.get("recipients"))
    recipient_groups = _normalize_recipient_mapping(config.get("recipient_groups"))
    valid_targets = set(recipients) | set(recipient_groups)

    config["audience_targets"] = _normalize_audience_targets(
        config.get("audience_targets"),
        valid_targets=valid_targets,
        sanitize_unresolved_targets=sanitize_unresolved_targets,
    )
    config["audience_policy"] = _normalize_audience_policy(config.get("audience_policy"))
    config["startup_notification_grace_s"] = _non_negative_int(
        config.get("startup_notification_grace_s"),
        DEFAULT_STARTUP_NOTIFICATION_GRACE_S,
    )
    config["persistence_thresholds"] = _normalize_int_mapping(
        config.get("persistence_thresholds"),
        defaults=DEFAULT_PERSISTENCE_THRESHOLDS,
    )
    config["aggregation"] = _normalize_aggregation(config.get("aggregation"))
    return config


def classify_notification_event_family(event: HeimaEvent) -> str:
    """Classify a Heima event into the AP audience-policy family vocabulary."""
    event_type = str(event.type or "").strip()
    category = event_type.split(".", 1)[0] or "system"
    context = event.context if isinstance(event.context, dict) else {}
    subtype = str(context.get("subtype") or "").strip()

    if is_security_critical_event(event):
        return "security_critical"
    if event_type in {"security.armed_away_but_home", "security_presence_mismatch"}:
        return "security_presence_mismatch"
    if category == "security" and subtype == "armed_away_but_home":
        return "security_presence_mismatch"
    if category == "occupancy" or event_type.startswith("invariant.presence_without_occupancy"):
        return "occupancy_mismatch"
    if category == "system" and (
        "config" in event_type or "installation" in event_type or "health" in event_type
    ):
        return "system_config_issue"
    if category in {"people", "house_state", "reaction"}:
        return category
    return category or "system_config_issue"


def is_security_critical_event(event: HeimaEvent) -> bool:
    """Return whether an event is a bounded security-critical condition."""
    event_type = str(event.type or "").strip()
    context = event.context if isinstance(event.context, dict) else {}
    subtype = str(context.get("subtype") or "").strip()
    security_state = str(context.get("security_state") or "").strip()
    if event_type in {"security.alarm_triggered", "security.triggered"}:
        return True
    if event_type.endswith(".triggered") and event_type.startswith("security."):
        return True
    if security_state == "triggered":
        return True
    if event_type == "security.armed_away_but_home":
        return True
    if subtype == "armed_away_but_home":
        return True
    return security_state == "armed_away" and bool(context.get("people_home_list"))


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

        self._stats.emitted += 1
        self._stats.last_event = event

        payload = event.as_dict()
        self._hass.bus.async_fire(EVENT_HEIMA_EVENT, payload)

        if dedup_window_s > 0:
            last_seen = self._last_seen_ts.get(event.key)
            if last_seen is not None and (now - last_seen) < dedup_window_s:
                self._stats.dropped_dedup += 1
                self._stats.suppressed_by_key[event.key] = (
                    self._stats.suppressed_by_key.get(event.key, 0) + 1
                )
                self._last_seen_ts[event.key] = now
                return True
            self._last_seen_ts[event.key] = now

        if rate_limit_per_key_s > 0:
            last_emit = self._last_emitted_ts.get(event.key)
            if last_emit is not None and (now - last_emit) < rate_limit_per_key_s:
                self._stats.dropped_rate_limited += 1
                self._stats.suppressed_by_key[event.key] = (
                    self._stats.suppressed_by_key.get(event.key, 0) + 1
                )
                return True

        self._last_emitted_ts[event.key] = now

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


def _normalize_audience_targets(
    raw: Any,
    *,
    valid_targets: set[str],
    sanitize_unresolved_targets: bool,
) -> dict[str, list[str]]:
    source = raw if isinstance(raw, dict) else {}
    normalized: dict[str, list[str]] = {}
    for role in AUDIENCE_TARGET_ROLES:
        values = _string_list(source.get(role, DEFAULT_AUDIENCE_TARGETS[role]))
        clean: list[str] = []
        seen: set[str] = set()
        for target in values:
            if target == AUDIENCE_POLICY_OBSERVABILITY:
                continue
            if sanitize_unresolved_targets and target not in valid_targets:
                continue
            if target in seen:
                continue
            seen.add(target)
            clean.append(target)
        normalized[role] = clean
    return normalized


def _policy_for_event(
    *,
    family: str,
    security_critical: bool,
    audience_policy: dict[str, dict[str, str]],
) -> str:
    if security_critical:
        if family == "security_presence_mismatch":
            policy = audience_policy.get("security_presence_mismatch", {}).get("push")
            if policy == AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE:
                return AUDIENCE_POLICY_RESIDENTS_AND_ADMINS
        return audience_policy.get("security_critical", {}).get(
            "push", AUDIENCE_POLICY_RESIDENTS_AND_ADMINS
        )
    return audience_policy.get(family, {"push": AUDIENCE_POLICY_OBSERVABILITY})["push"]


def _target_roles_for_policy(policy: str) -> tuple[str, ...]:
    if policy in {
        AUDIENCE_POLICY_ADMINS,
        AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE,
    }:
        return (AUDIENCE_TARGET_ADMINS,)
    if policy == AUDIENCE_POLICY_RESIDENTS:
        return (AUDIENCE_TARGET_RESIDENTS,)
    if policy in {
        AUDIENCE_POLICY_RESIDENTS_AND_ADMINS,
        AUDIENCE_POLICY_RESIDENTS_AND_ADMINS_AFTER_PERSISTENCE,
        AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE,
    }:
        return (AUDIENCE_TARGET_RESIDENTS, AUDIENCE_TARGET_ADMINS)
    return ()


def _policy_requires_persistence(policy: str) -> bool:
    return policy in {
        AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE,
        AUDIENCE_POLICY_RESIDENTS_AND_ADMINS_AFTER_PERSISTENCE,
        AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE,
    }


def _route_targets_for_roles(
    audience_targets: dict[str, list[str]],
    *,
    target_roles: tuple[str, ...],
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for role in target_roles:
        for target in audience_targets.get(role, []):
            if target and target not in seen:
                seen.add(target)
                result.append(target)
    return tuple(result)


def _normalize_audience_policy(raw: Any) -> dict[str, dict[str, str]]:
    source = raw if isinstance(raw, dict) else {}
    normalized: dict[str, dict[str, str]] = {}
    for family, default_policy in DEFAULT_AUDIENCE_POLICY.items():
        family_cfg = source.get(family)
        push = ""
        if isinstance(family_cfg, dict):
            push = str(family_cfg.get("push") or "").strip()
        elif family_cfg is not None:
            push = str(family_cfg).strip()
        if push not in AUDIENCE_POLICY_VALUES:
            push = default_policy["push"]
        normalized[family] = {"push": push}
    return normalized


def _normalize_aggregation(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    burst = source.get("global_burst_limit")
    burst_source = burst if isinstance(burst, dict) else {}
    default_burst = DEFAULT_AGGREGATION["global_burst_limit"]
    return {
        "presence_transition_window_s": _non_negative_int(
            source.get("presence_transition_window_s"),
            int(DEFAULT_AGGREGATION["presence_transition_window_s"]),
        ),
        "mismatch_window_s": _non_negative_int(
            source.get("mismatch_window_s"),
            int(DEFAULT_AGGREGATION["mismatch_window_s"]),
        ),
        "global_burst_limit": {
            "max_notifications": _non_negative_int(
                burst_source.get("max_notifications"),
                int(default_burst["max_notifications"]),
            ),
            "window_s": _non_negative_int(
                burst_source.get("window_s"),
                int(default_burst["window_s"]),
            ),
        },
    }


def _normalize_int_mapping(raw: Any, *, defaults: dict[str, int]) -> dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    return {
        key: _non_negative_int(source.get(key), default)
        for key, default in defaults.items()
    }


def _normalize_recipient_mapping(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): _string_list(value) for key, value in raw.items() if str(key).strip()}


def _string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        values = raw.replace(",", "\n").splitlines()
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = [raw]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _non_negative_int(raw: Any, default: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(0, value)


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
