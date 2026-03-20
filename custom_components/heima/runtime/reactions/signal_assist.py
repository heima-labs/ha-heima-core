"""Generic room-scoped signal assist reaction."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction


class RoomSignalAssistReaction(HeimaReaction):
    """Trigger configured steps when room-scoped signal burst pattern is observed."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        room_id: str,
        trigger_signal_entities: list[str],
        steps: list[ApplyStep],
        humidity_rise_threshold: float = 8.0,
        temperature_signal_entities: list[str] | None = None,
        temperature_rise_threshold: float = 0.8,
        correlation_window_s: int = 600,
        followup_window_s: int = 900,
        reaction_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._room_id = room_id
        self._humidity_entities = [e for e in trigger_signal_entities if e]
        self._temperature_entities = [e for e in (temperature_signal_entities or []) if e]
        self._steps = list(steps)
        self._humidity_rise_threshold = humidity_rise_threshold
        self._temperature_rise_threshold = temperature_rise_threshold
        self._correlation_window_s = correlation_window_s
        self._followup_window_s = followup_window_s
        self._reaction_id = reaction_id or self.__class__.__name__
        self._last_values: dict[str, tuple[float, datetime]] = {}
        self._pending_episode_ts: datetime | None = None
        self._last_fired_ts: float | None = None
        self._fire_count = 0
        self._suppressed_count = 0

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        snapshot = history[-1]
        if self._room_id not in snapshot.occupied_rooms:
            self._observe_signals(snapshot.ts)
            return []

        now = _parse_ts(snapshot.ts)
        if now is None:
            self._observe_signals(snapshot.ts)
            return []

        humidity_burst = self._observe_humidity_burst(now)
        temperature_burst = self._observe_temperature_burst(now)

        should_fire = False
        if humidity_burst:
            if self._temperature_entities:
                self._pending_episode_ts = now
            else:
                should_fire = True
        elif self._pending_episode_ts is not None:
            age = (now - self._pending_episode_ts).total_seconds()
            if age > self._correlation_window_s:
                self._pending_episode_ts = None
            elif temperature_burst:
                should_fire = True

        if should_fire and self._is_cooled_down():
            self._pending_episode_ts = None
            self._fire_count += 1
            self._last_fired_ts = time.monotonic()
            return list(self._steps)
        if should_fire:
            self._suppressed_count += 1
        return []

    def reset_learning_state(self) -> None:
        self._last_values.clear()
        self._pending_episode_ts = None
        self._last_fired_ts = None
        self._fire_count = 0
        self._suppressed_count = 0

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "humidity_entities": list(self._humidity_entities),
            "temperature_entities": list(self._temperature_entities),
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "pending_episode": self._pending_episode_ts.isoformat() if self._pending_episode_ts else None,
        }

    def _observe_humidity_burst(self, now: datetime) -> bool:
        return self._observe_numeric_burst(
            entity_ids=self._humidity_entities,
            now=now,
            threshold=self._humidity_rise_threshold,
        )

    def _observe_temperature_burst(self, now: datetime) -> bool:
        return self._observe_numeric_burst(
            entity_ids=self._temperature_entities,
            now=now,
            threshold=self._temperature_rise_threshold,
        )

    def _observe_numeric_burst(self, *, entity_ids: list[str], now: datetime, threshold: float) -> bool:
        burst = False
        for entity_id in entity_ids:
            current = self._current_numeric_state(entity_id)
            if current is None:
                continue
            prev = self._last_values.get(entity_id)
            self._last_values[entity_id] = (current, now)
            if prev is None:
                continue
            previous_value, previous_ts = prev
            if (now - previous_ts).total_seconds() > self._correlation_window_s:
                continue
            if current - previous_value >= threshold:
                burst = True
        return burst

    def _current_numeric_state(self, entity_id: str) -> float | None:
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= self._followup_window_s


def _parse_ts(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except (TypeError, ValueError):
        return None
