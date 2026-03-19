"""Builds EventContext snapshots from HA state and learning configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .event_store import EventContext
from .snapshot import DecisionSnapshot

_MAX_SIGNALS = 10


class ContextBuilder:
    """Produces EventContext at event time by reading configured HA entities.

    A single ContextBuilder instance is shared across all recorder behaviors.
    The coordinator owns it and calls update_config() on options reload.

    Config keys (from options["learning"]):
      outdoor_lux_entity:      entity_id of an illuminance sensor (lx)
      outdoor_temp_entity:     entity_id of a temperature sensor (°C)
      weather_entity:          entity_id of a weather integration
      context_signal_entities: list of entity_ids (max 10) that are strong
                               context signals for learning (projector, TV, etc.)
    """

    def __init__(self, hass: HomeAssistant, config: dict[str, Any] | None = None) -> None:
        self._hass = hass
        self._outdoor_lux_entity: str | None = None
        self._outdoor_temp_entity: str | None = None
        self._weather_entity: str | None = None
        self._signal_entities: list[str] = []
        if config:
            self.update_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update builder from a learning config dict (called on options reload)."""
        self._outdoor_lux_entity = config.get("outdoor_lux_entity") or None
        self._outdoor_temp_entity = config.get("outdoor_temp_entity") or None
        self._weather_entity = config.get("weather_entity") or None
        raw_signals = config.get("context_signal_entities", [])
        self._signal_entities = list(raw_signals)[:_MAX_SIGNALS] if isinstance(raw_signals, list) else []

    def build(self, snapshot: DecisionSnapshot) -> EventContext:
        """Build an EventContext from snapshot + current HA state."""
        dt = datetime.fromisoformat(snapshot.ts)
        local_dt = dt_util.as_local(dt)
        return EventContext(
            weekday=local_dt.weekday(),
            minute_of_day=local_dt.hour * 60 + local_dt.minute,
            month=local_dt.month,
            house_state=snapshot.house_state,
            occupants_count=snapshot.people_count,
            occupied_rooms=tuple(snapshot.occupied_rooms),
            outdoor_lux=self._read_float(self._outdoor_lux_entity),
            outdoor_temp=self._read_outdoor_temp(),
            weather_condition=self._read_weather_condition(),
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
