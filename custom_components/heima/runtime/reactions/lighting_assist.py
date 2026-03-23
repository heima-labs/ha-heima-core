"""Room-scoped lighting replay reaction driven by composite trigger semantics."""

from __future__ import annotations

import time
from datetime import datetime
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


class RoomLightingAssistReaction(HeimaReaction):
    """Replay learned lighting entity steps when a room-scoped darkness pattern reoccurs."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        room_id: str,
        entity_steps: list[dict[str, Any]],
        primary_signal_entities: list[str],
        primary_threshold: float,
        primary_signal_name: str = "room_lux",
        primary_threshold_mode: str = "below",
        corroboration_signal_entities: list[str] | None = None,
        corroboration_threshold: float | None = None,
        corroboration_signal_name: str = "corroboration",
        corroboration_threshold_mode: str = "below",
        correlation_window_s: int = 600,
        followup_window_s: int = 900,
        reaction_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._room_id = room_id
        self._entity_steps = list(entity_steps)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._followup_window_s = followup_window_s
        self._matcher = RuntimeCompositeMatcher(hass)
        corroboration_entities = [e for e in (corroboration_signal_entities or []) if e]
        self._pattern = RuntimeCompositePatternSpec(
            primary=RuntimeCompositeSignalSpec(
                name=primary_signal_name,
                entity_ids=tuple(primary_signal_entities),
                threshold=float(primary_threshold),
                threshold_mode=primary_threshold_mode,  # type: ignore[arg-type]
            ),
            corroborations=(
                RuntimeCompositeSignalSpec(
                    name=corroboration_signal_name,
                    entity_ids=tuple(corroboration_entities),
                    threshold=float(corroboration_threshold or 0.0),
                    threshold_mode=corroboration_threshold_mode,  # type: ignore[arg-type]
                    required=bool(corroboration_entities),
                ),
            )
            if corroboration_entities
            else (),
            correlation_window_s=correlation_window_s,
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
        if not result.ready:
            return []
        if not self._is_cooled_down():
            self._suppressed_count += 1
            return []

        self._pending_episode_ts = None
        self._last_fired_ts = time.monotonic()
        self._fire_count += 1
        return self._build_steps()

    def reset_learning_state(self) -> None:
        self._matcher.reset()
        self._pending_episode_ts = None
        self._last_fired_ts = None
        self._fire_count = 0
        self._suppressed_count = 0

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "entity_steps": len(self._entity_steps),
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "pending_episode": self._pending_episode_ts.isoformat() if self._pending_episode_ts else None,
        }

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= self._followup_window_s

    def _build_steps(self) -> list[ApplyStep]:
        steps: list[ApplyStep] = []
        for cfg in self._entity_steps:
            entity_id = str(cfg.get("entity_id") or "").strip()
            action = str(cfg.get("action") or "").strip()
            if not entity_id or action not in {"on", "off"}:
                continue
            if action == "on":
                params: dict[str, Any] = {"entity_id": entity_id}
                if cfg.get("brightness") is not None:
                    params["brightness"] = cfg["brightness"]
                if cfg.get("rgb_color") is not None:
                    params["rgb_color"] = cfg["rgb_color"]
                elif cfg.get("color_temp_kelvin") is not None:
                    params["color_temp_kelvin"] = cfg["color_temp_kelvin"]
                steps.append(
                    ApplyStep(
                        domain="lighting",
                        target=self._room_id,
                        action="light.turn_on",
                        params=params,
                        reason=f"room_lighting_assist:{self._reaction_id}",
                    )
                )
            else:
                steps.append(
                    ApplyStep(
                        domain="lighting",
                        target=self._room_id,
                        action="light.turn_off",
                        params={"entity_id": entity_id},
                        reason=f"room_lighting_assist:{self._reaction_id}",
                    )
                )
        return steps
