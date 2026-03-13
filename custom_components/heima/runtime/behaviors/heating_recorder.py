"""Behavior that records HeatingEvent when the setpoint changes."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from ..event_store import EventStore, HeatingEvent
from ..snapshot import DecisionSnapshot
from .base import HeimaBehavior


class HeatingRecorderBehavior(HeimaBehavior):
    """Record HeatingEvent on setpoint changes, with configurable env context."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: EventStore,
        context_entities: list[str] | None = None,
    ) -> None:
        self._hass = hass
        self._store = store
        self._context_entities: list[str] = list(context_entities or [])
        self._previous_setpoint: float | None = None
        self._previous_house_state: str | None = None

    @property
    def behavior_id(self) -> str:
        return "heating_recorder"

    def set_context_entities(self, entities: list[str]) -> None:
        self._context_entities = list(entities)

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        prev_setpoint = self._previous_setpoint
        prev_house_state = self._previous_house_state
        self._previous_setpoint = snapshot.heating_setpoint
        self._previous_house_state = snapshot.house_state

        if snapshot.heating_setpoint is None:
            return
        # record only when setpoint or house_state changes
        if (
            snapshot.heating_setpoint == prev_setpoint
            and snapshot.house_state == prev_house_state
        ):
            return

        env = self._read_env()
        event = HeatingEvent(
            ts=snapshot.ts,
            event_type="heating",
            house_state=snapshot.house_state,
            temperature_set=snapshot.heating_setpoint,
            source=snapshot.heating_source,  # type: ignore[arg-type]
            env=env,
        )
        self._hass.async_create_task(self._store.async_append(event))

    def _read_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        for entity_id in self._context_entities:
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            env[entity_id] = state.state
            if entity_id.startswith("weather."):
                for attr in ("temperature", "humidity", "wind_speed"):
                    val = state.attributes.get(attr)
                    if val is not None:
                        env[f"{entity_id}.{attr}"] = str(val)
        return env
