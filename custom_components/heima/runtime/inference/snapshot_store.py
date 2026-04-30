"""Snapshot persistence for v2 inference."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


@dataclass(frozen=True)
class HouseSnapshot:
    """Unit of observation persisted for inference modules."""

    ts: str
    weekday: int
    minute_of_day: int
    anyone_home: bool
    named_present: tuple[str, ...]
    room_occupancy: dict[str, bool]
    detected_activities: tuple[str, ...] = field(default_factory=tuple)
    house_state: str = ""
    heating_setpoint: float | None = None
    lighting_scenes: dict[str, str] = field(default_factory=dict)
    security_armed: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize the snapshot to HA storage."""
        return {
            "ts": self.ts,
            "weekday": self.weekday,
            "minute_of_day": self.minute_of_day,
            "anyone_home": self.anyone_home,
            "named_present": list(self.named_present),
            "room_occupancy": dict(self.room_occupancy),
            "detected_activities": list(self.detected_activities),
            "house_state": self.house_state,
            "heating_setpoint": self.heating_setpoint,
            "lighting_scenes": dict(self.lighting_scenes),
            "security_armed": self.security_armed,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> HouseSnapshot | None:
        """Deserialize a snapshot, ignoring malformed records."""
        try:
            ts = str(raw["ts"])
            weekday = int(raw["weekday"])
            minute_of_day = int(raw["minute_of_day"])
            anyone_home = bool(raw["anyone_home"])
        except (KeyError, TypeError, ValueError):
            return None

        named_present = _tuple_of_str(raw.get("named_present", ()))
        room_occupancy = _dict_of_bool(raw.get("room_occupancy", {}))
        detected_activities = _tuple_of_str(raw.get("detected_activities", ()))
        lighting_scenes = _dict_of_str(raw.get("lighting_scenes", {}))
        heating_raw = raw.get("heating_setpoint")
        try:
            heating_setpoint = None if heating_raw is None else float(heating_raw)
        except (TypeError, ValueError):
            heating_setpoint = None

        return cls(
            ts=ts,
            weekday=weekday,
            minute_of_day=minute_of_day,
            anyone_home=anyone_home,
            named_present=tuple(sorted(named_present)),
            room_occupancy=room_occupancy,
            detected_activities=tuple(sorted(detected_activities)),
            house_state=str(raw.get("house_state") or ""),
            heating_setpoint=heating_setpoint,
            lighting_scenes=lighting_scenes,
            security_armed=bool(raw.get("security_armed", False)),
        )

    def semantic_key(self) -> tuple[Any, ...]:
        """Return the observed state key used for write-on-change deduplication."""
        return (
            self.anyone_home,
            self.named_present,
            tuple(sorted(self.room_occupancy.items())),
            self.detected_activities,
            self.house_state,
            self.heating_setpoint,
            tuple(sorted(self.lighting_scenes.items())),
            self.security_armed,
        )


class SnapshotStore:
    """Durable append/query storage for inference snapshots."""

    STORAGE_KEY = "heima_snapshots"
    STORAGE_VERSION = 1
    MAX_RECORDS = 10000
    TTL_DAYS = 90
    _SAVE_DELAY_S = 30

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._snapshots: deque[HouseSnapshot] = deque(maxlen=self.MAX_RECORDS)
        self._loaded = False

    async def async_load(self) -> None:
        """Load persisted snapshots into memory."""
        raw = await self._store.async_load()
        snapshots_raw = []
        if isinstance(raw, dict):
            data = raw.get("data")
            if isinstance(data, dict):
                snapshots_raw = data.get("snapshots", [])

        self._snapshots.clear()
        if isinstance(snapshots_raw, list):
            for item in snapshots_raw:
                if not isinstance(item, dict):
                    continue
                snapshot = HouseSnapshot.from_dict(item)
                if snapshot is not None:
                    self._snapshots.append(snapshot)

        self._evict_ttl()
        self._loaded = True
        self._schedule_save()

    async def async_append(self, snapshot: HouseSnapshot) -> None:
        """Append a snapshot, enforcing TTL and max capacity."""
        if not self._loaded:
            await self.async_load()
        self._evict_ttl()
        self._snapshots.append(snapshot)
        self._schedule_save()

    async def async_append_if_changed(self, snapshot: HouseSnapshot) -> bool:
        """Append only when the observed state differs from the last snapshot."""
        if not self._loaded:
            await self.async_load()
        self._evict_ttl()
        if self._snapshots and self._snapshots[-1].semantic_key() == snapshot.semantic_key():
            return False
        self._snapshots.append(snapshot)
        self._schedule_save()
        return True

    async def async_clear(self) -> None:
        """Clear all persisted and in-memory snapshots."""
        self._snapshots.clear()
        self._schedule_save()

    async def async_flush(self) -> None:
        """Immediately flush current state to HA storage."""
        await self._store.async_save(self._serialize())

    def snapshots(self, *, limit: int | None = None) -> list[HouseSnapshot]:
        """Return snapshots in insertion order."""
        items = list(self._snapshots)
        if limit is not None and limit >= 0:
            return items[-limit:]
        return items

    def diagnostics(self) -> dict[str, Any]:
        """Return storage diagnostics."""
        return {
            "total_snapshots": len(self._snapshots),
            "max_records": self.MAX_RECORDS,
            "ttl_days": self.TTL_DAYS,
            "storage_key": self.STORAGE_KEY,
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"snapshots": [snapshot.as_dict() for snapshot in self._snapshots]}}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, self._SAVE_DELAY_S)

    def _evict_ttl(self, *, now: datetime | None = None) -> None:
        if not self._snapshots:
            return
        cutoff = (now or datetime.now(UTC)) - timedelta(days=self.TTL_DAYS)
        kept = [
            snapshot
            for snapshot in self._snapshots
            if (parsed := _parse_iso(snapshot.ts)) is not None and parsed >= cutoff
        ]
        self._snapshots = deque(kept, maxlen=self.MAX_RECORDS)


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _tuple_of_str(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list | tuple):
        return ()
    return tuple(str(item) for item in raw if str(item).strip())


def _dict_of_bool(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): bool(value) for key, value in raw.items() if str(key).strip()}


def _dict_of_str(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if str(key).strip() and str(value).strip()
    }
