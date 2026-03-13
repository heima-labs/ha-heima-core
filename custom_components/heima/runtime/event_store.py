"""Persistent event storage for Heima learning analyzers."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


@dataclass(frozen=True)
class PresenceEvent:
    """Presence transition event used by pattern analyzers."""

    ts: str
    event_type: Literal["presence"]
    transition: Literal["arrive", "depart"]
    weekday: int
    minute_of_day: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeatingEvent:
    """Heating setpoint event used by pattern analyzers."""

    ts: str
    event_type: Literal["heating"]
    house_state: str
    temperature_set: float
    source: Literal["user", "heima"]
    env: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HouseStateEvent:
    """House-state transition event used by pattern analyzers."""

    ts: str
    event_type: Literal["house_state"]
    from_state: str
    to_state: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PatternEvent = PresenceEvent | HeatingEvent | HouseStateEvent


class EventStore:
    """Durable append/query storage for analyzer input events."""

    STORAGE_KEY = "heima_pattern_events"
    STORAGE_VERSION = 1
    MAX_RECORDS = 5000
    TTL_DAYS = 60
    _SAVE_DELAY_S = 30

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._events: deque[PatternEvent] = deque(maxlen=self.MAX_RECORDS)
        self._loaded = False

    async def async_load(self) -> None:
        """Load persisted events into memory."""
        raw = await self._store.async_load()
        events_raw = []
        if isinstance(raw, dict):
            data = raw.get("data")
            if isinstance(data, dict):
                events_raw = data.get("events", [])

        self._events.clear()
        if isinstance(events_raw, list):
            for item in events_raw:
                event = self._event_from_dict(item)
                if event is not None:
                    self._events.append(event)

        self._evict_ttl()
        self._loaded = True
        self._schedule_save()

    async def async_append(self, event: PatternEvent) -> None:
        """Append a pattern event, enforcing TTL and max capacity."""
        if not self._loaded:
            await self.async_load()
        self._evict_ttl()
        self._events.append(event)
        self._schedule_save()

    async def async_query(
        self,
        *,
        event_type: str | None = None,
        since: str | None = None,
        limit: int | None = None,
    ) -> list[PatternEvent]:
        """Query events by optional type/time filters."""
        if not self._loaded:
            await self.async_load()

        since_dt = self._parse_iso_ts(since) if since else None
        results: list[PatternEvent] = []
        for event in self._events:
            if event_type and event.event_type != event_type:
                continue
            if since_dt is not None:
                event_dt = self._parse_iso_ts(event.ts)
                if event_dt is None or event_dt < since_dt:
                    continue
            results.append(event)

        if limit is not None and limit >= 0:
            return results[-limit:]
        return results

    async def async_clear(self) -> None:
        """Clear all persisted and in-memory events."""
        self._events.clear()
        self._schedule_save()

    async def async_flush(self) -> None:
        """Immediately flush current state to HA storage."""
        await self._store.async_save(self._serialize())

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"events": [event.as_dict() for event in self._events]}}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, self._SAVE_DELAY_S)

    def _evict_ttl(self) -> None:
        if not self._events:
            return
        cutoff = datetime.now(UTC) - timedelta(days=self.TTL_DAYS)
        filtered: deque[PatternEvent] = deque(maxlen=self.MAX_RECORDS)
        for event in self._events:
            event_dt = self._parse_iso_ts(event.ts)
            if event_dt is None:
                continue
            if event_dt >= cutoff:
                filtered.append(event)
        self._events = filtered

    def _event_from_dict(self, raw: Any) -> PatternEvent | None:
        if not isinstance(raw, dict):
            return None
        event_type = raw.get("event_type")
        if event_type == "presence":
            try:
                return PresenceEvent(
                    ts=str(raw["ts"]),
                    event_type="presence",
                    transition=str(raw["transition"]),  # type: ignore[arg-type]
                    weekday=int(raw["weekday"]),
                    minute_of_day=int(raw["minute_of_day"]),
                )
            except (KeyError, TypeError, ValueError):
                return None
        if event_type == "heating":
            try:
                raw_env = raw.get("env", {})
                env = {str(k): str(v) for k, v in raw_env.items()} if isinstance(raw_env, dict) else {}
                return HeatingEvent(
                    ts=str(raw["ts"]),
                    event_type="heating",
                    house_state=str(raw["house_state"]),
                    temperature_set=float(raw["temperature_set"]),
                    source=str(raw["source"]),  # type: ignore[arg-type]
                    env=env,
                )
            except (KeyError, TypeError, ValueError):
                return None
        if event_type == "house_state":
            try:
                return HouseStateEvent(
                    ts=str(raw["ts"]),
                    event_type="house_state",
                    from_state=str(raw["from_state"]),
                    to_state=str(raw["to_state"]),
                )
            except (KeyError, TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _parse_iso_ts(ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

