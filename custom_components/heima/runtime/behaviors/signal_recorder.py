"""Behavior that records generic state-change events for configured learning signals."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant

from ..context_builder import ContextBuilder
from ..event_store import EventStore, HeimaEvent
from .base import HeimaBehavior


class SignalRecorderBehavior(HeimaBehavior):
    """Listen for state changes on configured learning signals and persist generic events."""

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
        self._tracked_entities: set[str] = set()
        self._entity_to_room: dict[str, str] = {}
        self._unsub: Any = None
        self._last_snapshot = None

    @property
    def behavior_id(self) -> str:
        return "signal_recorder"

    async def async_setup(self) -> None:
        self._refresh_config()
        self._sync_listener_subscription()

    async def async_teardown(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def on_snapshot(self, snapshot) -> None:
        self._last_snapshot = snapshot

    def reset_learning_state(self) -> None:
        self._last_snapshot = None

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        self._refresh_config(options)
        self._sync_listener_subscription()

    async def _handle_state_changed(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "")
        if entity_id not in self._tracked_entities:
            return
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None or self._last_snapshot is None:
            return
        if old_state is not None and old_state.state == new_state.state:
            return

        context = self._context_builder.build(self._last_snapshot)
        room_id = self._entity_to_room.get(entity_id)
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        payload = {
            "entity_id": entity_id,
            "old_state": old_state.state if old_state is not None else None,
            "new_state": new_state.state,
            "unit_of_measurement": new_state.attributes.get("unit_of_measurement"),
            "device_class": new_state.attributes.get("device_class"),
        }
        self._hass.async_create_task(
            self._store.async_append(
                HeimaEvent(
                    ts=new_state.last_changed.isoformat(),
                    event_type="state_change",
                    context=context,
                    source="unknown",
                    domain=domain,
                    subject_type="entity",
                    subject_id=entity_id,
                    room_id=room_id,
                    correlation_id=self._extract_correlation_id(event, new_state),
                    data=payload,
                )
            )
        )

    def _refresh_config(self, options: dict[str, Any] | None = None) -> None:
        cfg = dict(options or self._entry.options)
        learning = dict(cfg.get("learning", {}))
        raw_entities = learning.get("context_signal_entities", [])
        self._tracked_entities = {
            str(entity_id).strip()
            for entity_id in raw_entities
            if str(entity_id).strip()
        }
        self._entity_to_room = self._build_entity_room_map(cfg)

    def _sync_listener_subscription(self) -> None:
        should_listen = bool(self._tracked_entities)
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

    def _build_entity_room_map(self, options: dict[str, Any]) -> dict[str, str]:
        from homeassistant.helpers.entity_registry import async_get as async_get_er

        room_sources: dict[str, str] = {}
        area_to_room: dict[str, str] = {}
        for room in options.get("rooms", []):
            room_id = str(room.get("room_id", "")).strip()
            if not room_id:
                continue
            for source in room.get("sources", []):
                source_id = str(source).strip()
                if source_id:
                    room_sources[source_id] = room_id
            area_id = str(room.get("area_id", "")).strip()
            if area_id:
                area_to_room[area_id] = room_id

        if not area_to_room:
            return room_sources

        entity_registry = async_get_er(self._hass)
        entity_to_room = dict(room_sources)
        for entry in entity_registry.entities.values():
            entity_area = entry.area_id
            if entry.entity_id in self._tracked_entities and entity_area and entity_area in area_to_room:
                entity_to_room.setdefault(entry.entity_id, area_to_room[entity_area])
        return entity_to_room

    def diagnostics(self) -> dict[str, Any]:
        return {
            "tracked_entities": sorted(self._tracked_entities),
            "entity_to_room": dict(self._entity_to_room),
        }
