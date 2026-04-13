"""Behavior that records canonical actuation events for room actuators."""

# mypy: disable-error-code=arg-type

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant

from ..context_builder import ContextBuilder
from ..event_store import EventStore, HeimaEvent
from ..snapshot import DecisionSnapshot
from .base import HeimaBehavior


class ActuationRecorderBehavior(HeimaBehavior):
    """Listen to actuator state changes and record user-observable actuation events.

    This canonicalizes fan / switch / climate followups used by cross-domain
    learning so analyzers no longer depend on raw state_change events.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store: EventStore,
        context_builder: ContextBuilder,
        entry: ConfigEntry,
    ) -> None:
        self._hass = hass
        self._store = store
        self._context_builder = context_builder
        self._entry = entry
        self._entity_to_room: dict[str, str] = {}
        self._last_snapshot: DecisionSnapshot | None = None
        self._unsub: Any = None

    @property
    def behavior_id(self) -> str:
        return "actuation_recorder"

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

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        self._last_snapshot = snapshot

    def reset_learning_state(self) -> None:
        self._last_snapshot = None

    async def _handle_state_changed(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id", "") or "")
        if not entity_id.startswith(("fan.", "switch.", "climate.")):
            return

        room_id = self._entity_to_room.get(entity_id)
        if not room_id or self._last_snapshot is None:
            return

        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return

        new_value = str(getattr(new_state, "state", "") or "").strip().lower()
        old_value = str(getattr(old_state, "state", "") or "").strip().lower() if old_state else ""
        if not new_value or new_value == old_value:
            return

        domain = entity_id.split(".", 1)[0]
        action = self._normalize_action(domain=domain, new_value=new_value)
        if action is None:
            return

        context = self._context_builder.build(self._last_snapshot)
        actuation_event = HeimaEvent(
            ts=new_state.last_changed.isoformat(),
            event_type="actuation",
            context=context,
            source="user",
            domain=domain,
            subject_type="entity",
            subject_id=entity_id,
            room_id=room_id,
            correlation_id=self._extract_correlation_id(event, new_state),
            data={
                "entity_id": entity_id,
                "room_id": room_id,
                "action": action,
                "new_state": new_value,
                "old_state": old_value or None,
            },
        )
        self._hass.async_create_task(self._store.async_append(actuation_event))

    @staticmethod
    def _normalize_action(*, domain: str, new_value: str) -> str | None:
        if domain in {"fan", "switch"}:
            if new_value in {"on", "off"}:
                return new_value
            return None
        if domain == "climate":
            return new_value
        return None

    def _sync_listener_subscription(self) -> None:
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

    def _build_entity_room_map(self) -> dict[str, str]:
        from homeassistant.helpers.device_registry import async_get as async_get_dr
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
        device_registry = async_get_dr(self._hass)
        entity_to_room: dict[str, str] = {}
        for entry in entity_registry.entities.values():
            if not entry.entity_id.startswith(("fan.", "switch.", "climate.")):
                continue
            entity_area = str(entry.area_id or "").strip()
            if entity_area and entity_area in area_to_room:
                entity_to_room[entry.entity_id] = area_to_room[entity_area]
                continue

            device_id = getattr(entry, "device_id", None)
            if not device_id:
                continue
            device_entry = device_registry.devices.get(device_id)
            if not device_entry:
                continue
            device_area = str(getattr(device_entry, "area_id", "") or "").strip()
            if device_area and device_area in area_to_room:
                entity_to_room[entry.entity_id] = area_to_room[device_area]

        return entity_to_room

    def diagnostics(self) -> dict[str, Any]:
        return {
            "monitored_entities": len(self._entity_to_room),
            "entity_to_room": dict(self._entity_to_room),
        }
