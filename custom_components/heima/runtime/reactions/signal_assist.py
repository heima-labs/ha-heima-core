"""Generic room-scoped signal assist reaction."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.core import HomeAssistant

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction
from .composite import (
    RuntimeCompositeMatcher,
    RuntimeCompositePatternSpec,
    RuntimeCompositeSignalSpec,
    parse_snapshot_ts,
)


class RoomSignalAssistReaction(HeimaReaction):
    """Trigger configured steps when room-scoped signal burst pattern is observed."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        room_id: str,
        trigger_signal_entities: list[str] | None = None,
        steps: list[ApplyStep],
        primary_signal_entities: list[str] | None = None,
        primary_rise_threshold: float | None = None,
        primary_signal_name: str = "primary",
        humidity_rise_threshold: float = 8.0,
        corroboration_signal_entities: list[str] | None = None,
        corroboration_rise_threshold: float | None = None,
        corroboration_signal_name: str = "corroboration",
        temperature_signal_entities: list[str] | None = None,
        temperature_rise_threshold: float = 0.8,
        correlation_window_s: int = 600,
        followup_window_s: int = 900,
        reaction_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._room_id = room_id
        resolved_primary_entities = [
            e for e in (primary_signal_entities or trigger_signal_entities or []) if e
        ]
        resolved_primary_threshold = (
            primary_rise_threshold if primary_rise_threshold is not None else humidity_rise_threshold
        )
        resolved_corroboration_entities = [
            e for e in (corroboration_signal_entities or temperature_signal_entities or []) if e
        ]
        resolved_corroboration_threshold = (
            corroboration_rise_threshold
            if corroboration_rise_threshold is not None
            else temperature_rise_threshold
        )
        self._primary_entities = resolved_primary_entities
        self._corroboration_entities = resolved_corroboration_entities
        self._steps = list(steps)
        self._primary_rise_threshold = float(resolved_primary_threshold)
        self._corroboration_rise_threshold = float(resolved_corroboration_threshold)
        self._primary_signal_name = primary_signal_name or "primary"
        self._corroboration_signal_name = corroboration_signal_name or "corroboration"
        self._correlation_window_s = correlation_window_s
        self._followup_window_s = followup_window_s
        self._reaction_id = reaction_id or self.__class__.__name__
        self._legacy_trigger_entities = [e for e in (trigger_signal_entities or []) if e]
        self._matcher = RuntimeCompositeMatcher(hass)
        self._pattern = RuntimeCompositePatternSpec(
            primary=RuntimeCompositeSignalSpec(
                name=self._primary_signal_name,
                entity_ids=tuple(self._primary_entities),
                threshold=self._primary_rise_threshold,
            ),
            corroborations=(
                RuntimeCompositeSignalSpec(
                    name=self._corroboration_signal_name,
                    entity_ids=tuple(self._corroboration_entities),
                    threshold=self._corroboration_rise_threshold,
                    required=bool(self._corroboration_entities),
                ),
            )
            if self._corroboration_entities
            else (),
            correlation_window_s=self._correlation_window_s,
        )
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
            return []

        now = parse_snapshot_ts(snapshot.ts)
        if now is None:
            return []

        result = self._matcher.observe(
            now=now,
            pending_since=self._pending_episode_ts,
            spec=self._pattern,
        )
        self._pending_episode_ts = result.pending_since
        should_fire = result.ready

        if should_fire and self._is_cooled_down():
            self._pending_episode_ts = None
            self._fire_count += 1
            self._last_fired_ts = time.monotonic()
            return list(self._steps)
        if should_fire:
            self._suppressed_count += 1
        return []

    def reset_learning_state(self) -> None:
        self._matcher.reset()
        self._pending_episode_ts = None
        self._last_fired_ts = None
        self._fire_count = 0
        self._suppressed_count = 0

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "trigger_signal_entities": list(self._legacy_trigger_entities),
            "primary_signal_name": self._primary_signal_name,
            "primary_entities": list(self._primary_entities),
            "primary_rise_threshold": self._primary_rise_threshold,
            "corroboration_signal_name": self._corroboration_signal_name,
            "corroboration_entities": list(self._corroboration_entities),
            "corroboration_rise_threshold": self._corroboration_rise_threshold,
            "humidity_entities": list(self._primary_entities),
            "temperature_entities": list(self._corroboration_entities),
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "pending_episode": self._pending_episode_ts.isoformat() if self._pending_episode_ts else None,
        }

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= self._followup_window_s
