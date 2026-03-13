"""Behavior that records lightweight transition events for analyzers."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..event_store import EventStore, HouseStateEvent, PresenceEvent
from ..snapshot import DecisionSnapshot
from .base import HeimaBehavior


class EventRecorderBehavior(HeimaBehavior):
    """Observe DecisionSnapshot transitions and append PatternEvents."""

    def __init__(self, hass: HomeAssistant, store: EventStore) -> None:
        self._hass = hass
        self._store = store
        self._previous_snapshot: DecisionSnapshot | None = None

    @property
    def behavior_id(self) -> str:
        return "event_recorder"

    def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        previous = self._previous_snapshot
        self._previous_snapshot = snapshot
        if previous is None:
            return

        if previous.anyone_home != snapshot.anyone_home:
            transition = "arrive" if snapshot.anyone_home else "depart"
            weekday, minute_of_day = self._weekday_and_minute(snapshot.ts)
            event = PresenceEvent(
                ts=snapshot.ts,
                event_type="presence",
                transition=transition,
                weekday=weekday,
                minute_of_day=minute_of_day,
            )
            self._hass.async_create_task(self._store.async_append(event))

        if previous.house_state != snapshot.house_state:
            event = HouseStateEvent(
                ts=snapshot.ts,
                event_type="house_state",
                from_state=previous.house_state,
                to_state=snapshot.house_state,
            )
            self._hass.async_create_task(self._store.async_append(event))

    @staticmethod
    def _weekday_and_minute(ts: str) -> tuple[int, int]:
        dt = datetime.fromisoformat(ts)
        local_dt = dt_util.as_local(dt)
        return local_dt.weekday(), (local_dt.hour * 60) + local_dt.minute

