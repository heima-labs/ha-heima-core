"""Behavior that canonicalizes threshold signals before persisting them."""

# mypy: disable-error-code=arg-type

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant

from ...room_sources import room_learning_source_entity_ids
from ..context_builder import ContextBuilder
from ..event_store import EventStore, HeimaEvent
from .base import HeimaBehavior

_DEFAULT_BUCKETS: dict[str, list[tuple[float | None, str]]] = {
    "illuminance": [(30, "dark"), (100, "dim"), (300, "ok"), (None, "bright")],
    "carbon_dioxide": [(800, "ok"), (1200, "elevated"), (None, "high")],
    "humidity": [(40, "low"), (70, "ok"), (None, "high")],
}
_DEVICE_CLASS_TO_SIGNAL_NAME = {
    "illuminance": "room_lux",
    "carbon_dioxide": "room_co2",
    "humidity": "room_humidity",
}
_IGNORED_STATES = {"unknown", "unavailable", ""}


@dataclass(frozen=True)
class _TrackedSignal:
    room_id: str
    signal_name: str
    entity_id: str
    device_class: str
    buckets: tuple[tuple[float | None, str], ...]
    burst_threshold: float | None = None
    burst_window_s: int | None = None
    burst_direction: str = "up"


class EventCanonicalizer(HeimaBehavior):
    """Emit semantic room signal threshold events instead of raw state changes."""

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
        self._tracked_by_entity: dict[str, _TrackedSignal] = {}
        self._bucket_state: dict[tuple[str, str], str] = {}
        self._burst_baseline: dict[tuple[str, str], tuple[float, datetime]] = {}
        self._last_burst_ts: dict[tuple[str, str], datetime] = {}
        self._unsub: Any = None
        self._last_snapshot = None

    @property
    def behavior_id(self) -> str:
        return "event_canonicalizer"

    async def async_setup(self) -> None:
        self._refresh_config()
        self._sync_listener_subscription()
        self._populate_baseline_from_current_states()

    async def async_teardown(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def on_snapshot(self, snapshot) -> None:
        self._last_snapshot = snapshot
        self._periodic_sync(snapshot)

    def reset_learning_state(self) -> None:
        self._last_snapshot = None
        self._bucket_state.clear()
        self._burst_baseline.clear()
        self._last_burst_ts.clear()
        self._populate_baseline_from_current_states()

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        self._refresh_config(options)
        self._sync_listener_subscription()
        self._populate_baseline_from_current_states()

    async def _handle_state_changed(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "").strip()
        tracked = self._tracked_by_entity.get(entity_id)
        if tracked is None:
            return
        new_state = event.data.get("new_state")
        if new_state is None or self._last_snapshot is None:
            return
        self._maybe_emit_for_state_change(
            tracked=tracked,
            raw_state=str(new_state.state or "").strip(),
            ts=new_state.last_changed.isoformat(),
            source=None,
            snapshot=self._last_snapshot,
        )

    def diagnostics(self) -> dict[str, Any]:
        tracked = {
            entity_id: {
                "room_id": item.room_id,
                "signal_name": item.signal_name,
                "device_class": item.device_class,
                "buckets": [
                    {"upper_bound": upper_bound, "label": label}
                    for upper_bound, label in item.buckets
                ],
            }
            for entity_id, item in sorted(self._tracked_by_entity.items())
        }
        bucket_state = {
            f"{room_id}:{signal_name}": bucket
            for (room_id, signal_name), bucket in sorted(self._bucket_state.items())
        }
        burst_baseline = {
            f"{room_id}:{signal_name}": {"value": value, "ts": ts.isoformat()}
            for (room_id, signal_name), (value, ts) in sorted(self._burst_baseline.items())
        }
        last_burst_ts = {
            f"{room_id}:{signal_name}": ts.isoformat()
            for (room_id, signal_name), ts in sorted(self._last_burst_ts.items())
        }
        return {
            "tracked_entities": tracked,
            "bucket_state": bucket_state,
            "burst_baseline": burst_baseline,
            "last_burst_ts": last_burst_ts,
        }

    def bucket_for(self, room_id: str, signal_name: str) -> str | None:
        return self._bucket_state.get((room_id, signal_name))

    def burst_recent_for(self, room_id: str, signal_name: str, *, window_s: int) -> bool:
        last = self._last_burst_ts.get((room_id, signal_name))
        if last is None:
            return False
        return (datetime.now(UTC) - last).total_seconds() <= max(0, int(window_s))

    def _refresh_config(self, options: dict[str, Any] | None = None) -> None:
        cfg = dict(options or self._entry.options)
        tracked: dict[str, _TrackedSignal] = {}
        for raw_room in cfg.get("rooms", []) or []:
            if not isinstance(raw_room, dict):
                continue
            room_id = str(raw_room.get("room_id") or "").strip()
            if not room_id:
                continue
            for item in self._room_signal_specs(raw_room):
                tracked[item.entity_id] = item
        self._tracked_by_entity = tracked
        self._bucket_state = {
            key: value for key, value in self._bucket_state.items() if self._tracked_key_exists(key)
        }
        self._burst_baseline = {
            key: value
            for key, value in self._burst_baseline.items()
            if self._tracked_key_exists(key)
        }
        self._last_burst_ts = {
            key: value
            for key, value in self._last_burst_ts.items()
            if self._tracked_key_exists(key)
        }

    def _tracked_key_exists(self, key: tuple[str, str]) -> bool:
        room_id, signal_name = key
        return any(
            item.room_id == room_id and item.signal_name == signal_name
            for item in self._tracked_by_entity.values()
        )

    def _room_signal_specs(self, room_cfg: dict[str, Any]) -> list[_TrackedSignal]:
        room_id = str(room_cfg.get("room_id") or "").strip()
        signals = room_cfg.get("signals")
        tracked: list[_TrackedSignal] = []
        if isinstance(signals, list) and signals:
            for raw in signals:
                if not isinstance(raw, dict):
                    continue
                entity_id = str(raw.get("entity_id") or "").strip()
                signal_name = str(raw.get("signal_name") or "").strip()
                device_class = str(raw.get("device_class") or "").strip()
                buckets = self._normalize_buckets(raw.get("buckets"))
                if not entity_id or not signal_name or not device_class or not buckets:
                    continue
                tracked.append(
                    _TrackedSignal(
                        room_id=room_id,
                        signal_name=signal_name,
                        entity_id=entity_id,
                        device_class=device_class,
                        buckets=buckets,
                        burst_threshold=self._coerce_burst_threshold(raw.get("burst_threshold")),
                        burst_window_s=self._coerce_positive_int(raw.get("burst_window_s")),
                        burst_direction=self._normalize_burst_direction(raw.get("burst_direction")),
                    )
                )
            if tracked:
                return tracked

        for entity_id in room_learning_source_entity_ids(room_cfg):
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            device_class = str(getattr(state, "attributes", {}).get("device_class") or "").strip()
            default_buckets = _DEFAULT_BUCKETS.get(device_class)
            signal_name_value = _DEVICE_CLASS_TO_SIGNAL_NAME.get(device_class)
            if not default_buckets or signal_name_value is None:
                continue
            tracked.append(
                _TrackedSignal(
                    room_id=room_id,
                    signal_name=signal_name_value,
                    entity_id=entity_id,
                    device_class=device_class,
                    buckets=tuple(default_buckets),
                )
            )
        return tracked

    @staticmethod
    def _normalize_buckets(raw_buckets: Any) -> tuple[tuple[float | None, str], ...]:
        normalized: list[tuple[float | None, str]] = []
        if not isinstance(raw_buckets, list):
            return ()
        for raw in raw_buckets:
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label") or "").strip()
            upper_bound_raw = raw.get("upper_bound")
            if not label:
                continue
            upper_bound: float | None
            if upper_bound_raw in (None, ""):
                upper_bound = None
            else:
                try:
                    upper_bound = float(upper_bound_raw)
                except (TypeError, ValueError):
                    continue
            normalized.append((upper_bound, label))
        return tuple(normalized)

    def _sync_listener_subscription(self) -> None:
        should_listen = bool(self._tracked_by_entity)
        if should_listen and self._unsub is None:
            self._unsub = self._hass.bus.async_listen(
                EVENT_STATE_CHANGED, self._handle_state_changed
            )
        elif not should_listen and self._unsub is not None:
            self._unsub()
            self._unsub = None

    def _populate_baseline_from_current_states(self) -> None:
        next_state: dict[tuple[str, str], str] = {}
        next_baseline: dict[tuple[str, str], tuple[float, datetime]] = {}
        for tracked in self._tracked_by_entity.values():
            state = self._hass.states.get(tracked.entity_id)
            if state is None:
                continue
            value = self._parse_numeric_state(str(state.state or "").strip())
            bucket = self._bucket_for_value(
                raw_state=str(state.state or "").strip(),
                buckets=tracked.buckets,
            )
            if bucket is not None:
                next_state[(tracked.room_id, tracked.signal_name)] = bucket
            if tracked.burst_threshold is not None and value is not None:
                next_baseline[(tracked.room_id, tracked.signal_name)] = (
                    value,
                    self._coerce_event_ts(getattr(state, "last_changed", None)),
                )
        self._bucket_state = next_state
        self._burst_baseline = next_baseline

    def _periodic_sync(self, snapshot) -> None:
        for tracked in self._tracked_by_entity.values():
            state = self._hass.states.get(tracked.entity_id)
            if state is None:
                continue
            self._maybe_emit_for_state_change(
                tracked=tracked,
                raw_state=str(state.state or "").strip(),
                ts=str(getattr(state, "last_changed", "") or ""),
                source="periodic_sync",
                snapshot=snapshot,
            )
            self._maybe_emit_burst(
                tracked=tracked,
                raw_state=str(state.state or "").strip(),
                ts=str(getattr(snapshot, "ts", "") or ""),
                snapshot=snapshot,
            )

    def _maybe_emit_for_state_change(
        self,
        *,
        tracked: _TrackedSignal,
        raw_state: str,
        ts: str,
        source: str | None,
        snapshot: Any,
    ) -> None:
        bucket = self._bucket_for_value(raw_state=raw_state, buckets=tracked.buckets)
        if bucket is None:
            return
        key = (tracked.room_id, tracked.signal_name)
        previous_bucket = self._bucket_state.get(key)
        if previous_bucket == bucket:
            return
        self._bucket_state[key] = bucket
        if previous_bucket is None:
            return
        direction = self._direction(
            from_bucket=previous_bucket,
            to_bucket=bucket,
            buckets=tracked.buckets,
        )
        value = self._parse_numeric_state(raw_state)
        event = HeimaEvent(
            ts=ts,
            event_type="room_signal_threshold",
            context=self._context_builder.build(snapshot),
            source=source,
            domain=tracked.entity_id.split(".", 1)[0],
            subject_type="signal",
            subject_id=tracked.signal_name,
            room_id=tracked.room_id,
            data={
                "signal_name": tracked.signal_name,
                "entity_id": tracked.entity_id,
                "from_bucket": previous_bucket,
                "to_bucket": bucket,
                "direction": direction,
                "value": value,
                "device_class": tracked.device_class,
            },
        )
        self._hass.async_create_task(self._store.async_append(event))

    def _maybe_emit_burst(
        self,
        *,
        tracked: _TrackedSignal,
        raw_state: str,
        ts: str,
        snapshot: Any,
    ) -> None:
        if tracked.burst_threshold is None:
            return
        value = self._parse_numeric_state(raw_state)
        if value is None:
            return
        key = (tracked.room_id, tracked.signal_name)
        event_dt = self._coerce_event_ts(ts)
        baseline = self._burst_baseline.get(key)
        if baseline is None:
            self._burst_baseline[key] = (value, event_dt)
            return
        baseline_value, _baseline_ts = baseline
        delta = value - baseline_value
        if not self._burst_condition_met(
            delta=delta,
            threshold=tracked.burst_threshold,
            direction=tracked.burst_direction,
        ):
            return
        self._burst_baseline[key] = (value, event_dt)
        self._last_burst_ts[key] = event_dt
        event = HeimaEvent(
            ts=ts or event_dt.isoformat(),
            event_type="room_signal_burst",
            context=self._context_builder.build(snapshot),
            source="periodic_sync",
            domain=tracked.entity_id.split(".", 1)[0],
            subject_type="signal",
            subject_id=tracked.signal_name,
            room_id=tracked.room_id,
            data={
                "signal_name": tracked.signal_name,
                "entity_id": tracked.entity_id,
                "delta": delta,
                "direction": "up" if delta >= 0 else "down",
                "from_value": baseline_value,
                "to_value": value,
                "burst_threshold": tracked.burst_threshold,
                "burst_window_s": tracked.burst_window_s,
                "device_class": tracked.device_class,
            },
        )
        self._hass.async_create_task(self._store.async_append(event))

    @staticmethod
    def _parse_numeric_state(raw_state: str) -> float | None:
        try:
            return float(raw_state)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_event_ts(value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return datetime.now(UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _bucket_for_value(
        self,
        *,
        raw_state: str,
        buckets: tuple[tuple[float | None, str], ...],
    ) -> str | None:
        raw_norm = raw_state.strip().lower()
        if raw_norm in _IGNORED_STATES:
            return None
        numeric = self._parse_numeric_state(raw_state)
        if numeric is None:
            return None
        for upper_bound, label in buckets:
            if upper_bound is None or numeric < upper_bound:
                return label
        return None

    @staticmethod
    def _direction(
        *,
        from_bucket: str,
        to_bucket: str,
        buckets: tuple[tuple[float | None, str], ...],
    ) -> str:
        labels = [label for _, label in buckets]
        try:
            return "up" if labels.index(to_bucket) > labels.index(from_bucket) else "down"
        except ValueError:
            return "down"

    @staticmethod
    def _coerce_burst_threshold(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return None
        return numeric if numeric > 0 else None

    @staticmethod
    def _normalize_burst_direction(value: Any) -> str:
        normalized = str(value or "up").strip().lower()
        if normalized in {"up", "down", "both"}:
            return normalized
        return "up"

    @staticmethod
    def _burst_condition_met(*, delta: float, threshold: float, direction: str) -> bool:
        if direction == "down":
            return delta <= -threshold
        if direction == "both":
            return abs(delta) >= threshold
        return delta >= threshold
