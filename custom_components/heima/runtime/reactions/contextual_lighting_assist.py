"""Context-aware room lighting reaction driven by profiles and ordered rules."""

from __future__ import annotations

from datetime import datetime
from datetime import time as dt_time
from typing import Any

from ...const import HOUSE_STATES_CANONICAL
from ...room_sources import room_signal_bucket_labels
from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from ._lighting_review import (
    render_entity_steps_discovery_details,
    render_entity_steps_tuning_details,
)
from ._room_lighting_base import _BaseRoomLightingAssist
from .composite import parse_snapshot_ts

_TRANSIENT_OCCUPANCY_MAX_S = 600.0
_CONTEXTUAL_OCCUPANCY_REASONS = {"focus", "settled", "transient", "generic"}
_AMBIENT_MODULATION_MODE = "brightness_multiplier"


def derive_contextual_occupancy_reason(*, house_state: str, occupancy_age_s: float | None) -> str:
    """Return a constrained proxy reason for why the room is occupied."""
    if str(house_state or "").strip() == "working":
        return "focus"
    if occupancy_age_s is None:
        return "generic"
    if occupancy_age_s < _TRANSIENT_OCCUPANCY_MAX_S:
        return "transient"
    return "settled"


def time_window_matches(*, current_time: dt_time, window: dict[str, Any]) -> bool:
    """Return True when a HH:MM window matches current_time, including midnight crossing."""
    start_raw = str(window.get("start") or "").strip()
    end_raw = str(window.get("end") or "").strip()
    if not start_raw or not end_raw:
        return False
    start = _parse_hhmm(start_raw)
    end = _parse_hhmm(end_raw)
    if start is None or end is None:
        return False
    if start <= end:
        return start <= current_time < end
    return current_time >= start or current_time < end


def resolve_contextual_lighting_profile(
    *,
    house_state: str,
    current_dt: datetime,
    occupancy_age_s: float | None,
    rules: list[dict[str, Any]],
    default_profile: str | None,
) -> tuple[str | None, int | None, str | None, str]:
    """Resolve the selected profile from ordered rules and conservative context."""
    occupancy_reason = derive_contextual_occupancy_reason(
        house_state=house_state,
        occupancy_age_s=occupancy_age_s,
    )
    current_time = current_dt.timetz().replace(tzinfo=None)
    for index, rule in enumerate(rules):
        profile = str(rule.get("profile") or "").strip()
        if not profile:
            continue
        states = [str(v).strip() for v in list(rule.get("house_state_in") or []) if str(v).strip()]
        if states and house_state not in states:
            continue
        reasons = [
            str(v).strip() for v in list(rule.get("occupancy_reason_in") or []) if str(v).strip()
        ]
        if reasons and occupancy_reason not in reasons:
            continue
        time_window = rule.get("time_window")
        if (
            isinstance(time_window, dict)
            and time_window
            and not time_window_matches(
                current_time=current_time,
                window=time_window,
            )
        ):
            continue
        return profile, index, _rule_summary(rule), occupancy_reason
    return default_profile, None, "default_profile", occupancy_reason


class RoomContextualLightingAssistReaction(_BaseRoomLightingAssist):
    """Apply different lighting profiles for the same dark-room trigger."""

    def __init__(
        self,
        *,
        hass: Any,
        bucket_getter: Any | None = None,
        occupancy_age_getter: Any | None = None,
        room_id: str,
        primary_signal_entities: list[str],
        primary_bucket: str,
        primary_bucket_match_mode: str = "eq",
        primary_bucket_labels: list[str] | None = None,
        primary_signal_name: str = "room_lux",
        profiles: dict[str, dict[str, Any]] | None = None,
        rules: list[dict[str, Any]] | None = None,
        default_profile: str | None = None,
        ambient_modulation: dict[str, Any] | None = None,
        followup_window_s: int = 900,
        reaction_id: str | None = None,
    ) -> None:
        self._bucket_getter = bucket_getter or (lambda _room_id, _signal_name: None)
        self._occupancy_age_getter = occupancy_age_getter or (lambda _room_id: None)
        super().__init__(
            hass=hass,
            bucket_getter=bucket_getter,
            room_id=room_id,
            reaction_id=reaction_id,
            followup_window_s=followup_window_s,
            primary_signal_name=primary_signal_name,
            primary_bucket=primary_bucket,
            primary_bucket_match_mode=primary_bucket_match_mode,
            primary_bucket_labels=primary_bucket_labels,
        )
        self._primary_signal_entities = list(primary_signal_entities)
        self._profiles = {
            str(name).strip(): dict(payload)
            for name, payload in dict(profiles or {}).items()
            if str(name).strip() and isinstance(payload, dict)
        }
        self._rules = [dict(item) for item in list(rules or []) if isinstance(item, dict)]
        self._default_profile = str(default_profile or "").strip() or None
        self._ambient_modulation = dict(ambient_modulation or {})
        self._last_applied_profile: str | None = None
        self._current_primary_bucket_value: str | None = None
        self._current_house_state: str = "unknown"
        self._occupancy_age_s: float | None = None
        self._occupancy_reason: str = "generic"
        self._selected_profile: str | None = None
        self._selected_rule_index: int | None = None
        self._selected_rule_summary: str | None = None
        self._ambient_source_bucket: str | None = None
        self._ambient_brightness_scale: float | None = None
        self._last_applied_ambient_scale: float | None = None

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        snapshot = history[-1]
        self._current_house_state = str(snapshot.house_state or "unknown")
        if self._room_id not in snapshot.occupied_rooms:
            self._last_applied_profile = None
            self._last_fired_ts = None
            self._last_fired_iso = None
            self._occupancy_age_s = None
            self._occupancy_reason = "generic"
            self._selected_profile = None
            self._selected_rule_index = None
            self._selected_rule_summary = None
            self._ambient_source_bucket = None
            self._ambient_brightness_scale = None
            self._last_applied_ambient_scale = None
            return []

        self._current_primary_bucket_value = self._current_primary_bucket()
        if not self._bucket_matches(self._current_primary_bucket_value):
            return []

        current_dt = parse_snapshot_ts(snapshot.ts)
        if current_dt is None:
            return []
        self._occupancy_age_s = _coerce_float(self._occupancy_age_getter(self._room_id))
        profile_name, rule_index, rule_summary, occupancy_reason = (
            resolve_contextual_lighting_profile(
                house_state=self._current_house_state,
                current_dt=current_dt,
                occupancy_age_s=self._occupancy_age_s,
                rules=self._rules,
                default_profile=self._default_profile,
            )
        )
        self._occupancy_reason = occupancy_reason
        self._selected_profile = profile_name
        self._selected_rule_index = rule_index
        self._selected_rule_summary = rule_summary
        if not profile_name:
            return []
        entity_steps = self._profile_entity_steps(profile_name)
        if not entity_steps:
            return []
        entity_steps = self._apply_ambient_modulation(entity_steps)
        if not self._needs_apply(profile_name, entity_steps):
            return []
        if not self._is_cooled_down() and not self._profile_transition_needs_immediate_apply(
            profile_name
        ):
            self._mark_suppressed()
            return []

        self._mark_fired()
        self._last_applied_profile = profile_name
        self._last_applied_ambient_scale = self._ambient_brightness_scale
        return self._build_steps(entity_steps, reason_prefix="room_contextual_lighting_assist")

    def reset_learning_state(self) -> None:
        self._reset_runtime_counters()
        self._last_applied_profile = None
        self._occupancy_age_s = None
        self._occupancy_reason = "generic"
        self._selected_profile = None
        self._selected_rule_index = None
        self._selected_rule_summary = None
        self._ambient_source_bucket = None
        self._ambient_brightness_scale = None
        self._last_applied_ambient_scale = None

    def diagnostics(self) -> dict[str, Any]:
        data = self._base_diagnostics()
        data.update(
            {
                "current_primary_bucket": self._current_primary_bucket_value,
                "current_house_state": self._current_house_state,
                "occupancy_age_s": self._occupancy_age_s,
                "occupancy_reason": self._occupancy_reason,
                "selected_profile": self._selected_profile,
                "last_applied_profile": self._last_applied_profile,
                "selected_rule_index": self._selected_rule_index,
                "selected_rule_summary": self._selected_rule_summary,
                "available_profiles": sorted(self._profiles),
                "ambient_source_bucket": self._ambient_source_bucket,
                "ambient_brightness_scale": self._ambient_brightness_scale,
            }
        )
        return data

    def _profile_entity_steps(self, profile_name: str) -> list[dict[str, Any]]:
        profile = dict(self._profiles.get(profile_name) or {})
        raw = profile.get("entity_steps")
        return [dict(step) for step in list(raw or []) if isinstance(step, dict)]

    def _needs_apply(self, profile_name: str, entity_steps: list[dict[str, Any]]) -> bool:
        if self._last_applied_profile != profile_name:
            return True
        if self._last_applied_ambient_scale != self._ambient_brightness_scale:
            return True
        return super()._entity_steps_need_apply(entity_steps)

    def _profile_transition_needs_immediate_apply(self, profile_name: str) -> bool:
        """Allow contextual transitions to re-apply immediately despite cooldown."""
        if self._last_applied_profile != profile_name:
            return True
        if self._last_applied_ambient_scale != self._ambient_brightness_scale:
            return True
        return False

    def _apply_ambient_modulation(self, entity_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._ambient_source_bucket = None
        self._ambient_brightness_scale = None
        if not self._ambient_modulation:
            return entity_steps
        source_signal_name = str(self._ambient_modulation.get("source_signal_name") or "").strip()
        if not source_signal_name:
            return entity_steps
        mode = str(self._ambient_modulation.get("mode") or "").strip()
        if mode != _AMBIENT_MODULATION_MODE:
            return entity_steps
        bucket = self._current_bucket_for(source_signal_name)
        self._ambient_source_bucket = bucket
        multipliers = dict(self._ambient_modulation.get("buckets") or {})
        scale = _coerce_float(multipliers.get(str(bucket or "").strip()))
        if scale is None:
            return entity_steps
        self._ambient_brightness_scale = scale
        clamp_min = _coerce_int(self._ambient_modulation.get("clamp_min"))
        clamp_max = _coerce_int(self._ambient_modulation.get("clamp_max"))
        adjusted: list[dict[str, Any]] = []
        for raw in entity_steps:
            step = dict(raw)
            brightness = _coerce_int(step.get("brightness"))
            if brightness is None:
                adjusted.append(step)
                continue
            modulated = int(round(float(brightness) * scale))
            if clamp_min is not None:
                modulated = max(clamp_min, modulated)
            if clamp_max is not None:
                modulated = min(clamp_max, modulated)
            step["brightness"] = max(1, modulated)
            adjusted.append(step)
        return adjusted


def build_room_contextual_lighting_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomContextualLightingAssistReaction | None:
    """Build a contextual lighting reaction from persisted config."""
    try:
        room_id = str(cfg["room_id"]).strip()
        primary_signal_entities = [
            str(v).strip() for v in cfg.get("primary_signal_entities", []) if str(v).strip()
        ]
        primary_bucket = str(cfg.get("primary_bucket") or "").strip()
        primary_bucket_match_mode = str(cfg.get("primary_bucket_match_mode") or "eq").strip()
        primary_signal_name = str(cfg.get("primary_signal_name", "room_lux") or "room_lux").strip()
        profiles = dict(cfg.get("profiles") or {})
        rules = list(cfg.get("rules") or [])
        default_profile = str(cfg.get("default_profile") or "").strip()
        ambient_modulation = dict(cfg.get("ambient_modulation") or {})
        followup_window_s = int(cfg.get("followup_window_s", 900))
        if not room_id or not primary_signal_entities or not primary_bucket:
            raise ValueError("missing required contextual lighting fields")
        if not validate_contextual_lighting_contract(
            {
                "profiles": profiles,
                "rules": rules,
                "default_profile": default_profile,
                "ambient_modulation": ambient_modulation,
                "followup_window_s": followup_window_s,
            }
        ):
            raise ValueError("invalid contextual lighting contract")
    except (KeyError, TypeError, ValueError):
        return None
    rooms = list(dict(getattr(engine, "_entry").options).get("rooms") or [])  # noqa: SLF001
    primary_bucket_labels = room_signal_bucket_labels(rooms, room_id, primary_signal_name)
    return RoomContextualLightingAssistReaction(
        hass=engine._hass,  # noqa: SLF001
        bucket_getter=engine.signal_bucket,
        occupancy_age_getter=engine.room_occupancy_age_s,
        room_id=room_id,
        primary_signal_entities=primary_signal_entities,
        primary_bucket=primary_bucket,
        primary_bucket_match_mode=primary_bucket_match_mode,
        primary_bucket_labels=primary_bucket_labels,
        primary_signal_name=primary_signal_name,
        profiles=profiles,
        rules=rules,
        default_profile=default_profile,
        ambient_modulation=ambient_modulation,
        followup_window_s=followup_window_s,
        reaction_id=proposal_id,
    )


def validate_contextual_lighting_contract(cfg: dict[str, Any]) -> bool:
    """Return True when profiles/rules/default_profile form a valid contextual contract."""
    profiles = dict(cfg.get("profiles") or {})
    rules = list(cfg.get("rules") or [])
    default_profile = str(cfg.get("default_profile") or "").strip()
    followup_window_s = cfg.get("followup_window_s", 900)
    if not profiles or not isinstance(profiles.get(default_profile), dict):
        return False
    if _coerce_int(followup_window_s) is None or int(followup_window_s) < 0:
        return False
    for name, profile in profiles.items():
        if not str(name).strip():
            return False
        entity_steps = dict(profile).get("entity_steps")
        if not isinstance(entity_steps, list) or not entity_steps:
            return False
        for raw_step in entity_steps:
            if not isinstance(raw_step, dict):
                return False
            entity_id = str(raw_step.get("entity_id") or "").strip()
            action = str(raw_step.get("action") or "").strip()
            if not entity_id or action not in {"on", "off"}:
                return False
    for raw_rule in rules:
        if not isinstance(raw_rule, dict):
            return False
        profile = str(raw_rule.get("profile") or "").strip()
        if not profile or profile not in profiles:
            return False
        states = [
            str(v).strip() for v in list(raw_rule.get("house_state_in") or []) if str(v).strip()
        ]
        if states and any(state not in HOUSE_STATES_CANONICAL for state in states):
            return False
        reasons = [
            str(v).strip()
            for v in list(raw_rule.get("occupancy_reason_in") or [])
            if str(v).strip()
        ]
        if reasons and any(reason not in _CONTEXTUAL_OCCUPANCY_REASONS for reason in reasons):
            return False
        time_window = raw_rule.get("time_window")
        if time_window not in (None, {}) and (
            not isinstance(time_window, dict)
            or _parse_hhmm(str(time_window.get("start") or "").strip()) is None
            or _parse_hhmm(str(time_window.get("end") or "").strip()) is None
        ):
            return False
    ambient_modulation = cfg.get("ambient_modulation")
    if ambient_modulation not in (None, {}):
        if not isinstance(ambient_modulation, dict):
            return False
        source_signal_name = str(ambient_modulation.get("source_signal_name") or "").strip()
        mode = str(ambient_modulation.get("mode") or "").strip()
        buckets = ambient_modulation.get("buckets")
        if (
            not source_signal_name
            or mode != _AMBIENT_MODULATION_MODE
            or not isinstance(buckets, dict)
        ):
            return False
        if not buckets:
            return False
        for label, multiplier in buckets.items():
            if not str(label).strip() or _coerce_float(multiplier) is None:
                return False
        clamp_min = ambient_modulation.get("clamp_min")
        clamp_max = ambient_modulation.get("clamp_max")
        if clamp_min is not None and _coerce_int(clamp_min) is None:
            return False
        if clamp_max is not None and _coerce_int(clamp_max) is None:
            return False
        if clamp_min is not None and clamp_max is not None and int(clamp_min) > int(clamp_max):
            return False
    return True


def present_room_contextual_lighting_assist_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels: dict[str, str],  # noqa: ARG001
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    profiles = dict(cfg.get("profiles") or {})
    return f"{room_id}: contextual lighting ({len(profiles)} profiles)" if room_id else reaction_id


def present_room_contextual_lighting_assist_proposal_label(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    language: str,  # noqa: ARG001
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    profiles = dict(cfg.get("profiles") or {})
    if not room_id:
        return None
    return f"{room_id}: contextual lighting ({len(profiles)} profiles)"


def present_room_contextual_lighting_assist_review_title(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    language: str,
    tuning: bool,  # noqa: ARG001
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    return (
        f"Illuminazione contestuale stanza: {room_id}"
        if language.startswith("it")
        else f"Contextual room lighting: {room_id}"
    )


def present_admin_authored_room_contextual_lighting_assist_details(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    profiles = dict(cfg.get("profiles") or {})
    rules = list(cfg.get("rules") or [])
    is_it = language.startswith("it")
    lines = [
        (
            f"Profili configurati: {len(profiles)}"
            if is_it
            else f"Configured profiles: {len(profiles)}"
        ),
        (f"Regole configurate: {len(rules)}" if is_it else f"Configured rules: {len(rules)}"),
    ]
    default_profile = str(cfg.get("default_profile") or "").strip()
    if default_profile:
        lines.append(
            f"Profilo di default: {default_profile}"
            if is_it
            else f"Default profile: {default_profile}"
        )
    ambient_modulation = dict(cfg.get("ambient_modulation") or {})
    ambient_signal = str(ambient_modulation.get("source_signal_name") or "").strip()
    if ambient_signal:
        lines.append(
            f"Modulazione ambientale: {ambient_signal}"
            if is_it
            else f"Ambient modulation: {ambient_signal}"
        )
    for profile_name, profile in profiles.items():
        entity_steps = profile.get("entity_steps")
        if isinstance(entity_steps, list) and entity_steps:
            lines.extend(render_entity_steps_discovery_details(entity_steps, language=language))
            break
    return lines


def present_learned_room_contextual_lighting_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    return present_admin_authored_room_contextual_lighting_assist_details(
        flow,
        proposal,
        cfg,
        language,
    )


def present_tuning_room_contextual_lighting_assist_details(
    flow: Any,  # noqa: ARG001
    proposal: Any,  # noqa: ARG001
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    is_it = language.startswith("it")
    lines: list[str] = []
    current_default = str(target_cfg.get("default_profile") or "").strip()
    proposed_default = str(cfg.get("default_profile") or "").strip()
    if current_default != proposed_default:
        lines.append(
            f"Profilo di default: {current_default} -> {proposed_default}"
            if is_it
            else f"Default profile: {current_default} -> {proposed_default}"
        )
    current_profiles = dict(target_cfg.get("profiles") or {})
    proposed_profiles = dict(cfg.get("profiles") or {})
    for profile_name in sorted(set(current_profiles) & set(proposed_profiles)):
        current_steps = current_profiles.get(profile_name, {}).get("entity_steps")
        proposed_steps = proposed_profiles.get(profile_name, {}).get("entity_steps")
        if (
            current_steps != proposed_steps
            and isinstance(current_steps, list)
            and isinstance(proposed_steps, list)
        ):
            lines.extend(
                render_entity_steps_tuning_details(
                    current_steps,
                    proposed_steps,
                    language=language,
                )
            )
            break
    return lines


def _parse_hhmm(raw: str) -> dt_time | None:
    try:
        hour_str, minute_str = raw.split(":", 1)
        return dt_time(hour=int(hour_str), minute=int(minute_str))
    except (TypeError, ValueError):
        return None


def _rule_summary(rule: dict[str, Any]) -> str:
    parts = [f"profile={str(rule.get('profile') or '').strip()}"]
    states = [str(v).strip() for v in list(rule.get("house_state_in") or []) if str(v).strip()]
    if states:
        parts.append(f"house_state_in={','.join(states)}")
    reasons = [
        str(v).strip() for v in list(rule.get("occupancy_reason_in") or []) if str(v).strip()
    ]
    if reasons:
        parts.append(f"occupancy_reason_in={','.join(reasons)}")
    time_window = rule.get("time_window")
    if isinstance(time_window, dict):
        start = str(time_window.get("start") or "").strip()
        end = str(time_window.get("end") or "").strip()
        if start and end:
            parts.append(f"time_window={start}-{end}")
    return " ".join(parts)


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
