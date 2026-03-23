"""Behavior that records LightingEvent when users change lights."""

from __future__ import annotations

import time
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant

from ..context_builder import ContextBuilder
from ..event_store import EventStore, HeimaEvent
from ..snapshot import DecisionSnapshot
from .base import HeimaBehavior

# Seconds after a Heima lighting apply within which state changes are attributed to Heima.
# Scenes are applied with blocking=False so changes arrive asynchronously.
_HEIMA_APPLY_TTL_S = 5.0


class LightingRecorderBehavior(HeimaBehavior):
    """Listen to HA light entity state changes and record user-initiated ones.

    Source discrimination: if a light entity's room was applied by Heima within
    _HEIMA_APPLY_TTL_S seconds, the change is attributed to Heima and skipped.
    Everything else is attributed to the user and recorded as a LightingEvent.

    Entity → room mapping is derived from HA entity registry (area_id) matched
    against the room configs (area_id field in options["rooms"]).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store: EventStore,
        context_builder: ContextBuilder,
        entry: ConfigEntry,
        lighting_apply_state_fn: Callable[[], dict[str, Any]],
    ) -> None:
        self._hass = hass
        self._store = store
        self._context_builder = context_builder
        self._entry = entry
        self._lighting_apply_state_fn = lighting_apply_state_fn
        self._entity_to_room: dict[str, str] = {}
        self._last_snapshot: DecisionSnapshot | None = None
        self._unsub: Any = None

    @property
    def behavior_id(self) -> str:
        return "lighting_recorder"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        self._entity_to_room = self._build_entity_room_map()
        self._sync_listener_subscription()

    async def async_teardown(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        self._entity_to_room = self._build_entity_room_map()
        self._sync_listener_subscription()

    # ------------------------------------------------------------------
    # Snapshot hook (context caching)
    # ------------------------------------------------------------------

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        self._last_snapshot = snapshot

    def reset_learning_state(self) -> None:
        self._last_snapshot = None

    # ------------------------------------------------------------------
    # State change handler
    # ------------------------------------------------------------------

    async def _handle_state_changed(self, event: Event) -> None:
        entity_id = event.data.get("entity_id", "")
        if not entity_id.startswith("light."):
            return

        room_id = self._entity_to_room.get(entity_id)
        if not room_id:
            return

        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return
        if new_state.state not in ("on", "off"):
            return
        if old_state is not None and old_state.state == new_state.state:
            return  # no change in on/off status

        # Source discrimination
        if self._is_recent_heima_apply(entity_id=entity_id, room_id=room_id):
            return  # Heima caused this change

        if self._last_snapshot is None:
            return  # no context available yet

        context = self._context_builder.build(self._last_snapshot)
        attrs = new_state.attributes
        action: str = new_state.state  # "on" or "off"

        brightness: int | None = None
        color_temp_kelvin: int | None = None
        rgb_color: list[int] | None = None

        if action == "on":
            raw_brightness = attrs.get("brightness")
            if raw_brightness is not None:
                try:
                    brightness = int(raw_brightness)
                except (ValueError, TypeError):
                    pass

            raw_ctek = attrs.get("color_temp_kelvin")
            if raw_ctek is not None:
                try:
                    color_temp_kelvin = int(raw_ctek)
                except (ValueError, TypeError):
                    pass

            raw_rgb = attrs.get("rgb_color")
            if isinstance(raw_rgb, (list, tuple)) and len(raw_rgb) == 3:
                try:
                    rgb_color = [int(raw_rgb[0]), int(raw_rgb[1]), int(raw_rgb[2])]
                except (ValueError, TypeError):
                    pass

        lighting_event = HeimaEvent(
            ts=new_state.last_changed.isoformat(),
            event_type="lighting",
            context=context,
            source="user",
            domain="lighting",
            subject_type="entity",
            subject_id=entity_id,
            room_id=room_id,
            correlation_id=self._extract_correlation_id(event, new_state),
            data={
                "entity_id": entity_id,
                "room_id": room_id,
                "action": action,
                "scene": None,  # direct entity change; no scene context
                "brightness": brightness,
                "color_temp_kelvin": color_temp_kelvin,
                "rgb_color": rgb_color,
            },
        )
        self._hass.async_create_task(self._store.async_append(lighting_event))

    def _sync_listener_subscription(self) -> None:
        """Keep the state_changed listener aligned with whether we have tracked lights."""
        should_listen = bool(self._entity_to_room)
        if should_listen and self._unsub is None:
            self._unsub = self._hass.bus.async_listen(
                EVENT_STATE_CHANGED, self._handle_state_changed
            )
        elif not should_listen and self._unsub is not None:
            self._unsub()
            self._unsub = None

    @staticmethod
    def _extract_correlation_id(event: Event, new_state: Any) -> str | None:
        """Use HA context id when available so related entity changes can be grouped later."""
        for candidate in (
            getattr(new_state, "context", None),
            event.data.get("context"),
        ):
            context_id = getattr(candidate, "id", None)
            if isinstance(context_id, str) and context_id:
                return context_id
            if isinstance(candidate, dict):
                raw_id = candidate.get("id")
                if isinstance(raw_id, str) and raw_id:
                    return raw_id
        return None

    def _is_recent_heima_apply(self, *, entity_id: str, room_id: str) -> bool:
        """Prefer entity-level apply provenance, then fall back to room-level timestamps."""
        apply_state = self._lighting_apply_state_fn()
        now = time.monotonic()

        entities = apply_state.get("entities", {}) if isinstance(apply_state, dict) else {}
        entity_apply = entities.get(entity_id) if isinstance(entities, dict) else None
        if isinstance(entity_apply, dict):
            applied_ts = entity_apply.get("applied_ts")
            if isinstance(applied_ts, (int, float)) and (now - applied_ts) < _HEIMA_APPLY_TTL_S:
                return True

        scripts = apply_state.get("scripts", {}) if isinstance(apply_state, dict) else {}
        if isinstance(scripts, dict):
            for payload in scripts.values():
                if not isinstance(payload, dict):
                    continue
                applied_ts = payload.get("applied_ts")
                if not isinstance(applied_ts, (int, float)) or (now - applied_ts) >= _HEIMA_APPLY_TTL_S:
                    continue
                expected_entity_ids = payload.get("expected_entity_ids")
                if isinstance(expected_entity_ids, list) and expected_entity_ids:
                    if entity_id in expected_entity_ids:
                        return True
                    continue
                script_room_id = payload.get("room_id")
                if isinstance(script_room_id, str) and script_room_id:
                    if script_room_id == room_id:
                        return True
                    continue
                return True

        rooms = apply_state.get("rooms", {}) if isinstance(apply_state, dict) else apply_state
        room_apply_ts = rooms.get(room_id, 0.0) if isinstance(rooms, dict) else 0.0
        return isinstance(room_apply_ts, (int, float)) and (now - room_apply_ts) < _HEIMA_APPLY_TTL_S

    # ------------------------------------------------------------------
    # Entity → room mapping
    # ------------------------------------------------------------------

    def _build_entity_room_map(self) -> dict[str, str]:
        """Map light entity_ids to room_ids via HA area registry."""
        from homeassistant.helpers.entity_registry import async_get as async_get_er

        area_to_room: dict[str, str] = {}
        for room in self._entry.options.get("rooms", []):
            room_id = str(room.get("room_id", "")).strip()
            area_id = str(room.get("area_id", "")).strip()
            if room_id and area_id:
                area_to_room[area_id] = room_id

        if not area_to_room:
            return {}

        entity_registry = async_get_er(self._hass)
        entity_to_room: dict[str, str] = {}
        for entry in entity_registry.entities.values():
            if not entry.entity_id.startswith("light."):
                continue
            entity_area = entry.area_id
            if entity_area and entity_area in area_to_room:
                entity_to_room[entry.entity_id] = area_to_room[entity_area]

        return entity_to_room

    def diagnostics(self) -> dict[str, Any]:
        return {
            "monitored_entities": len(self._entity_to_room),
            "entity_to_room": dict(self._entity_to_room),
        }
