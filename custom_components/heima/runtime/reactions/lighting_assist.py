"""Room-scoped lighting replay reaction driven by composite trigger semantics."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Literal

from homeassistant.core import HomeAssistant

from ...room_sources import room_signal_bucket_labels
from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction
from .composite import (
    RuntimeCompositeMatcher,
    RuntimeCompositePatternSpec,
    RuntimeCompositeSignalSpec,
    parse_snapshot_ts,
)

BucketMatchMode = Literal["eq", "lte", "gte"]


def _normalize_bucket_match_mode(value: str | BucketMatchMode | None) -> BucketMatchMode:
    normalized = str(value or "eq").strip().lower()
    if normalized in {"eq", "lte", "gte"}:
        return normalized  # type: ignore[return-value]
    return "eq"


def _bucket_match_mode_label(value: str | BucketMatchMode | None, *, language: str) -> str:
    normalized = _normalize_bucket_match_mode(value)
    is_it = language.startswith("it")
    if normalized == "lte":
        return "bucket o inferiori" if is_it else "bucket or lower"
    if normalized == "gte":
        return "bucket o superiori" if is_it else "bucket or higher"
    return "bucket esatto" if is_it else "exact bucket"


class RoomLightingAssistReaction(HeimaReaction):
    """Replay learned lighting entity steps when a room-scoped darkness pattern reoccurs."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        bucket_getter: Any | None = None,
        room_id: str,
        entity_steps: list[dict[str, Any]],
        primary_signal_entities: list[str],
        primary_bucket: str | None = None,
        primary_bucket_match_mode: BucketMatchMode = "eq",
        primary_bucket_labels: list[str] | None = None,
        primary_signal_name: str = "room_lux",
        corroboration_signal_entities: list[str] | None = None,
        corroboration_threshold: float | None = None,
        corroboration_signal_name: str = "corroboration",
        corroboration_threshold_mode: str = "below",
        correlation_window_s: int = 600,
        followup_window_s: int = 900,
        reaction_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._bucket_getter = bucket_getter or (lambda _room_id, _signal_name: None)
        self._room_id = room_id
        self._entity_steps = list(entity_steps)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._followup_window_s = followup_window_s
        self._matcher = RuntimeCompositeMatcher(hass)
        self._primary_bucket = str(primary_bucket or "").strip() or None
        self._primary_bucket_match_mode = _normalize_bucket_match_mode(primary_bucket_match_mode)
        self._primary_bucket_labels = tuple(
            str(item).strip() for item in (primary_bucket_labels or []) if str(item).strip()
        )
        corroboration_entities = [e for e in (corroboration_signal_entities or []) if e]
        self._pattern = RuntimeCompositePatternSpec(
            primary=RuntimeCompositeSignalSpec(
                name=primary_signal_name,
                entity_ids=tuple(primary_signal_entities),
                threshold=0.0,
                threshold_mode="state_change",
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
        self._steady_condition_active = False

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        snapshot = history[-1]
        if self._room_id not in snapshot.occupied_rooms:
            self._steady_condition_active = False
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
        steady_ready = self._steady_ready()
        corroboration_ready = bool(self._pattern.corroborations) and bool(result.ready) and bool(
            self._bucket_matches(self._current_primary_bucket())
        )
        should_fire = corroboration_ready or steady_ready
        if not should_fire:
            self._steady_condition_active = False
            return []
        if not self._is_cooled_down():
            self._suppressed_count += 1
            return []

        self._pending_episode_ts = None
        self._last_fired_ts = time.monotonic()
        self._fire_count += 1
        self._steady_condition_active = steady_ready
        return self._build_steps()

    def reset_learning_state(self) -> None:
        self._matcher.reset()
        self._pending_episode_ts = None
        self._last_fired_ts = None
        self._fire_count = 0
        self._suppressed_count = 0
        self._steady_condition_active = False

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "entity_steps": len(self._entity_steps),
            "primary_bucket": self._primary_bucket,
            "primary_bucket_match_mode": self._primary_bucket_match_mode,
            "primary_bucket_labels": list(self._primary_bucket_labels),
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "pending_episode": self._pending_episode_ts.isoformat()
            if self._pending_episode_ts
            else None,
            "steady_condition_active": self._steady_condition_active,
        }

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= self._followup_window_s

    def _current_primary_bucket(self) -> str | None:
        return self._bucket_getter(self._room_id, self._pattern.primary.name)

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

    def _steady_ready(self) -> bool:
        current_bucket = self._current_primary_bucket()
        if not self._bucket_matches(current_bucket):
            return False
        if self._steady_condition_active:
            return False
        return self._entity_steps_need_apply()

    def _bucket_matches(self, current_bucket: str | None) -> bool:
        expected_bucket = str(self._primary_bucket or "").strip()
        current = str(current_bucket or "").strip()
        if not expected_bucket or not current:
            return False
        if self._primary_bucket_match_mode == "eq":
            return current == expected_bucket
        order = list(self._primary_bucket_labels)
        if not order:
            return current == expected_bucket
        try:
            current_index = order.index(current)
            expected_index = order.index(expected_bucket)
        except ValueError:
            return current == expected_bucket
        if self._primary_bucket_match_mode == "lte":
            return current_index <= expected_index
        if self._primary_bucket_match_mode == "gte":
            return current_index >= expected_index
        return current == expected_bucket

    def _entity_steps_need_apply(self) -> bool:
        for cfg in self._entity_steps:
            entity_id = str(cfg.get("entity_id") or "").strip()
            desired_action = str(cfg.get("action") or "").strip()
            if not entity_id or desired_action not in {"on", "off"}:
                continue
            state = self._hass.states.get(entity_id)
            current = str(state.state).strip().lower() if state is not None else ""
            if desired_action == "on" and current != "on":
                return True
            if desired_action == "off" and current != "off":
                return True
        return False


def build_room_lighting_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomLightingAssistReaction | None:
    """Build a RoomLightingAssistReaction from persisted config."""
    try:
        room_id = str(cfg["room_id"]).strip()
        primary_signal_entities = [
            str(v).strip() for v in cfg.get("primary_signal_entities", []) if str(v).strip()
        ]
        primary_bucket = str(cfg.get("primary_bucket") or "").strip() or None
        primary_bucket_match_mode = _normalize_bucket_match_mode(
            str(cfg.get("primary_bucket_match_mode") or "eq")
        )
        primary_signal_name = str(cfg.get("primary_signal_name", "room_lux"))
        corroboration_signal_entities = [
            str(v).strip() for v in cfg.get("corroboration_signal_entities", []) if str(v).strip()
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
        rooms = list(dict(getattr(engine, "_entry").options).get("rooms") or [])  # noqa: SLF001
        primary_bucket_labels = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
        if not room_id or not primary_signal_entities or not entity_steps:
            raise ValueError("room_id, primary_signal_entities or entity_steps missing")
        if primary_bucket is None:
            raise ValueError("primary_bucket missing")
    except (KeyError, TypeError, ValueError):
        return None
    return RoomLightingAssistReaction(
        hass=engine._hass,  # noqa: SLF001
        bucket_getter=engine.signal_bucket,
        room_id=room_id,
        entity_steps=entity_steps,
        primary_signal_entities=primary_signal_entities,
        primary_bucket=primary_bucket,
        primary_bucket_match_mode=primary_bucket_match_mode,
        primary_bucket_labels=primary_bucket_labels,
        primary_signal_name=primary_signal_name,
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
    primary_bucket = str(cfg.get("primary_bucket") or "").strip()
    if primary_bucket:
        details.append(
            f"Bucket buio: {primary_bucket}" if is_it else f"Darkness bucket: {primary_bucket}"
        )
    primary_bucket_match_mode = str(cfg.get("primary_bucket_match_mode") or "").strip()
    if primary_bucket_match_mode:
        match_label = _bucket_match_mode_label(primary_bucket_match_mode, language=language)
        details.append(
            f"Match bucket: {match_label}" if is_it else f"Bucket match: {match_label}"
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
    primary_bucket = str(cfg.get("primary_bucket") or "").strip()
    if primary_bucket:
        details.append(
            f"Bucket proposto: {primary_bucket}" if is_it else f"Proposed bucket: {primary_bucket}"
        )
    primary_bucket_match_mode = str(cfg.get("primary_bucket_match_mode") or "").strip()
    if primary_bucket_match_mode:
        match_label = _bucket_match_mode_label(primary_bucket_match_mode, language=language)
        details.append(
            f"Match proposto: {match_label}"
            if is_it
            else f"Proposed bucket match: {match_label}"
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

    current_bucket = str(target_cfg.get("primary_bucket") or "").strip()
    proposed_bucket = str(cfg.get("primary_bucket") or "").strip()
    if current_bucket or proposed_bucket:
        if current_bucket != proposed_bucket:
            details.append(
                f"Bucket: {current_bucket} -> {proposed_bucket}"
                if is_it
                else f"Bucket: {current_bucket} -> {proposed_bucket}"
            )
    current_match_mode = str(target_cfg.get("primary_bucket_match_mode") or "").strip()
    proposed_match_mode = str(cfg.get("primary_bucket_match_mode") or "").strip()
    if current_match_mode or proposed_match_mode:
        current_match_label = _bucket_match_mode_label(current_match_mode, language=language)
        proposed_match_label = _bucket_match_mode_label(proposed_match_mode, language=language)
        if current_match_mode != proposed_match_mode:
            details.append(
                f"Match: {current_match_label} -> {proposed_match_label}"
                if is_it
                else f"Match: {current_match_label} -> {proposed_match_label}"
            )

    current_primary_entities = target_cfg.get("primary_signal_entities")
    proposed_primary_entities = cfg.get("primary_signal_entities")
    if isinstance(current_primary_entities, list) and isinstance(proposed_primary_entities, list):
        if len(current_primary_entities) != len(proposed_primary_entities):
            details.append(
                f"Entità primarie: {len(current_primary_entities)} -> {len(proposed_primary_entities)}"
                if is_it
                else (
                    f"Primary entities: {len(current_primary_entities)} ->"
                    f" {len(proposed_primary_entities)}"
                )
            )

    current_corroboration_threshold = target_cfg.get("corroboration_threshold")
    proposed_corroboration_threshold = cfg.get("corroboration_threshold")
    if current_corroboration_threshold not in (
        None,
        "",
    ) and proposed_corroboration_threshold not in (
        None,
        "",
    ):
        if str(current_corroboration_threshold) != str(proposed_corroboration_threshold):
            details.append(
                f"Soglia corroborante: {current_corroboration_threshold} -> {proposed_corroboration_threshold}"
                if is_it
                else (
                    "Corroboration threshold: "
                    f"{current_corroboration_threshold} -> {proposed_corroboration_threshold}"
                )
            )

    current_corroboration_mode = str(
        target_cfg.get("corroboration_threshold_mode") or "below"
    ).strip()
    proposed_corroboration_mode = str(cfg.get("corroboration_threshold_mode") or "below").strip()
    if current_corroboration_mode != proposed_corroboration_mode:
        details.append(
            f"Modo corroborante: {current_corroboration_mode} -> {proposed_corroboration_mode}"
            if is_it
            else f"Corroboration mode: {current_corroboration_mode} -> {proposed_corroboration_mode}"
        )

    current_corroboration_entities = target_cfg.get("corroboration_signal_entities")
    proposed_corroboration_entities = cfg.get("corroboration_signal_entities")
    if isinstance(current_corroboration_entities, list) and isinstance(
        proposed_corroboration_entities, list
    ):
        if len(current_corroboration_entities) != len(proposed_corroboration_entities):
            details.append(
                (
                    "Entità corroboranti: "
                    f"{len(current_corroboration_entities)} -> {len(proposed_corroboration_entities)}"
                )
                if is_it
                else (
                    "Corroboration entities: "
                    f"{len(current_corroboration_entities)} -> {len(proposed_corroboration_entities)}"
                )
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
    primary_signal_name = str(cfg.get("primary_signal_name") or "").strip()
    if language.startswith("it"):
        if primary_signal_name:
            return f"Luci {room_id} · {primary_signal_name}"
        return f"Luci {room_id}"
    if primary_signal_name:
        return f"Lighting {room_id} · {primary_signal_name}"
    return f"Lighting {room_id}"


def present_room_lighting_assist_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_followup: bool,
) -> str | None:
    if str(getattr(proposal, "origin", "") or "") == "admin_authored":
        return None
    title = present_room_lighting_assist_proposal_label(flow, proposal, cfg, language)
    if not title:
        return None
    if language.startswith("it"):
        return f"Affinamento luce: {title}" if is_followup else f"Nuova luce assistita: {title}"
    return f"Lighting tuning: {title}" if is_followup else f"New lighting assist: {title}"
