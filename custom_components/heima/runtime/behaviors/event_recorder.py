"""Behavior that records lightweight transition events for analyzers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from ..context_builder import ContextBuilder
from ..event_store import EventStore, HeimaEvent
from ..snapshot import DecisionSnapshot
from .base import HeimaBehavior


class EventRecorderBehavior(HeimaBehavior):
    """Observe DecisionSnapshot transitions and append HeimaEvents."""

    def __init__(self, hass: HomeAssistant, store: EventStore, context_builder: ContextBuilder) -> None:
        self._hass = hass
        self._store = store
        self._context_builder = context_builder
        self._previous_snapshot: DecisionSnapshot | None = None

    @property
    def behavior_id(self) -> str:
        return "event_recorder"

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        previous = self._previous_snapshot
        self._previous_snapshot = snapshot
        if previous is None:
            return

        context = self._context_builder.build(snapshot)

        if previous.anyone_home != snapshot.anyone_home:
            transition = "arrive" if snapshot.anyone_home else "depart"
            event = HeimaEvent(
                ts=snapshot.ts,
                event_type="presence",
                context=context,
                source=None,
                data={"transition": transition},
            )
            self._hass.async_create_task(self._store.async_append(event))

    def reset_learning_state(self) -> None:
        self._previous_snapshot = None

        if previous.house_state != snapshot.house_state:
            event = HeimaEvent(
                ts=snapshot.ts,
                event_type="house_state",
                context=context,
                source=None,
                data={
                    "from_state": previous.house_state,
                    "to_state": snapshot.house_state,
                },
            )
            self._hass.async_create_task(self._store.async_append(event))
