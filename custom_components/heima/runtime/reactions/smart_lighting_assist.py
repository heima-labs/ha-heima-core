"""Unified room smart lighting reaction for Phase AB."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import replace as dataclass_replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from ...room_sources import room_signal_bucket_labels
from ..contracts import ApplyStep
from ..scheduler import ScheduledRuntimeJob
from ..snapshot import DecisionSnapshot
from ._lighting_review import (
    render_entity_steps_discovery_details,
    render_entity_steps_tuning_details,
)
from ._room_lighting_base import _BaseRoomLightingAssist
from .composite import parse_snapshot_ts

ROOM_TYPE_DEFAULTS: dict[str, tuple[int, int]] = {
    "bagno": (2, 30),
    "cucina": (4, 45),
    "corridoio": (1, 15),
    "ingresso": (1, 15),
    "studio": (6, 60),
    "soggiorno": (8, 90),
    "sala_da_pranzo": (6, 60),
    "tinello": (4, 45),
    "camera_da_letto": (5, 60),
    "cameretta_bambini": (5, 90),
    "lavanderia": (3, 20),
    "ripostiglio": (1, 15),
    "garage": (3, 30),
    "generic": (5, 45),
}

NIGHT_SUPPRESS_ROOM_TYPES = {
    "camera_da_letto",
    "cameretta_bambini",
    "studio",
    "soggiorno",
    "sala_da_pranzo",
    "tinello",
    "garage",
    "ripostiglio",
}

_VISIT_RING_SIZE = 50
_LEARNED_MIN_VISITS = 20
_DEFAULT_MANUAL_OVERRIDE_WINDOW_MIN = 30
_DEFAULT_DIM_BRIGHTNESS_PCT = 15
_DEFAULT_DIM_RATIO = 0.3
_ISSUED_CONTEXT_TTL_S = 30.0


class RoomSmartLightingAssistReaction(_BaseRoomLightingAssist):
    """Presence, lux, profile and adaptive timeout based room lighting."""

    def __init__(
        self,
        *,
        hass: Any,
        bucket_getter: Any | None = None,
        room_id: str,
        indoor_lux_signal: str = "room_lux",
        outdoor_lux_signal: str | None = None,
        lux_on_buckets: list[str],
        room_type: str = "generic",
        suppress_on_states: list[str] | None = None,
        night_mode_states: list[str] | None = None,
        timeout_mode: str = "learned",
        base_timeout_min: int | None = None,
        fast_exit_timeout_s: int | None = None,
        dim_brightness_pct: int = _DEFAULT_DIM_BRIGHTNESS_PCT,
        dim_ratio: float = _DEFAULT_DIM_RATIO,
        profiles: list[dict[str, Any]] | dict[str, dict[str, Any]] | None = None,
        entity_steps: list[dict[str, Any]] | None = None,
        outdoor_lux_scale: dict[str, float] | None = None,
        manual_override_window_min: int = _DEFAULT_MANUAL_OVERRIDE_WINDOW_MIN,
        reaction_id: str | None = None,
    ) -> None:
        room_type = room_type if room_type in ROOM_TYPE_DEFAULTS else "generic"
        default_base_min, default_fast_exit_s = ROOM_TYPE_DEFAULTS[room_type]
        super().__init__(
            hass=hass,
            bucket_getter=bucket_getter,
            room_id=room_id,
            reaction_id=reaction_id,
            followup_window_s=0,
            primary_signal_name=indoor_lux_signal,
            primary_bucket=None,
            primary_bucket_match_mode="eq",
            primary_bucket_labels=None,
        )
        self._indoor_lux_signal = str(indoor_lux_signal or "room_lux").strip()
        self._outdoor_lux_signal = str(outdoor_lux_signal or "").strip() or None
        self._lux_on_buckets = {
            str(bucket).strip() for bucket in list(lux_on_buckets or []) if str(bucket).strip()
        }
        self._room_type = room_type
        self._suppress_on_states = {
            str(state).strip() for state in list(suppress_on_states or []) if str(state).strip()
        }
        self._night_mode_states = {
            str(state).strip() for state in list(night_mode_states or []) if str(state).strip()
        }
        self._effective_suppress_states = set(self._suppress_on_states)
        if self._room_type in NIGHT_SUPPRESS_ROOM_TYPES:
            self._effective_suppress_states.update(self._night_mode_states)
        self._timeout_mode = timeout_mode if timeout_mode in {"fixed", "learned"} else "learned"
        self._base_timeout_s = int(base_timeout_min or default_base_min) * 60
        self._fast_exit_timeout_s = int(fast_exit_timeout_s or default_fast_exit_s)
        self._dim_brightness_pct = max(1, min(100, int(dim_brightness_pct)))
        self._dim_ratio = max(0.0, min(1.0, float(dim_ratio)))
        self._profiles = _normalize_profiles(profiles)
        self._entity_steps = [dict(step) for step in list(entity_steps or [])]
        self._outdoor_lux_scale = dict(outdoor_lux_scale or {})
        self._manual_override_window_s = max(0, int(manual_override_window_min)) * 60

        self._visit_durations_s: deque[float] = deque(maxlen=_VISIT_RING_SIZE)
        self._visit_started_monotonic: float | None = None
        self._absence_started_monotonic: float | None = None
        self._dim_due_monotonic: float | None = None
        self._off_due_monotonic: float | None = None
        self._dim_applied = False
        self._manual_override_until: float | None = None
        self._manual_override_active = False
        self._manual_on_hold = False
        self._was_occupied = False
        self._last_applied_profile: str | None = None
        self._last_applied_outdoor_scale: float | None = None
        self._selected_profile: str | None = None
        self._current_indoor_bucket: str | None = None
        self._current_outdoor_bucket: str | None = None
        self._current_outdoor_scale: float | None = None
        self._current_house_state = "unknown"
        self._issued_context_ids: deque[tuple[str, float]] = deque(maxlen=64)

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        snapshot = history[-1]
        now = time.monotonic()
        self._expire_manual_override(now)
        occupied = self._room_id in snapshot.occupied_rooms
        if occupied:
            self._on_occupied(now)
            return self._evaluate_occupied(snapshot)
        self._on_unoccupied(now)
        return self._evaluate_absent(now)

    def scheduled_jobs(self, entry_id: str) -> dict[str, ScheduledRuntimeJob]:
        jobs: dict[str, ScheduledRuntimeJob] = {}
        if self._dim_due_monotonic is not None and not self._dim_applied:
            job_id = f"smart_lighting_dim:{self._reaction_id}"
            jobs[job_id] = ScheduledRuntimeJob(
                job_id=job_id,
                owner=self.__class__.__name__,
                entry_id=entry_id,
                due_monotonic=self._dim_due_monotonic,
                label=f"smart lighting dim: {self._room_id}",
            )
        if self._off_due_monotonic is not None:
            job_id = f"smart_lighting_off:{self._reaction_id}"
            jobs[job_id] = ScheduledRuntimeJob(
                job_id=job_id,
                owner=self.__class__.__name__,
                entry_id=entry_id,
                due_monotonic=self._off_due_monotonic,
                label=f"smart lighting off: {self._room_id}",
            )
        return jobs

    def reset_learning_state(self) -> None:
        self._reset_runtime_counters()
        self._visit_durations_s.clear()
        self._visit_started_monotonic = None
        self._clear_absence_sequence()
        self._manual_override_until = None
        self._manual_override_active = False
        self._manual_on_hold = False
        self._was_occupied = False
        self._last_applied_profile = None
        self._last_applied_outdoor_scale = None
        self._selected_profile = None
        self._issued_context_ids.clear()

    def diagnostics(self) -> dict[str, Any]:
        data = self._base_diagnostics()
        data.update(
            {
                "room_id": self._room_id,
                "room_type": self._room_type,
                "indoor_lux_signal": self._indoor_lux_signal,
                "outdoor_lux_signal": self._outdoor_lux_signal,
                "lux_on_buckets": sorted(self._lux_on_buckets),
                "effective_suppress_states": sorted(self._effective_suppress_states),
                "timeout_mode": self._timeout_mode,
                "base_timeout_s": self._base_timeout_s,
                "fast_exit_timeout_s": self._fast_exit_timeout_s,
                "manual_override_active": self._manual_override_active,
                "manual_on_hold": self._manual_on_hold,
                "selected_profile": self._selected_profile,
                "last_applied_profile": self._last_applied_profile,
                "current_indoor_bucket": self._current_indoor_bucket,
                "current_outdoor_bucket": self._current_outdoor_bucket,
                "current_outdoor_scale": self._current_outdoor_scale,
                "visit_samples": len(self._visit_durations_s),
                "dim_due_monotonic": self._dim_due_monotonic,
                "off_due_monotonic": self._off_due_monotonic,
                "dim_applied": self._dim_applied,
                "issued_context_ids": len(self._issued_context_ids),
            }
        )
        return data

    def owns_context_id(self, context_id: str | None) -> bool:
        """Return whether a HA state change context belongs to this reaction instance."""
        self._purge_issued_context_ids(time.monotonic())
        context_id = str(context_id or "").strip()
        if not context_id:
            return False
        return any(issued_id == context_id for issued_id, _expires_at in self._issued_context_ids)

    def tracks_light_entity(self, entity_id: str) -> bool:
        """Return whether this reaction may manage the given light entity."""
        entity_id = str(entity_id or "").strip()
        if not entity_id:
            return False
        return entity_id in self._configured_light_entities()

    def handle_external_light_change(self, entity_id: str, new_state: str) -> None:
        """Apply manual override state for an external light change."""
        entity_id = str(entity_id or "").strip()
        new_state = str(new_state or "").strip().lower()
        if not entity_id or new_state not in {"on", "off"}:
            return
        if new_state == "off" and entity_id in self._active_profile_light_entities():
            self._clear_absence_sequence()
            self._manual_override_active = True
            self._manual_override_until = (
                time.monotonic() + self._manual_override_window_s
                if self._manual_override_window_s > 0
                else None
            )
            return
        if new_state == "on" and self._would_be_active_for_manual_hold():
            self._manual_on_hold = True

    def _evaluate_occupied(self, snapshot: DecisionSnapshot) -> list[ApplyStep]:
        self._current_house_state = str(snapshot.house_state or "unknown").strip()
        self._current_indoor_bucket = self._current_bucket_for(self._indoor_lux_signal)
        self._current_outdoor_bucket = (
            self._current_bucket_for(self._outdoor_lux_signal)
            if self._outdoor_lux_signal
            else None
        )
        self._current_outdoor_scale = self._outdoor_scale_for(self._current_outdoor_bucket)
        if self._manual_override_active:
            return []
        if self._current_house_state in self._effective_suppress_states:
            return []
        if self._current_indoor_bucket not in self._lux_on_buckets:
            return []

        profile_name, entity_steps = self._select_entity_steps(snapshot)
        self._selected_profile = profile_name
        if not entity_steps:
            return []
        entity_steps = self._apply_outdoor_scale(entity_steps)
        if self._manual_on_hold and self._last_applied_profile is not None:
            return []
        if not self._needs_apply(profile_name, entity_steps):
            return []
        self._mark_fired()
        self._last_applied_profile = profile_name
        self._last_applied_outdoor_scale = self._current_outdoor_scale
        return self._with_batch_context(
            self._build_steps(entity_steps, reason_prefix="room_smart_lighting_assist")
        )

    def _evaluate_absent(self, now: float) -> list[ApplyStep]:
        if self._off_due_monotonic is None:
            return []
        if (
            self._dim_due_monotonic is not None
            and not self._dim_applied
            and now >= self._dim_due_monotonic
        ):
            self._dim_applied = True
            return self._with_batch_context(
                self._build_steps(
                    self._dimmed_steps(self._active_entity_steps()),
                    reason_prefix="room_smart_lighting_assist:dim",
                )
            )
        if now >= self._off_due_monotonic:
            steps = self._with_batch_context(
                self._build_steps(
                    self._off_steps(self._active_entity_steps()),
                    reason_prefix="room_smart_lighting_assist:off",
                )
            )
            self._clear_absence_sequence()
            self._last_applied_profile = None
            self._last_applied_outdoor_scale = None
            return steps
        return []

    def _on_occupied(self, now: float) -> None:
        if not self._was_occupied:
            self._visit_started_monotonic = now
            self._manual_override_active = False
            self._manual_override_until = None
            self._manual_on_hold = False
            self._last_applied_profile = None
            self._last_applied_outdoor_scale = None
        self._was_occupied = True
        self._clear_absence_sequence()

    def _on_unoccupied(self, now: float) -> None:
        if self._was_occupied:
            if self._visit_started_monotonic is not None:
                duration = max(0.0, now - self._visit_started_monotonic)
                self._visit_durations_s.append(duration)
                timeout_s = self._effective_timeout_s(duration)
                self._absence_started_monotonic = now
                self._dim_due_monotonic = now + timeout_s * (1.0 - self._dim_ratio)
                self._off_due_monotonic = now + timeout_s
                self._dim_applied = False
            self._visit_started_monotonic = None
        self._was_occupied = False

    def _clear_absence_sequence(self) -> None:
        self._absence_started_monotonic = None
        self._dim_due_monotonic = None
        self._off_due_monotonic = None
        self._dim_applied = False

    def _effective_timeout_s(self, current_visit_duration_s: float) -> float:
        threshold = self._fast_exit_timeout_s * 3
        if self._timeout_mode == "learned" and len(self._visit_durations_s) >= _LEARNED_MIN_VISITS:
            ordered = sorted(self._visit_durations_s)
            index = max(0, int(len(ordered) * 0.25) - 1)
            threshold = ordered[index]
        if current_visit_duration_s < threshold:
            return float(self._fast_exit_timeout_s)
        return float(self._base_timeout_s)

    def _select_entity_steps(self, snapshot: DecisionSnapshot) -> tuple[str | None, list[dict[str, Any]]]:
        current_dt = parse_snapshot_ts(snapshot.ts)
        hour_bucket = _hour_bucket(current_dt)
        if self._current_house_state in self._night_mode_states:
            for profile in self._profiles:
                states = _string_list(profile.get("house_states"))
                if "sleeping" in states:
                    return _profile_name(profile), _profile_steps(profile)
            return "night_fallback", self._night_fallback_steps()

        for profile in self._profiles:
            states = _string_list(profile.get("house_states"))
            hour_buckets = _string_list(profile.get("hour_buckets"))
            if states and self._current_house_state not in states:
                continue
            if hour_buckets and hour_bucket not in hour_buckets:
                continue
            return _profile_name(profile), _profile_steps(profile)
        if self._entity_steps:
            return "entity_steps", [dict(step) for step in self._entity_steps]
        if self._profiles:
            profile = self._profiles[0]
            return _profile_name(profile), _profile_steps(profile)
        return None, []

    def _active_entity_steps(self) -> list[dict[str, Any]]:
        if self._last_applied_profile == "entity_steps":
            return [dict(step) for step in self._entity_steps]
        for profile in self._profiles:
            if _profile_name(profile) == self._last_applied_profile:
                return _profile_steps(profile)
        if self._entity_steps:
            return [dict(step) for step in self._entity_steps]
        if self._profiles:
            return _profile_steps(self._profiles[0])
        return []

    def _configured_light_entities(self) -> set[str]:
        entities = {str(step.get("entity_id") or "").strip() for step in self._entity_steps}
        for profile in self._profiles:
            entities.update(str(step.get("entity_id") or "").strip() for step in _profile_steps(profile))
        return {entity_id for entity_id in entities if entity_id}

    def _active_profile_light_entities(self) -> set[str]:
        return {
            str(step.get("entity_id") or "").strip()
            for step in self._active_entity_steps()
            if str(step.get("entity_id") or "").strip()
        }

    def _would_be_active_for_manual_hold(self) -> bool:
        if not self._was_occupied:
            return False
        if self._current_house_state in self._effective_suppress_states:
            return False
        if self._current_indoor_bucket not in self._lux_on_buckets:
            return False
        return True

    def _with_batch_context(self, steps: list[ApplyStep]) -> list[ApplyStep]:
        if not steps:
            return []
        context_id = str(uuid4())
        self._register_issued_context_id(context_id)
        return [dataclass_replace(step, context_id=context_id) for step in steps]

    def _register_issued_context_id(self, context_id: str) -> None:
        now = time.monotonic()
        self._purge_issued_context_ids(now)
        self._issued_context_ids.append((context_id, now + _ISSUED_CONTEXT_TTL_S))

    def _purge_issued_context_ids(self, now: float) -> None:
        while self._issued_context_ids and self._issued_context_ids[0][1] <= now:
            self._issued_context_ids.popleft()

    def _night_fallback_steps(self) -> list[dict[str, Any]]:
        base = self._entity_steps or (self._profiles[0].get("entity_steps") if self._profiles else [])
        steps: list[dict[str, Any]] = []
        for raw in list(base or []):
            step = dict(raw)
            if str(step.get("action") or "").strip() == "on":
                step["brightness"] = 26
                step["color_temp_kelvin"] = 2200
            steps.append(step)
        return steps

    def _apply_outdoor_scale(self, entity_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scale = self._current_outdoor_scale
        if scale is None:
            return entity_steps
        adjusted: list[dict[str, Any]] = []
        for raw in entity_steps:
            step = dict(raw)
            brightness = _coerce_int(step.get("brightness"))
            if brightness is not None and str(step.get("action") or "") == "on":
                step["brightness"] = max(1, min(255, int(round(brightness * scale))))
            adjusted.append(step)
        return adjusted

    def _outdoor_scale_for(self, bucket: str | None) -> float | None:
        if not bucket:
            return None
        value = self._outdoor_lux_scale.get(bucket)
        return _coerce_float(value)

    def _needs_apply(self, profile_name: str | None, entity_steps: list[dict[str, Any]]) -> bool:
        if self._last_applied_profile != profile_name:
            return True
        if self._last_applied_outdoor_scale != self._current_outdoor_scale:
            return True
        return self._entity_steps_need_apply(entity_steps)

    def _dimmed_steps(self, entity_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        brightness = max(1, min(255, int(round(255 * self._dim_brightness_pct / 100.0))))
        result: list[dict[str, Any]] = []
        for raw in entity_steps:
            step = dict(raw)
            if str(step.get("action") or "").strip() == "on":
                step["brightness"] = brightness
                result.append(step)
        return result

    @staticmethod
    def _off_steps(entity_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in entity_steps:
            entity_id = str(raw.get("entity_id") or "").strip()
            if entity_id:
                result.append({"entity_id": entity_id, "action": "off"})
        return result

    def _expire_manual_override(self, now: float) -> None:
        if (
            self._manual_override_until is not None
            and self._manual_override_until <= now
            and self._manual_override_active
        ):
            self._manual_override_active = False
            self._manual_override_until = None


def build_room_smart_lighting_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomSmartLightingAssistReaction | None:
    """Build a smart lighting reaction from persisted config."""
    try:
        room_id = str(cfg["room_id"]).strip()
        indoor_lux_signal = str(cfg.get("indoor_lux_signal") or "room_lux").strip()
        lux_on_buckets = _string_list(cfg.get("lux_on_buckets"))
        entity_steps = [dict(step) for step in list(cfg.get("entity_steps") or [])]
        profiles = cfg.get("profiles")
        if not room_id or not indoor_lux_signal or not lux_on_buckets:
            raise ValueError("missing required smart lighting fields")
        if not entity_steps and not _normalize_profiles(profiles):
            raise ValueError("missing entity_steps/profiles")
    except (KeyError, TypeError, ValueError):
        return None

    rooms = list(dict(getattr(engine, "_entry").options).get("rooms") or [])  # noqa: SLF001
    indoor_bucket_labels = room_signal_bucket_labels(rooms, room_id, indoor_lux_signal)
    configured_scale = dict(cfg.get("outdoor_lux_scale") or {})
    ambient = dict(cfg.get("ambient_modulation") or {})
    if not configured_scale and isinstance(ambient.get("buckets"), dict):
        configured_scale = dict(ambient.get("buckets") or {})

    return RoomSmartLightingAssistReaction(
        hass=engine._hass,  # noqa: SLF001
        bucket_getter=engine.signal_bucket,
        room_id=room_id,
        indoor_lux_signal=indoor_lux_signal,
        outdoor_lux_signal=str(cfg.get("outdoor_lux_signal") or "").strip() or None,
        lux_on_buckets=[
            bucket for bucket in lux_on_buckets if not indoor_bucket_labels or bucket in indoor_bucket_labels
        ]
        or lux_on_buckets,
        room_type=str(cfg.get("room_type") or "generic").strip(),
        suppress_on_states=_string_list(cfg.get("suppress_on_states")),
        night_mode_states=_string_list(cfg.get("night_mode_states")),
        timeout_mode=str(cfg.get("timeout_mode") or "learned").strip(),
        base_timeout_min=_coerce_int(cfg.get("base_timeout_min")),
        fast_exit_timeout_s=_coerce_int(cfg.get("fast_exit_timeout_s")),
        dim_brightness_pct=_coerce_int(cfg.get("dim_brightness_pct"))
        or _DEFAULT_DIM_BRIGHTNESS_PCT,
        dim_ratio=_coerce_float(cfg.get("dim_ratio")) or _DEFAULT_DIM_RATIO,
        profiles=profiles,
        entity_steps=entity_steps,
        outdoor_lux_scale={str(k): float(v) for k, v in configured_scale.items() if _coerce_float(v) is not None},
        manual_override_window_min=_coerce_int(cfg.get("manual_override_window_min"))
        or _DEFAULT_MANUAL_OVERRIDE_WINDOW_MIN,
        reaction_id=proposal_id,
    )


def validate_smart_lighting_contract(cfg: dict[str, Any]) -> bool:
    """Return True when the smart lighting config has the minimum runnable shape."""
    room_id = str(cfg.get("room_id") or "").strip()
    indoor_lux_signal = str(cfg.get("indoor_lux_signal") or "").strip()
    lux_on_buckets = _string_list(cfg.get("lux_on_buckets"))
    profiles = _normalize_profiles(cfg.get("profiles"))
    entity_steps = [dict(step) for step in list(cfg.get("entity_steps") or []) if isinstance(step, dict)]
    if not room_id or not indoor_lux_signal or not lux_on_buckets:
        return False
    if not profiles and not entity_steps:
        return False
    for step in entity_steps:
        if not _valid_entity_step(step):
            return False
    for profile in profiles:
        if not _profile_steps(profile) or any(not _valid_entity_step(step) for step in _profile_steps(profile)):
            return False
    return True


def present_room_smart_lighting_assist_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels: dict[str, str],  # noqa: ARG001
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    return f"{room_id}: smart lighting" if room_id else reaction_id


def present_room_smart_lighting_assist_proposal_label(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    language: str,  # noqa: ARG001
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    return f"{room_id}: smart lighting" if room_id else None


def present_room_smart_lighting_assist_review_title(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    language: str,
    tuning: bool,  # noqa: ARG001
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    return (
        f"Illuminazione smart stanza: {room_id}"
        if language.startswith("it")
        else f"Smart room lighting: {room_id}"
    )


def present_admin_authored_room_smart_lighting_assist_details(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    profiles = _normalize_profiles(cfg.get("profiles"))
    lines = [
        (
            f"Profili configurati: {len(profiles)}"
            if language.startswith("it")
            else f"Configured profiles: {len(profiles)}"
        )
    ]
    steps = [dict(step) for step in list(cfg.get("entity_steps") or []) if isinstance(step, dict)]
    if not steps and profiles:
        steps = _profile_steps(profiles[0])
    lines.extend(render_entity_steps_discovery_details(steps, language=language))
    return lines


def present_learned_room_smart_lighting_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    return present_admin_authored_room_smart_lighting_assist_details(
        flow,
        proposal,
        cfg,
        language,
    )


def present_tuning_room_smart_lighting_assist_details(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    current = [dict(step) for step in list(target_cfg.get("entity_steps") or []) if isinstance(step, dict)]
    proposed = [dict(step) for step in list(cfg.get("entity_steps") or []) if isinstance(step, dict)]
    if current and proposed and current != proposed:
        return render_entity_steps_tuning_details(current, proposed, language=language)
    return []


def _normalize_profiles(
    profiles: list[dict[str, Any]] | dict[str, dict[str, Any]] | Any,
) -> list[dict[str, Any]]:
    if isinstance(profiles, dict):
        result = []
        for name, payload in profiles.items():
            if isinstance(payload, dict):
                item = dict(payload)
                item.setdefault("name", str(name))
                result.append(item)
        return result
    return [dict(item) for item in list(profiles or []) if isinstance(item, dict)]


def _profile_name(profile: dict[str, Any]) -> str:
    return str(profile.get("name") or profile.get("profile") or "profile").strip() or "profile"


def _profile_steps(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(step) for step in list(profile.get("entity_steps") or []) if isinstance(step, dict)]


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in list(value or []) if str(item).strip()]


def _valid_entity_step(step: dict[str, Any]) -> bool:
    entity_id = str(step.get("entity_id") or "").strip()
    action = str(step.get("action") or "").strip()
    return bool(entity_id and action in {"on", "off"})


def _hour_bucket(current_dt: datetime | None) -> str:
    if current_dt is None:
        return "unknown"
    hour = current_dt.hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "day"
    if 17 <= hour < 23:
        return "evening"
    return "night"


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
