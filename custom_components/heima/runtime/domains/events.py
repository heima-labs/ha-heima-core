"""EventsDomain: generic event queue and emission pipeline."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ...const import (
    DEFAULT_ENABLED_EVENT_CATEGORIES,
    EVENT_CATEGORIES_ALL,
)
from ..contracts import HeimaEvent
from ..notifications import HeimaEventPipeline
from ..state_store import CanonicalState

_LOGGER = logging.getLogger(__name__)


class EventsDomain:
    """Generic event queue + emission pipeline.

    Owns the pending-event list and the HeimaEventPipeline.
    Domain-specific "consistency" events (occupancy, security) are NOT here;
    they live in their respective domain handlers.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._pipeline = HeimaEventPipeline(hass)
        self._pending_events: list[HeimaEvent] = []
        self._suppressed_event_categories: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def pipeline(self) -> HeimaEventPipeline:
        return self._pipeline

    @property
    def suppressed_event_categories(self) -> dict[str, int]:
        return self._suppressed_event_categories

    # ------------------------------------------------------------------
    # Queue helpers (called by domain handlers and engine)
    # ------------------------------------------------------------------

    def queue_event(self, event: HeimaEvent) -> None:
        self._pending_events.append(event)

    def queue_people_transition_event(
        self,
        *,
        slug: str,
        prev_is_home: bool | None,
        is_home: bool,
        source: str,
        confidence: int,
    ) -> None:
        if prev_is_home is None or prev_is_home == is_home:
            return
        self.queue_event(
            HeimaEvent(
                type="people.arrive" if is_home else "people.leave",
                key=f"{'people.arrive' if is_home else 'people.leave'}.{slug}",
                severity="info",
                title="Person arrived" if is_home else "Person left",
                message=f"Person '{slug}' {'arrived' if is_home else 'left'}.",
                context={"person": slug, "source": source, "confidence": confidence},
            )
        )

    def queue_anonymous_transition_event(
        self,
        *,
        prev_is_on: bool | None,
        is_on: bool,
        source: str,
        confidence: int,
        weight: int,
    ) -> None:
        if prev_is_on is None or prev_is_on == is_on:
            return
        context: dict[str, Any] = {"source": source, "confidence": confidence}
        if is_on:
            context["weight"] = weight
        self.queue_event(
            HeimaEvent(
                type="people.anonymous_on" if is_on else "people.anonymous_off",
                key="people.anonymous",
                severity="info",
                title="Anonymous presence detected" if is_on else "Anonymous presence cleared",
                message=(
                    "Anonymous presence detected." if is_on else "Anonymous presence cleared."
                ),
                context=context,
            )
        )

    def queue_house_state_changed_event(
        self, *, previous: str | None, current: str, reason: str
    ) -> None:
        if previous is None or previous == "unknown" or previous == current:
            return
        self.queue_event(
            HeimaEvent(
                type="house_state.changed",
                key="house_state.changed",
                severity="info",
                title="House state changed",
                message=(
                    f"House state changed from '{previous}' to '{current}' (reason: {reason})."
                ),
                context={"from": previous, "to": current, "reason": reason},
            )
        )

    # ------------------------------------------------------------------
    # Category helpers
    # ------------------------------------------------------------------

    @staticmethod
    def event_category(event_type: str) -> str:
        prefix = str(event_type or "").split(".", 1)[0]
        return prefix or "system"

    def enabled_event_categories(self, notifications_config: dict[str, Any]) -> set[str]:
        raw = notifications_config.get("enabled_event_categories")
        if raw is None:
            return set(DEFAULT_ENABLED_EVENT_CATEGORIES) | {"system"}
        enabled = {str(v) for v in list(raw) if str(v)}
        enabled.add("system")  # system is always enabled by spec
        return enabled

    def event_enabled(self, event: HeimaEvent, notifications_config: dict[str, Any]) -> bool:
        category = self.event_category(event.type)
        if category == "system":
            return True
        known_categories = set(EVENT_CATEGORIES_ALL)
        if category not in known_categories:
            return True
        return category in self.enabled_event_categories(notifications_config)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "stats": self._pipeline.stats.as_dict(),
            "suppressed_event_categories": dict(self._suppressed_event_categories),
        }

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    async def async_emit_queued_events(
        self,
        *,
        notifications_config: dict[str, Any],
        state: CanonicalState,
    ) -> None:
        if not self._pending_events:
            self._sync_event_sensors(state)
            return

        queued = list(self._pending_events)
        self._pending_events.clear()
        for event in queued:
            await self.async_emit_event_obj(event, notifications_config=notifications_config)

        self._sync_event_sensors(state)

    async def async_emit_event_obj(
        self,
        event: HeimaEvent,
        *,
        notifications_config: dict[str, Any],
    ) -> bool:
        if not self.event_enabled(event, notifications_config):
            category = self.event_category(event.type)
            self._suppressed_event_categories[category] = (
                self._suppressed_event_categories.get(category, 0) + 1
            )
            _LOGGER.debug(
                "Heima event suppressed by category toggle: %s (%s)",
                event.type,
                category,
            )
            return False
        recipients, recipient_groups, route_targets = self._normalized_routing_inputs(
            notifications_config
        )
        return await self._pipeline.async_emit(
            event,
            routes=[],
            recipients=recipients,
            recipient_groups=recipient_groups,
            route_targets=route_targets,
            dedup_window_s=int(notifications_config.get("dedup_window_s", 60)),
            rate_limit_per_key_s=int(notifications_config.get("rate_limit_per_key_s", 300)),
        )

    def _normalized_routing_inputs(
        self, notifications_config: dict[str, Any]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
        """Extract routing inputs from notifications config."""
        recipients = dict(notifications_config.get("recipients", {}))
        recipient_groups = dict(notifications_config.get("recipient_groups", {}))
        route_targets = [
            str(t) for t in list(notifications_config.get("route_targets", [])) if str(t)
        ]
        return recipients, recipient_groups, route_targets

    # ------------------------------------------------------------------
    # Sync sensors
    # ------------------------------------------------------------------

    def sync_event_sensors(self, state: CanonicalState) -> None:
        """Public alias used by engine for external event emit path."""
        self._sync_event_sensors(state)

    def _sync_event_sensors(self, state: CanonicalState) -> None:
        stats = self._pipeline.stats.as_dict()
        if "heima_last_event" in state.sensors:
            last_event = stats.get("last_event") or {}
            state.set_sensor("heima_last_event", str(last_event.get("type", "")))
            state.set_sensor_attributes(
                "heima_last_event",
                {
                    "type": last_event.get("type", ""),
                    "key": last_event.get("key", ""),
                    "severity": last_event.get("severity", ""),
                    "title": last_event.get("title", ""),
                    "message": last_event.get("message", ""),
                    "context": last_event.get("context") or {},
                    "event_id": last_event.get("event_id", ""),
                    "ts": last_event.get("ts", ""),
                },
            )
        if "heima_event_stats" in state.sensors:
            last_event = stats.get("last_event") or {}
            summary = (
                f"emitted={stats.get('emitted', 0)} "
                f"dedup={stats.get('dropped_dedup', 0)} "
                f"rate={stats.get('dropped_rate_limited', 0)} "
                f"last={last_event.get('type', '')}"
            ).strip()
            state.set_sensor("heima_event_stats", summary[:255])
            state.set_sensor_attributes(
                "heima_event_stats",
                {
                    "emitted": stats.get("emitted", 0),
                    "dropped_dedup": stats.get("dropped_dedup", 0),
                    "dropped_rate_limited": stats.get("dropped_rate_limited", 0),
                    "suppressed_by_key": stats.get("suppressed_by_key", {}),
                    "last_event": last_event,
                    "raw_json": json.dumps(stats, sort_keys=True),
                    "suppressed_event_categories": dict(self._suppressed_event_categories),
                },
            )
