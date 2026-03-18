"""Persistent event storage for Heima learning analyzers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


@dataclass(frozen=True)
class EventContext:
    """House context snapshot captured at event time.

    Embedded in every HeimaEvent so analyzers can correlate actions with context
    (outdoor darkness, house state, who's home, strong-signal device states, etc.).
    """

    # --- Time (always present, derived from local datetime) ---
    weekday: int           # 0=Monday … 6=Sunday
    minute_of_day: int     # 0–1439 (local time)
    month: int             # 1–12 (season proxy)

    # --- Aggregated house state (always present) ---
    house_state: str

    # --- Occupancy (always present, derived from PeopleResult) ---
    occupants_count: int
    occupied_rooms: tuple[str, ...]  # tuple for frozen-dataclass compatibility

    # --- External environment (None if sensor not configured) ---
    outdoor_lux: float | None
    outdoor_temp: float | None
    weather_condition: str | None    # "sunny", "cloudy", "rainy", …

    # --- Strong signals: user-configured entities, max 10, entity_id → state ---
    signals: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "weekday": self.weekday,
            "minute_of_day": self.minute_of_day,
            "month": self.month,
            "house_state": self.house_state,
            "occupants_count": self.occupants_count,
            "occupied_rooms": list(self.occupied_rooms),
            "outdoor_lux": self.outdoor_lux,
            "outdoor_temp": self.outdoor_temp,
            "weather_condition": self.weather_condition,
            "signals": dict(self.signals),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EventContext":
        return cls(
            weekday=int(raw.get("weekday", 0)),
            minute_of_day=int(raw.get("minute_of_day", 0)),
            month=int(raw.get("month", 1)),
            house_state=str(raw.get("house_state", "")),
            occupants_count=int(raw.get("occupants_count", 0)),
            occupied_rooms=tuple(raw.get("occupied_rooms", [])),
            outdoor_lux=float(raw["outdoor_lux"]) if raw.get("outdoor_lux") is not None else None,
            outdoor_temp=float(raw["outdoor_temp"]) if raw.get("outdoor_temp") is not None else None,
            weather_condition=str(raw["weather_condition"]) if raw.get("weather_condition") else None,
            signals={str(k): str(v) for k, v in raw.get("signals", {}).items()},
        )


@dataclass(frozen=True)
class HeimaEvent:
    """Unified event type for all learning system pattern events.

    Every event carries a full EventContext so analyzers can detect correlations
    between actions and the state of the house at the time they occurred.

    Fields:
      ts          ISO-8601 UTC timestamp
      event_type  discriminator: "presence", "heating", "house_state", "lighting", …
      context     house context snapshot at event time
      source      "user" | "heima" | None (PresenceEvent / HouseStateEvent have None)
      data        event-specific payload (see below per event_type)

    data payloads by event_type:
      presence:    {"transition": "arrive"|"depart"}
      heating:     {"temperature_set": float}
      house_state: {"from_state": str, "to_state": str}
      lighting:    {"room_id": str, "action": "on"|"off", "scene": str|None,
                    "brightness": int|None, "color_temp_kelvin": int|None,
                    "rgb_color": [r,g,b]|None}
    """

    ts: str
    event_type: str
    context: EventContext
    source: str | None
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "event_type": self.event_type,
            "context": self.context.as_dict(),
            "source": self.source,
            "data": dict(self.data),
        }


# Single type alias — kept so import sites don't need updating when adding new event_types
PatternEvent = HeimaEvent


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
        self._events: deque[HeimaEvent] = deque(maxlen=self.MAX_RECORDS)
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

    async def async_append(self, event: HeimaEvent) -> None:
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
    ) -> list[HeimaEvent]:
        """Query events by optional type/time filters."""
        if not self._loaded:
            await self.async_load()

        since_dt = self._parse_iso_ts(since) if since else None
        results: list[HeimaEvent] = []
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

    def diagnostics(self) -> dict[str, Any]:
        from collections import Counter
        type_counts = Counter(e.event_type for e in self._events)
        return {
            "total_events": len(self._events),
            "max_records": self.MAX_RECORDS,
            "by_type": dict(type_counts),
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"events": [event.as_dict() for event in self._events]}}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, self._SAVE_DELAY_S)

    def _evict_ttl(self) -> None:
        if not self._events:
            return
        cutoff = datetime.now(UTC) - timedelta(days=self.TTL_DAYS)
        filtered: deque[HeimaEvent] = deque(maxlen=self.MAX_RECORDS)
        for event in self._events:
            event_dt = self._parse_iso_ts(event.ts)
            if event_dt is None:
                continue
            if event_dt >= cutoff:
                filtered.append(event)
        self._events = filtered

    def _event_from_dict(self, raw: Any) -> HeimaEvent | None:
        if not isinstance(raw, dict):
            return None
        event_type = raw.get("event_type")
        if not event_type:
            return None

        # Context: from nested "context" key, or reconstructed from legacy top-level fields
        if "context" in raw and isinstance(raw["context"], dict):
            try:
                context = EventContext.from_dict(raw["context"])
            except (KeyError, TypeError, ValueError):
                return None
        else:
            # Backward compat: old records had weekday/minute_of_day/house_state at top level
            context = EventContext(
                weekday=int(raw.get("weekday", 0)),
                minute_of_day=int(raw.get("minute_of_day", 0)),
                month=1,
                house_state=str(raw.get("house_state", "")),
                occupants_count=0,
                occupied_rooms=(),
                outdoor_lux=None,
                outdoor_temp=None,
                weather_condition=None,
                signals={},
            )

        source = raw.get("source")

        if "data" in raw and isinstance(raw["data"], dict):
            data = dict(raw["data"])
        else:
            data = self._legacy_data_from_raw(str(event_type), raw)

        try:
            return HeimaEvent(
                ts=str(raw["ts"]),
                event_type=str(event_type),
                context=context,
                source=str(source) if source is not None else None,
                data=data,
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _legacy_data_from_raw(event_type: str, raw: dict[str, Any]) -> dict[str, Any]:
        """Reconstruct data dict from legacy flat event format."""
        if event_type == "presence":
            return {"transition": str(raw.get("transition", "arrive"))}
        if event_type == "heating":
            raw_env = raw.get("env", {})
            signals = {str(k): str(v) for k, v in raw_env.items()} if isinstance(raw_env, dict) else {}
            return {
                "temperature_set": float(raw.get("temperature_set", 0.0)),
                "signals": signals,  # env migrated to signals
            }
        if event_type == "house_state":
            return {
                "from_state": str(raw.get("from_state", "")),
                "to_state": str(raw.get("to_state", "")),
            }
        return {}

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
