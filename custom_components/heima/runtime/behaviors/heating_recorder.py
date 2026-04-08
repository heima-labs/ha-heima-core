"""Behavior that records HeatingEvent when the setpoint changes."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from ..context_builder import ContextBuilder
from ..event_store import EventStore, HeimaEvent
from ..snapshot import DecisionSnapshot
from .base import HeimaBehavior


class HeatingRecorderBehavior(HeimaBehavior):
    """Record heating HeimaEvent on setpoint changes.

    Context signals (outdoor temp, weather, projector, etc.) are read by the
    shared ContextBuilder and stored in context.signals, enabling the
    HeatingPatternAnalyzer to detect correlations between setpoint preferences
    and environmental context.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store: EventStore,
        context_builder: ContextBuilder,
    ) -> None:
        self._hass = hass
        self._store = store
        self._context_builder = context_builder
        self._previous_setpoint: float | None = None
        self._previous_house_state: str | None = None

    @property
    def behavior_id(self) -> str:
        return "heating_recorder"

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        prev_setpoint = self._previous_setpoint
        prev_house_state = self._previous_house_state
        self._previous_setpoint = snapshot.heating_setpoint
        self._previous_house_state = snapshot.house_state

        if snapshot.heating_setpoint is None:
            return
        if snapshot.heating_setpoint == prev_setpoint and snapshot.house_state == prev_house_state:
            return

        context = self._context_builder.build(snapshot)
        event = HeimaEvent(
            ts=snapshot.ts,
            event_type="heating",
            context=context,
            source=snapshot.heating_source or "unknown",
            data={
                "temperature_set": snapshot.heating_setpoint,
                "provenance": dict(snapshot.heating_provenance or {}),
            },
        )
        self._hass.async_create_task(self._store.async_append(event))

    def reset_learning_state(self) -> None:
        self._previous_setpoint = None
        self._previous_house_state = None
