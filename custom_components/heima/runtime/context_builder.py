"""Builds EventContext snapshots from HA state and learning configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..room_sources import room_learning_source_entity_ids
from .event_store import EventContext
from .external_context import ExternalContext
from .snapshot import DecisionSnapshot

_MAX_SIGNALS = 10


class ContextBuilder:
    """Produces EventContext at event time by reading configured HA entities.

    A single ContextBuilder instance is shared across all recorder behaviors.
    The coordinator owns it and calls update_config() on options reload.

    Config keys (from options snapshot):
      outdoor_lux_entity:      entity_id of an illuminance sensor (lx)
      outdoor_temp_entity:     entity_id of a temperature sensor (°C)
      weather_entity:          entity_id of a weather integration
      context_signal_entities: list of entity_ids (max 10) that are strong
                               context signals for learning (projector, TV, etc.)
      rooms[*].learning_sources: room-scoped signals used as learnable trigger/context inputs
    """

    def __init__(self, hass: HomeAssistant, config: dict[str, Any] | None = None) -> None:
        self._hass = hass
        self._outdoor_lux_entity: str | None = None
        self._outdoor_temp_entity: str | None = None
        self._weather_entity: str | None = None
        self._signal_entities: list[str] = []
        self._ext_ctx: ExternalContext | None = None
        if config:
            self.update_config(config)

    def update_ext_ctx(self, ext_ctx: ExternalContext | None) -> None:
        """Store the latest ExternalContext so behaviors don't need to pass it explicitly."""
        self._ext_ctx = ext_ctx

    def update_config(self, config: dict[str, Any]) -> None:
        """Update builder from options or learning config (called on options reload)."""
        learning = dict(config.get("learning", {})) if "learning" in config else dict(config)
        self._outdoor_lux_entity = learning.get("outdoor_lux_entity") or None
        self._outdoor_temp_entity = learning.get("outdoor_temp_entity") or None
        self._weather_entity = learning.get("weather_entity") or None
        raw_signals = learning.get("context_signal_entities", [])
        merged_signals: list[str] = []
        if isinstance(config.get("rooms"), list):
            for room in config.get("rooms", []):
                merged_signals.extend(room_learning_source_entity_ids(room))
        if isinstance(raw_signals, list):
            merged_signals.extend(str(entity_id) for entity_id in raw_signals)

        deduped: list[str] = []
        seen: set[str] = set()
        for entity_id in merged_signals:
            clean = str(entity_id).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)
        self._signal_entities = deduped[:_MAX_SIGNALS]

    def build(
        self,
        snapshot: DecisionSnapshot,
        ext_ctx: ExternalContext | None = None,
    ) -> EventContext:
        """Build an EventContext from snapshot + current HA state.

        ext_ctx (explicit) takes precedence; falls back to self._ext_ctx (set by engine each cycle)
        when no direct entity is configured in learning settings.
        """
        effective = ext_ctx or self._ext_ctx
        dt = datetime.fromisoformat(snapshot.ts)
        local_dt = dt_util.as_local(dt)
        return EventContext(
            weekday=local_dt.weekday(),
            minute_of_day=local_dt.hour * 60 + local_dt.minute,
            month=local_dt.month,
            house_state=snapshot.house_state,
            occupants_count=snapshot.people_count,
            occupied_rooms=tuple(snapshot.occupied_rooms),
            outdoor_lux=self._read_float(self._outdoor_lux_entity) or (effective.outdoor_lux if effective else None),
            outdoor_temp=self._read_outdoor_temp() or (effective.outdoor_temp if effective else None),
            weather_condition=self._read_weather_condition() or (effective.weather_condition if effective else None),
            signals=self._read_signals(),
        )

    # ------------------------------------------------------------------

    def _read_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _read_outdoor_temp(self) -> float | None:
        # Prefer dedicated temp entity; fall back to weather.temperature attribute
        val = self._read_float(self._outdoor_temp_entity)
        if val is not None:
            return val
        if self._weather_entity:
            state = self._hass.states.get(self._weather_entity)
            if state is not None:
                try:
                    return float(state.attributes.get("temperature", ""))
                except (ValueError, TypeError):
                    pass
        return None

    def _read_weather_condition(self) -> str | None:
        if not self._weather_entity:
            return None
        state = self._hass.states.get(self._weather_entity)
        if state is None:
            return None
        return str(state.state) or None

    def _read_signals(self) -> dict[str, str]:
        signals: dict[str, str] = {}
        for entity_id in self._signal_entities:
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            signals[entity_id] = state.state
        return signals
