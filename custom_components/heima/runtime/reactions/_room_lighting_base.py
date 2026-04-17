"""Shared runtime primitives for room-scoped lighting assist reactions."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Literal

from homeassistant.core import HomeAssistant

from ..contracts import ApplyStep
from .base import HeimaReaction

BucketMatchMode = Literal["eq", "lte", "gte"]


def normalize_bucket_match_mode(value: str | BucketMatchMode | None) -> BucketMatchMode:
    """Normalize persisted bucket match mode values."""
    normalized = str(value or "eq").strip().lower()
    if normalized in {"eq", "lte", "gte"}:
        return normalized  # type: ignore[return-value]
    return "eq"


def bucket_match_mode_label(value: str | BucketMatchMode | None, *, language: str) -> str:
    """Return a human label for a bucket match mode."""
    normalized = normalize_bucket_match_mode(value)
    is_it = language.startswith("it")
    if normalized == "lte":
        return "bucket o inferiori" if is_it else "bucket or lower"
    if normalized == "gte":
        return "bucket o superiori" if is_it else "bucket or higher"
    return "bucket esatto" if is_it else "exact bucket"


class _BaseRoomLightingAssist(HeimaReaction):
    """Common runtime behavior for room-scoped lighting assist reactions."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        bucket_getter: Any | None,
        room_id: str,
        reaction_id: str | None,
        followup_window_s: int,
        primary_signal_name: str,
        primary_bucket: str | None,
        primary_bucket_match_mode: str | BucketMatchMode,
        primary_bucket_labels: list[str] | None,
    ) -> None:
        self._hass = hass
        self._bucket_getter = bucket_getter or (lambda _room_id, _signal_name: None)
        self._room_id = room_id
        self._reaction_id = reaction_id or self.__class__.__name__
        self._followup_window_s = int(followup_window_s)
        self._primary_signal_name = str(primary_signal_name or "").strip()
        self._primary_bucket = str(primary_bucket or "").strip() or None
        self._primary_bucket_match_mode = normalize_bucket_match_mode(primary_bucket_match_mode)
        self._primary_bucket_labels = tuple(
            str(item).strip() for item in (primary_bucket_labels or []) if str(item).strip()
        )
        self._last_fired_ts: float | None = None
        self._last_fired_iso: str | None = None
        self._fire_count = 0
        self._suppressed_count = 0

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def _current_primary_bucket(self) -> str | None:
        return self._current_bucket_for(self._primary_signal_name)

    def _current_bucket_for(self, signal_name: str) -> str | None:
        value = self._bucket_getter(self._room_id, signal_name)
        text = str(value or "").strip()
        return text or None

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

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= self._followup_window_s

    def _mark_suppressed(self) -> None:
        self._suppressed_count += 1

    def _mark_fired(self) -> None:
        self._last_fired_ts = time.monotonic()
        self._last_fired_iso = datetime.now().isoformat()
        self._fire_count += 1

    def _reset_runtime_counters(self) -> None:
        self._last_fired_ts = None
        self._last_fired_iso = None
        self._fire_count = 0
        self._suppressed_count = 0

    def _entity_steps_need_apply(self, entity_steps: list[dict[str, Any]]) -> bool:
        for cfg in entity_steps:
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

    def _build_steps(
        self, entity_steps: list[dict[str, Any]], *, reason_prefix: str
    ) -> list[ApplyStep]:
        steps: list[ApplyStep] = []
        for cfg in entity_steps:
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
                        reason=f"{reason_prefix}:{self._reaction_id}",
                    )
                )
            else:
                steps.append(
                    ApplyStep(
                        domain="lighting",
                        target=self._room_id,
                        action="light.turn_off",
                        params={"entity_id": entity_id},
                        reason=f"{reason_prefix}:{self._reaction_id}",
                    )
                )
        return steps

    def _base_diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "primary_bucket": self._primary_bucket,
            "primary_bucket_match_mode": self._primary_bucket_match_mode,
            "primary_bucket_labels": list(self._primary_bucket_labels),
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "last_fired_iso": self._last_fired_iso,
        }
