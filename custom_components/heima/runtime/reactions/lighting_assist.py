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


def build_room_lighting_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomLightingAssistReaction | None:
    """Build a RoomLightingAssistReaction from persisted config."""
    try:
        room_id = str(cfg["room_id"]).strip()
        primary_signal_entities = [
            str(v).strip()
            for v in cfg.get("primary_signal_entities", [])
            if str(v).strip()
        ]
        primary_threshold = float(cfg["primary_threshold"])
        primary_signal_name = str(cfg.get("primary_signal_name", "room_lux"))
        primary_threshold_mode = str(cfg.get("primary_threshold_mode", "below"))
        corroboration_signal_entities = [
            str(v).strip()
            for v in cfg.get("corroboration_signal_entities", [])
            if str(v).strip()
        ]
        corroboration_threshold = (
            float(cfg["corroboration_threshold"])
            if cfg.get("corroboration_threshold") is not None
            else None
        )
        corroboration_signal_name = str(cfg.get("corroboration_signal_name", "corroboration"))
        corroboration_threshold_mode = str(cfg.get("corroboration_threshold_mode", "below"))
        correlation_window_s = int(cfg.get("correlation_window_s", 600))
        followup_window_s = int(cfg.get("followup_window_s", 900))
        entity_steps = list(cfg.get("entity_steps", []))
        if not room_id or not primary_signal_entities or not entity_steps:
            raise ValueError("room_id, primary_signal_entities or entity_steps missing")
    except (KeyError, TypeError, ValueError):
        return None
    return RoomLightingAssistReaction(
        hass=engine._hass,  # noqa: SLF001
        room_id=room_id,
        entity_steps=entity_steps,
        primary_signal_entities=primary_signal_entities,
        primary_threshold=primary_threshold,
        primary_signal_name=primary_signal_name,
        primary_threshold_mode=primary_threshold_mode,
        corroboration_signal_entities=corroboration_signal_entities,
        corroboration_threshold=corroboration_threshold,
        corroboration_signal_name=corroboration_signal_name,
        corroboration_threshold_mode=corroboration_threshold_mode,
        correlation_window_s=correlation_window_s,
        followup_window_s=followup_window_s,
        reaction_id=proposal_id,
    )


def present_room_lighting_assist_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    """Return a human label for persisted room lighting assist reactions."""
    try:
        room_id = str(cfg.get("room_id", "")).strip() or reaction_id
        primary_entities = list(cfg.get("primary_signal_entities", []))
        entity_steps = list(cfg.get("entity_steps", []))
        parts = [f"Luce {room_id}"]
        if primary_entities:
            parts.append(f"lux:{len(primary_entities)}")
        if entity_steps:
            parts.append(f"{len(entity_steps)} entità")
        return " — ".join(parts)
    except (TypeError, ValueError):
        return labels_map.get(reaction_id)


def present_admin_authored_room_lighting_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return room-lighting-specific admin-authored review details."""
    is_it = language.startswith("it")
    details: list[str] = []

    primary_signal_name = str(cfg.get("primary_signal_name") or "").strip()
    if primary_signal_name:
        details.append(
            f"Segnale primario: {primary_signal_name}"
            if is_it
            else f"Primary signal: {primary_signal_name}"
        )
    primary_entities = cfg.get("primary_signal_entities")
    if isinstance(primary_entities, list) and primary_entities:
        details.append(
            f"Entità primarie: {len(primary_entities)}"
            if is_it
            else f"Primary entities: {len(primary_entities)}"
        )
    primary_threshold = cfg.get("primary_threshold")
    if primary_threshold not in (None, ""):
        details.append(
            f"Soglia buio: {primary_threshold}"
            if is_it
            else f"Darkness threshold: {primary_threshold}"
        )
    entity_steps = cfg.get("entity_steps")
    if isinstance(entity_steps, list) and entity_steps:
        details.append(
            f"Luci configurate: {len(entity_steps)}"
            if is_it
            else f"Configured lights: {len(entity_steps)}"
        )
    return details


def present_learned_room_lighting_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return learned/tuning review details for room lighting assist proposals."""
    is_it = language.startswith("it")
    details: list[str] = []

    primary_signal_name = str(cfg.get("primary_signal_name") or "").strip()
    if primary_signal_name:
        details.append(
            f"Segnale primario: {primary_signal_name}"
            if is_it
            else f"Primary signal: {primary_signal_name}"
        )
    primary_threshold = cfg.get("primary_threshold")
    if primary_threshold not in (None, ""):
        details.append(
            f"Soglia proposta: {primary_threshold}"
            if is_it
            else f"Proposed threshold: {primary_threshold}"
        )
    entity_steps = cfg.get("entity_steps")
    if isinstance(entity_steps, list) and entity_steps:
        details.append(
            f"Luci proposte: {len(entity_steps)}"
            if is_it
            else f"Proposed lights: {len(entity_steps)}"
        )
    return details


def present_tuning_room_lighting_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return room-lighting-specific tuning diff lines."""
    is_it = language.startswith("it")
    details: list[str] = []

    current_threshold = target_cfg.get("primary_threshold")
    proposed_threshold = cfg.get("primary_threshold")
    if current_threshold not in (None, "") and proposed_threshold not in (None, ""):
        if str(current_threshold) != str(proposed_threshold):
            details.append(
                f"Soglia: {current_threshold} -> {proposed_threshold}"
                if is_it
                else f"Threshold: {current_threshold} -> {proposed_threshold}"
            )

    current_steps = target_cfg.get("entity_steps")
    proposed_steps = cfg.get("entity_steps")
    if isinstance(current_steps, list) and isinstance(proposed_steps, list):
        if len(current_steps) != len(proposed_steps):
            details.append(
                f"Luci: {len(current_steps)} -> {len(proposed_steps)}"
                if is_it
                else f"Lights: {len(current_steps)} -> {len(proposed_steps)}"
            )

    return details


def present_room_lighting_assist_proposal_label(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    if not room_id:
        return None
    if language.startswith("it"):
        return f"Luce {room_id}"
    return f"Lighting {room_id}"
