"""Security-owned vacation presence simulation reaction bootstrap."""

from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any

from homeassistant.util import dt as dt_util

from ..contracts import ApplyStep
from ..scheduler import ScheduledRuntimeJob
from ..snapshot import DecisionSnapshot
from ._compat import resolve_reaction_type
from .base import HeimaReaction

_SOURCE_EVENT_RECOVERY_WINDOW_S = 120
_SOURCE_PROFILE_MAX_AGE_DAYS = 90
_SOURCE_PROFILE_PREFERRED_AGE_DAYS = 45
_MIN_EVENT_GAP_MIN = 18
_LATE_OUTLIER_SOFT_LIMIT_MIN = 23 * 60 + 15
_LATE_OUTLIER_HARD_LIMIT_MIN = 23 * 60 + 30
_ROOM_CLOSEOUT_PREFERRED_MIN = 25
_ROOM_CLOSEOUT_SOFT_MAX_MIN = 150
_ROOM_CLOSEOUT_HARD_MAX_MIN = 240
_TEMPORAL_COMPANION_PREFERRED_MIN = 35
_TEMPORAL_COMPANION_SOFT_MAX_MIN = 150
_SEQUENCE_COMPANION_PREFERRED_MIN = 20
_SEQUENCE_COMPANION_SOFT_MAX_MIN = 120
_EVENING_SHAPE_SPAN_TOLERANCE_MIN = 30
_EVENING_SHAPE_SPAN_SOFT_TOLERANCE_MIN = 90


class VacationPresenceSimulationReaction(HeimaReaction):
    """Bootstrap dynamic-policy reaction for vacation presence simulation.

    This slice selects a credible source profile from accepted lighting
    reactions and exposes runtime gating diagnostics, but the derived nightly
    execution plan still lands in the next step.
    """

    def __init__(
        self,
        *,
        reaction_id: str,
        enabled: bool,
        allowed_rooms: list[str],
        allowed_entities: list[str],
        requires_dark_outside: bool,
        simulation_aggressiveness: str,
        min_jitter_override_min: int | None,
        max_jitter_override_min: int | None,
        max_events_per_evening_override: int | None,
        latest_end_time_override: str | None,
        skip_if_presence_detected: bool,
        source_profile_kind: str,
        source_reaction_ids: list[str],
        source_rooms: list[str],
        source_profiles: list[dict[str, Any]],
        hass: Any,
    ) -> None:
        self._reaction_id = reaction_id
        self._hass = hass
        self._enabled = enabled
        self._allowed_rooms = list(allowed_rooms)
        self._allowed_entities = list(allowed_entities)
        self._requires_dark_outside = requires_dark_outside
        self._simulation_aggressiveness = simulation_aggressiveness
        self._min_jitter_override_min = min_jitter_override_min
        self._max_jitter_override_min = max_jitter_override_min
        self._max_events_per_evening_override = max_events_per_evening_override
        self._latest_end_time_override = latest_end_time_override
        self._skip_if_presence_detected = skip_if_presence_detected
        self._source_profile_kind = source_profile_kind
        self._source_reaction_ids = list(source_reaction_ids)
        self._source_rooms = list(source_rooms)
        self._source_profiles = list(source_profiles)
        self._last_blocked_reason = (
            "insufficient_learned_evidence"
            if not self._source_reaction_ids
            else "waiting_for_snapshot"
        )
        self._fired_event_ids_by_date: dict[str, set[str]] = {}
        self._fire_count = 0
        self._last_fired_ts: float | None = None
        self._last_simulated_activation: str | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not self._enabled:
            self._last_blocked_reason = "disabled"
            return []
        if not self._source_reaction_ids:
            self._last_blocked_reason = "insufficient_learned_evidence"
            return []
        if not history:
            self._last_blocked_reason = "waiting_for_snapshot"
            return []

        current = history[-1]
        if current.house_state != "vacation":
            self._last_blocked_reason = "not_in_vacation"
            return []
        if self._skip_if_presence_detected and current.anyone_home:
            self._last_blocked_reason = "presence_detected"
            return []
        if self._requires_dark_outside:
            dark_ok, dark_reason = self._is_dark_outside()
            if not dark_ok:
                self._last_blocked_reason = dark_reason
                return []

        now_local = dt_util.now()
        tonight_plan, plan_reason = self._derive_tonight_plan(now_local)
        if not tonight_plan:
            self._last_blocked_reason = plan_reason
            return []
        current_event = self._current_due_event(tonight_plan, now_local)
        if current_event is None:
            self._last_blocked_reason = "awaiting_next_planned_activation"
            return []

        self._mark_event_fired(current_event["event_id"], now_local.date())
        self._fire_count += 1
        self._last_fired_ts = time.monotonic()
        self._last_simulated_activation = now_local.isoformat()
        self._last_blocked_reason = ""
        return self._build_steps_from_event(current_event)

    def scheduled_jobs(self, entry_id: str) -> dict[str, ScheduledRuntimeJob]:
        if not self._enabled or not self._source_reaction_ids:
            return {}
        if self._current_house_state() != "vacation":
            return {}
        if self._skip_if_presence_detected and self._current_anyone_home():
            return {}
        if self._requires_dark_outside:
            dark_ok, _ = self._is_dark_outside()
            if not dark_ok:
                return {}

        now_local = dt_util.now()
        tonight_plan, _ = self._derive_tonight_plan(now_local)
        next_event = self._next_pending_event(tonight_plan, now_local)
        if next_event is None:
            return {}

        due_local = next_event["due_local"]
        delay_s = max(0.1, (due_local - now_local).total_seconds())
        due_monotonic = time.monotonic() + delay_s
        job_id = f"security_presence_simulation:{self._reaction_id}:{next_event['event_id']}"
        return {
            job_id: ScheduledRuntimeJob(
                job_id=job_id,
                owner="VacationPresenceSimulationReaction",
                entry_id=entry_id,
                due_monotonic=due_monotonic,
                label=f"security: vacation presence ~{due_local.strftime('%H:%M')} ({next_event['room_id']})",
            )
        }

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        if self._source_profile_kind != "accepted_lighting_reactions":
            return
        source_reaction_ids, source_rooms, source_profiles = _select_source_profile(
            options=options,
            allowed_rooms=self._allowed_rooms,
            allowed_entities=self._allowed_entities,
        )
        self._source_reaction_ids = source_reaction_ids
        self._source_rooms = source_rooms
        self._source_profiles = source_profiles
        if not self._source_reaction_ids:
            self._last_blocked_reason = "insufficient_learned_evidence"

    def diagnostics(self) -> dict[str, Any]:
        now_local = dt_util.now()
        tonight_plan, _ = self._derive_tonight_plan(now_local)
        next_event = self._next_pending_event(tonight_plan, now_local)
        recent_profiles = self._recent_source_profiles(now_local.date())
        source_trace = self._source_trace(now_local.date())
        selected_trace = [item for item in source_trace if item.get("selected") is True]
        excluded_trace = [item for item in source_trace if item.get("selected") is not True]
        blocked_reason = self._last_blocked_reason
        return {
            "enabled": self._enabled,
            "allowed_rooms": list(self._allowed_rooms),
            "allowed_entities": list(self._allowed_entities),
            "requires_dark_outside": self._requires_dark_outside,
            "simulation_aggressiveness": self._simulation_aggressiveness,
            "min_jitter_override_min": self._min_jitter_override_min,
            "max_jitter_override_min": self._max_jitter_override_min,
            "max_events_per_evening_override": self._max_events_per_evening_override,
            "latest_end_time_override": self._latest_end_time_override,
            "skip_if_presence_detected": self._skip_if_presence_detected,
            "source_profile_kind": self._source_profile_kind,
            "source_profile_ready": bool(self._source_reaction_ids),
            "source_reaction_count": len(self._source_reaction_ids),
            "source_reaction_ids": list(self._source_reaction_ids),
            "source_rooms": list(self._source_rooms),
            "recent_source_reaction_count": len(recent_profiles),
            "recent_source_reaction_ids": [item["reaction_id"] for item in recent_profiles],
            "selected_source_trace": selected_trace[:5],
            "excluded_source_trace": excluded_trace[:5],
            "active_tonight": bool(self._enabled and tonight_plan),
            "operational_state": _operational_state_for_security_presence(
                enabled=self._enabled,
                tonight_plan=tonight_plan,
                blocked_reason=blocked_reason,
            ),
            "tonight_plan_count": len(tonight_plan),
            "tonight_plan_preview": [
                {
                    "source_reaction_id": item["source_reaction_id"],
                    "room_id": item["room_id"],
                    "due_local": item["due_local"].isoformat(),
                    "jitter_min": item.get("jitter_min", 0),
                    "entity_steps": len(item["entity_steps"]),
                    "selection_reason": item.get("selection_reason"),
                    "source_score": item.get("source_score"),
                }
                for item in tonight_plan
            ],
            "next_planned_activation": next_event["due_local"].isoformat() if next_event else None,
            "last_simulated_activation": self._last_simulated_activation,
            "fire_count": self._fire_count,
            "last_fired_ts": self._last_fired_ts,
            "blocked_reason": blocked_reason,
        }

    def reset_learning_state(self) -> None:
        self._fired_event_ids_by_date = {}
        self._last_blocked_reason = (
            "insufficient_learned_evidence"
            if not self._source_reaction_ids
            else "waiting_for_snapshot"
        )
        self._fire_count = 0
        self._last_fired_ts = None
        self._last_simulated_activation = None

    def _derive_tonight_plan(
        self,
        now_local: datetime,
    ) -> tuple[list[dict[str, Any]], str]:
        if not self._source_profiles:
            return [], "insufficient_learned_evidence"

        dark_anchor = self._dark_anchor_local(now_local)
        if dark_anchor is None:
            return [], "sun_unavailable"

        source_candidates = self._candidate_sources_for_tonight(now_local.date())
        if not source_candidates:
            return [], "no_suitable_recent_sources"
        if not self._has_sufficient_source_strength(source_candidates, now_local.date()):
            return [], "insufficient_source_strength"

        budget = self._event_budget(source_candidates)
        selected, selection_reasons = self._select_plan_sources(source_candidates, budget)
        if not selected:
            return [], "insufficient_source_strength"
        first_min = int(selected[0]["scheduled_min"])
        start_offset_min = self._bootstrap_dark_start_offset_min()
        anchor = dark_anchor + timedelta(minutes=start_offset_min)
        latest_end = self._latest_end_local(now_local.date())

        plan: list[dict[str, Any]] = []
        for index, profile in enumerate(selected):
            delta_min = int(profile["scheduled_min"]) - first_min
            jitter_min = self._event_jitter_min(now_local.date(), index, profile["reaction_id"])
            due_local = anchor + timedelta(minutes=delta_min + jitter_min)
            if plan:
                min_due = plan[-1]["due_local"] + timedelta(minutes=self._minimum_event_gap_min())
                if due_local < min_due:
                    due_local = min_due
            if latest_end is not None and due_local > latest_end:
                continue
            event_id = f"{now_local.date().isoformat()}:{index}:{profile['reaction_id']}"
            plan.append(
                {
                    "event_id": event_id,
                    "source_reaction_id": profile["reaction_id"],
                    "room_id": profile["room_id"],
                    "entity_steps": list(profile["entity_steps"]),
                    "due_local": due_local,
                    "jitter_min": jitter_min,
                    "selection_reason": selection_reasons.get(profile["reaction_id"], ""),
                    "source_score": float(profile.get("score") or 0.0),
                }
            )
        if not plan:
            return [], "plan_empty_after_guardrails"
        return plan, ""

    def _select_plan_sources(
        self,
        source_candidates: list[dict[str, Any]],
        budget: int,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if budget <= 0 or not source_candidates:
            return [], {}

        selected: list[dict[str, Any]] = []
        selection_reasons: dict[str, str] = {}
        remaining = list(source_candidates)
        first = remaining.pop(0)
        selected.append(first)
        selection_reasons[str(first.get("reaction_id") or "")] = "top_ranked_seed"

        while remaining and len(selected) < budget:
            same_weekday_available = any(
                bool(item.get("same_weekday") is True) for item in remaining
            )
            best_index: int | None = None
            best_key: tuple[object, ...] | None = None
            best_reason = "ranked_fill"
            for index, item in enumerate(remaining):
                room_id = str(item.get("room_id") or "").strip()
                room_closeout_score = self._room_closeout_score(item, selected)
                sequence_coherence_score = self._sequence_coherence_score(item, selected)
                evening_shape_score = self._evening_shape_score(item, selected)
                temporal_companion_score = self._temporal_companion_score(item, selected)
                progresses_evening = int(item.get("scheduled_min") or 0) > max(
                    int(chosen.get("scheduled_min") or 0) for chosen in selected
                )
                backward_same_weekday_penalty = (
                    1 if bool(item.get("same_weekday") is True) and not progresses_evening else 0
                )
                same_weekday_progressive = (
                    1 if bool(item.get("same_weekday") is True) and progresses_evening else 0
                )
                same_weekday_companion = (
                    1
                    if (
                        same_weekday_available
                        and bool(selected[0].get("same_weekday") is True)
                        and bool(item.get("same_weekday") is True)
                        and progresses_evening
                    )
                    else 0
                )
                selected_rooms = {str(chosen.get("room_id") or "").strip() for chosen in selected}
                room_bonus = 1 if room_id and room_id not in selected_rooms else 0
                spread_min = _closest_scheduled_gap_min(item, selected)
                spread_bucket = min(spread_min, 240)
                reason = "ranked_fill"
                if room_closeout_score >= 3:
                    reason = "room_closeout_duration_preferred"
                elif sequence_coherence_score >= 2:
                    reason = "sequence_coherence_preferred"
                elif evening_shape_score >= 2:
                    reason = "evening_shape_preferred"
                elif same_weekday_companion:
                    reason = "same_weekday_companion_preferred"
                elif temporal_companion_score >= 2:
                    reason = "temporal_companion_preferred"
                elif room_closeout_score > 0:
                    reason = "room_closeout_preferred"
                elif room_bonus:
                    reason = "room_diversity_preferred"
                elif spread_bucket >= 45:
                    reason = "temporal_spread_preferred"
                key = (
                    room_closeout_score,
                    evening_shape_score,
                    sequence_coherence_score,
                    same_weekday_companion,
                    temporal_companion_score,
                    same_weekday_progressive,
                    -backward_same_weekday_penalty,
                    room_bonus,
                    spread_bucket,
                    -abs(self._preferred_closeout_delta_penalty(item, selected)),
                    -abs(self._preferred_evening_shape_penalty(item, selected)),
                    -abs(self._preferred_sequence_coherence_penalty(item, selected)),
                    -abs(self._preferred_temporal_companion_penalty(item, selected)),
                    float(item.get("score") or 0.0),
                    str(item.get("reaction_id") or ""),
                )
                if best_key is None or key > best_key:
                    best_key = key
                    best_index = index
                    best_reason = reason
            assert best_index is not None
            chosen = remaining.pop(best_index)
            selected.append(chosen)
            selection_reasons[str(chosen.get("reaction_id") or "")] = best_reason

        ordered = sorted(
            selected,
            key=lambda item: (
                int(item["scheduled_min"]),
                -float(item.get("score") or 0.0),
                item["reaction_id"],
            ),
        )
        return ordered, selection_reasons

    def _room_closeout_score(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        room_id = str(candidate.get("room_id") or "").strip()
        if not room_id or str(candidate.get("action_kind") or "") != "off":
            return 0

        selected_same_room = [
            item for item in selected if str(item.get("room_id") or "").strip() == room_id
        ]
        if not selected_same_room:
            return 0

        has_on = any(str(item.get("action_kind") or "") == "on" for item in selected_same_room)
        has_off = any(str(item.get("action_kind") or "") == "off" for item in selected_same_room)
        if not has_on or has_off:
            return 0

        candidate_min = int(candidate.get("scheduled_min") or 0)
        latest_selected_min = max(
            int(item.get("scheduled_min") or 0) for item in selected_same_room
        )
        if candidate_min < latest_selected_min:
            return 0

        dwell_min = candidate_min - latest_selected_min
        target = self._room_closeout_target_min(candidate, selected)
        if dwell_min < _ROOM_CLOSEOUT_PREFERRED_MIN:
            return 1
        if abs(dwell_min - target) <= 20:
            return 4
        if dwell_min <= _ROOM_CLOSEOUT_SOFT_MAX_MIN:
            return 3
        if dwell_min <= _ROOM_CLOSEOUT_HARD_MAX_MIN:
            return 2
        return 1

    def _preferred_closeout_delta_penalty(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        room_id = str(candidate.get("room_id") or "").strip()
        if not room_id or str(candidate.get("action_kind") or "") != "off":
            return 9999

        selected_same_room = [
            item
            for item in selected
            if str(item.get("room_id") or "").strip() == room_id
            and str(item.get("action_kind") or "") == "on"
        ]
        if not selected_same_room:
            return 9999

        latest_on_min = max(int(item.get("scheduled_min") or 0) for item in selected_same_room)
        dwell_min = int(candidate.get("scheduled_min") or 0) - latest_on_min
        if dwell_min < 0:
            return 9999
        target = self._room_closeout_target_min(candidate, selected)
        return abs(dwell_min - target)

    def _room_closeout_target_min(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        observed = self._observed_room_dwell_target_min(candidate, selected)
        if observed is not None:
            return observed
        return (_ROOM_CLOSEOUT_PREFERRED_MIN + _ROOM_CLOSEOUT_SOFT_MAX_MIN) // 2

    def _observed_room_dwell_target_min(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int | None:
        room_id = str(candidate.get("room_id") or "").strip()
        if not room_id or str(candidate.get("action_kind") or "") != "off":
            return None
        selected_weekdays = {
            int(item.get("weekday") or 0)
            for item in selected
            if str(item.get("room_id") or "").strip() == room_id
        }
        by_room = [
            item
            for item in self._source_profiles
            if str(item.get("room_id") or "").strip() == room_id
        ]
        preferred_weekdays = [
            item for item in by_room if int(item.get("weekday") or 0) in selected_weekdays
        ]
        samples = self._room_dwell_samples(preferred_weekdays)
        if not samples:
            samples = self._room_dwell_samples(by_room)
        if not samples:
            return None
        return int(round(float(median(samples))))

    def _room_dwell_samples(self, profiles: list[dict[str, Any]]) -> list[int]:
        if not profiles:
            return []
        grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for item in profiles:
            observed_at = _parse_dt_local(item.get("updated_at")) or _parse_dt_local(
                item.get("created_at")
            )
            observation_key = (
                observed_at.date().isoformat() if observed_at is not None else "unknown"
            )
            group_key = (observation_key, int(item.get("weekday") or 0))
            grouped.setdefault(group_key, []).append(item)
        samples: list[int] = []
        for group_key in sorted(grouped):
            ordered = sorted(
                grouped[group_key],
                key=lambda item: (
                    int(item.get("scheduled_min") or 0),
                    str(item.get("reaction_id") or ""),
                ),
            )
            latest_on: int | None = None
            for item in ordered:
                action_kind = str(item.get("action_kind") or "")
                scheduled_min = int(item.get("scheduled_min") or 0)
                if action_kind == "on":
                    latest_on = scheduled_min
                elif action_kind == "off":
                    if latest_on is None or scheduled_min <= latest_on:
                        continue
                    dwell = scheduled_min - latest_on
                    if _ROOM_CLOSEOUT_PREFERRED_MIN <= dwell <= _ROOM_CLOSEOUT_HARD_MAX_MIN:
                        samples.append(dwell)
        return samples

    def _temporal_companion_score(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        if not selected or not bool(candidate.get("same_weekday") is True):
            return 0
        if not bool(selected[0].get("same_weekday") is True):
            return 0
        candidate_min = int(candidate.get("scheduled_min") or 0)
        seed_min = int(selected[0].get("scheduled_min") or 0)
        if candidate_min <= seed_min:
            return 0
        delta_min = candidate_min - seed_min
        if delta_min < _TEMPORAL_COMPANION_PREFERRED_MIN:
            return 1
        if delta_min <= _TEMPORAL_COMPANION_SOFT_MAX_MIN:
            return 3
        return 1

    def _sequence_coherence_score(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        if not selected or not bool(candidate.get("same_weekday") is True):
            return 0
        seed = selected[0]
        if not bool(seed.get("same_weekday") is True):
            return 0
        latest_selected_min = max(int(item.get("scheduled_min") or 0) for item in selected)
        candidate_min = int(candidate.get("scheduled_min") or 0)
        if candidate_min <= latest_selected_min:
            return 0
        delta_min = candidate_min - latest_selected_min
        if delta_min < _SEQUENCE_COMPANION_PREFERRED_MIN:
            return 1
        if delta_min <= _SEQUENCE_COMPANION_SOFT_MAX_MIN:
            return 3
        return 1

    def _preferred_sequence_coherence_penalty(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        if not selected or bool(candidate.get("same_weekday") is True) is False:
            return 9999
        seed = selected[0]
        if bool(seed.get("same_weekday") is True) is False:
            return 9999
        latest_selected_min = max(int(item.get("scheduled_min") or 0) for item in selected)
        candidate_min = int(candidate.get("scheduled_min") or 0)
        delta_min = candidate_min - latest_selected_min
        if delta_min < 0:
            return 9999
        target = (_SEQUENCE_COMPANION_PREFERRED_MIN + _SEQUENCE_COMPANION_SOFT_MAX_MIN) // 2
        return abs(delta_min - target)

    def _evening_shape_score(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        target = self._observed_evening_shape_span_target_min(selected)
        if target is None or not selected:
            return 0
        projected = self._projected_evening_span_min(candidate, selected)
        if projected is None:
            return 0
        delta = abs(projected - target)
        if delta <= _EVENING_SHAPE_SPAN_TOLERANCE_MIN:
            return 3
        if delta <= _EVENING_SHAPE_SPAN_SOFT_TOLERANCE_MIN:
            return 2
        return 1

    def _preferred_evening_shape_penalty(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        target = self._observed_evening_shape_span_target_min(selected)
        projected = self._projected_evening_span_min(candidate, selected)
        if target is None or projected is None:
            return 9999
        return abs(projected - target)

    def _projected_evening_span_min(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int | None:
        if not selected:
            return None
        mins = [int(item.get("scheduled_min") or 0) for item in selected]
        mins.append(int(candidate.get("scheduled_min") or 0))
        return max(mins) - min(mins)

    def _observed_evening_shape_span_target_min(
        self,
        selected: list[dict[str, Any]],
    ) -> int | None:
        if not selected:
            return None
        seed = selected[0]
        if bool(seed.get("same_weekday") is True) is False:
            return None
        target_weekday = int(seed.get("weekday") or 0)
        samples = self._evening_shape_span_samples(target_weekday)
        if not samples:
            return None
        return int(round(float(median(samples))))

    def _evening_shape_span_samples(self, weekday: int) -> list[int]:
        grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for item in self._source_profiles:
            if int(item.get("weekday") or 0) != weekday:
                continue
            observed_at = _parse_dt_local(item.get("updated_at")) or _parse_dt_local(
                item.get("created_at")
            )
            observation_key = (
                observed_at.date().isoformat() if observed_at is not None else "unknown"
            )
            group_key = (observation_key, weekday)
            grouped.setdefault(group_key, []).append(item)
        samples: list[int] = []
        for group_key in sorted(grouped):
            scheduled = sorted(int(item.get("scheduled_min") or 0) for item in grouped[group_key])
            if len(scheduled) < 2:
                continue
            samples.append(max(scheduled) - min(scheduled))
        return samples

    def _preferred_temporal_companion_penalty(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
    ) -> int:
        if not selected:
            return 9999
        if bool(candidate.get("same_weekday") is True) is False:
            return 9999
        if bool(selected[0].get("same_weekday") is True) is False:
            return 9999
        candidate_min = int(candidate.get("scheduled_min") or 0)
        seed_min = int(selected[0].get("scheduled_min") or 0)
        delta_min = candidate_min - seed_min
        if delta_min < 0:
            return 9999
        target = (_TEMPORAL_COMPANION_PREFERRED_MIN + _TEMPORAL_COMPANION_SOFT_MAX_MIN) // 2
        return abs(delta_min - target)

    def _candidate_sources_for_tonight(self, today: date) -> list[dict[str, Any]]:
        recent_profiles = self._recent_source_profiles(today)
        if not recent_profiles:
            return []
        weekday = today.weekday()
        candidates: list[dict[str, Any]] = []
        for item in recent_profiles:
            scheduled_min = int(item["scheduled_min"])
            if scheduled_min < 16 * 60 or scheduled_min > _LATE_OUTLIER_HARD_LIMIT_MIN:
                continue
            age_days = _age_days(item, today)
            same_weekday = int(item["weekday"]) == weekday
            late_penalty = 0.0
            if scheduled_min > _LATE_OUTLIER_SOFT_LIMIT_MIN:
                late_penalty = float(scheduled_min - _LATE_OUTLIER_SOFT_LIMIT_MIN) * 2.0
            weekday_bonus = 120.0 if same_weekday else 0.0
            recency_score = max(0.0, float(_SOURCE_PROFILE_MAX_AGE_DAYS - age_days))
            score = weekday_bonus + recency_score - late_penalty
            candidate = dict(item)
            candidate["same_weekday"] = same_weekday
            candidate["age_days"] = age_days
            candidate["score"] = score
            candidates.append(candidate)

        return sorted(
            candidates,
            key=lambda item: (
                -float(item.get("score") or 0.0),
                int(item["scheduled_min"]),
                str(item["reaction_id"]),
            ),
        )

    def _recent_source_profiles(self, today: date) -> list[dict[str, Any]]:
        return [
            item
            for item in self._source_profiles
            if _age_days(item, today) <= _SOURCE_PROFILE_MAX_AGE_DAYS
        ]

    def _bootstrap_dark_start_offset_min(self) -> int:
        if self._simulation_aggressiveness == "low":
            return 35
        if self._simulation_aggressiveness == "high":
            return 10
        return 20

    def _event_budget(self, source_candidates: list[dict[str, Any]]) -> int:
        if self._max_events_per_evening_override is not None:
            desired = max(1, self._max_events_per_evening_override)
        elif self._simulation_aggressiveness == "low":
            desired = 1
        elif self._simulation_aggressiveness == "high":
            desired = 3
        else:
            desired = 2

        if not source_candidates:
            return 0

        unique_rooms = {
            str(item.get("room_id") or "").strip()
            for item in source_candidates
            if str(item.get("room_id") or "").strip()
        }
        candidate_count = len(source_candidates)
        if candidate_count == 1:
            return 1
        if len(unique_rooms) >= 2:
            return min(desired, candidate_count)
        return min(desired, min(candidate_count, 2))

    def _has_sufficient_source_strength(
        self,
        source_candidates: list[dict[str, Any]],
        today: date,
    ) -> bool:
        if not source_candidates:
            return False
        if len(source_candidates) >= 2:
            return True
        candidate = source_candidates[0]
        age_days = int(candidate.get("age_days") or _age_days(candidate, today))
        same_weekday = bool(candidate.get("same_weekday") is True)
        return same_weekday and age_days <= _SOURCE_PROFILE_PREFERRED_AGE_DAYS

    def _source_trace(self, today: date) -> list[dict[str, Any]]:
        recent_ids = {item["reaction_id"] for item in self._recent_source_profiles(today)}
        candidates = self._candidate_sources_for_tonight(today)
        candidate_map = {item["reaction_id"]: item for item in candidates}
        budget = self._event_budget(candidates)
        selected, selection_reasons = self._select_plan_sources(candidates, budget)
        selected_ids = {item["reaction_id"] for item in selected}

        trace: list[dict[str, Any]] = []
        for item in self._source_profiles:
            reaction_id = str(item.get("reaction_id") or "")
            scheduled_min = int(item.get("scheduled_min") or 0)
            row = {
                "reaction_id": reaction_id,
                "room_id": str(item.get("room_id") or "").strip(),
                "scheduled_min": scheduled_min,
                "weekday": int(item.get("weekday") or 0),
                "action_kind": str(item.get("action_kind") or ""),
                "recent": reaction_id in recent_ids,
                "candidate": reaction_id in candidate_map,
                "selected": reaction_id in selected_ids,
                "score": float(candidate_map.get(reaction_id, {}).get("score") or 0.0),
                "selection_reason": selection_reasons.get(reaction_id, ""),
                "exclusion_reason": "",
            }
            if reaction_id in selected_ids:
                row["exclusion_reason"] = ""
            elif reaction_id in candidate_map:
                row["exclusion_reason"] = "not_selected_within_budget"
            elif reaction_id not in recent_ids:
                row["exclusion_reason"] = "too_old"
            elif scheduled_min < 16 * 60:
                row["exclusion_reason"] = "outside_evening_window"
            elif scheduled_min > _LATE_OUTLIER_HARD_LIMIT_MIN:
                row["exclusion_reason"] = "late_outlier"
            else:
                row["exclusion_reason"] = "candidate_filtered"
            trace.append(row)

        return sorted(
            trace,
            key=lambda item: (
                0 if item["selected"] else 1,
                0 if item["candidate"] else 1,
                -float(item["score"]),
                int(item["scheduled_min"]),
                item["reaction_id"],
            ),
        )

    def _minimum_event_gap_min(self) -> int:
        return _MIN_EVENT_GAP_MIN

    def _event_jitter_min(self, today: date, index: int, source_reaction_id: str) -> int:
        if index == 0:
            return 0
        min_jitter, max_jitter = self._jitter_bounds_min()
        if max_jitter <= 0:
            return 0
        if min_jitter > max_jitter:
            min_jitter, max_jitter = max_jitter, min_jitter
        spread = max_jitter - min_jitter
        if spread <= 0:
            magnitude = max_jitter
        else:
            seed = f"{today.isoformat()}|{self._reaction_id}|{source_reaction_id}|{index}"
            digest = hashlib.sha256(seed.encode("utf-8")).digest()
            magnitude = min_jitter + (int.from_bytes(digest[:2], "big") % (spread + 1))

        sign_seed = f"{today.isoformat()}|sign|{self._reaction_id}|{source_reaction_id}|{index}"
        sign_digest = hashlib.sha256(sign_seed.encode("utf-8")).digest()
        sign = 1 if sign_digest[0] % 2 == 0 else -1
        return sign * magnitude

    def _jitter_bounds_min(self) -> tuple[int, int]:
        min_jitter = self._min_jitter_override_min
        max_jitter = self._max_jitter_override_min
        if min_jitter is None or max_jitter is None:
            if self._simulation_aggressiveness == "low":
                return 2, 4
            if self._simulation_aggressiveness == "high":
                return 5, 12
            return 3, 8
        return max(0, min_jitter), max(0, max_jitter)

    def _latest_end_local(self, today: date) -> datetime | None:
        if not self._latest_end_time_override:
            return None
        try:
            hh, mm = [int(part) for part in self._latest_end_time_override.split(":", 1)]
        except (TypeError, ValueError):
            return None
        return dt_util.now().replace(
            year=today.year,
            month=today.month,
            day=today.day,
            hour=hh,
            minute=mm,
            second=0,
            microsecond=0,
        )

    def _is_dark_outside(self) -> tuple[bool, str]:
        sun_state = self._hass.states.get("sun.sun") if self._hass is not None else None
        if sun_state is None:
            return False, "sun_unavailable"
        state = str(getattr(sun_state, "state", "") or "").strip()
        if state == "below_horizon":
            return True, ""
        return False, "outside_not_dark"

    def _dark_anchor_local(self, now_local: datetime) -> datetime | None:
        sun_state = self._hass.states.get("sun.sun") if self._hass is not None else None
        if sun_state is None:
            return None
        raw_state = str(getattr(sun_state, "state", "") or "").strip()
        attrs = getattr(sun_state, "attributes", {}) or {}

        last_setting = _parse_dt_local(attrs.get("last_setting"))
        if last_setting is not None and last_setting.date() == now_local.date():
            return last_setting

        next_setting = _parse_dt_local(attrs.get("next_setting"))
        if next_setting is not None and next_setting.date() == now_local.date():
            return next_setting

        # HA can expose only ``next_setting`` after sunset. In that case, derive
        # the dark anchor for "tonight" from tomorrow's next setting.
        if raw_state == "below_horizon" and next_setting is not None:
            derived = next_setting - timedelta(days=1)
            if derived.date() == now_local.date():
                return derived

        next_dusk = _parse_dt_local(attrs.get("next_dusk"))
        if next_dusk is not None and next_dusk.date() == now_local.date():
            return next_dusk
        if raw_state == "below_horizon" and next_dusk is not None:
            derived = next_dusk - timedelta(days=1)
            if derived.date() == now_local.date():
                return derived

        return None

    def _current_house_state(self) -> str:
        state = (
            self._hass.states.get("sensor.heima_house_state") if self._hass is not None else None
        )
        return str(getattr(state, "state", "") or "").strip()

    def _current_anyone_home(self) -> bool:
        state = (
            self._hass.states.get("binary_sensor.heima_anyone_home")
            if self._hass is not None
            else None
        )
        raw = str(getattr(state, "state", "") or "").strip().lower()
        return raw == "on"

    def _next_pending_event(
        self,
        tonight_plan: list[dict[str, Any]],
        now_local: datetime,
    ) -> dict[str, Any] | None:
        fired = self._fired_event_ids(now_local.date())
        recovery_limit = now_local - timedelta(seconds=_SOURCE_EVENT_RECOVERY_WINDOW_S)
        for event in tonight_plan:
            if event["event_id"] in fired:
                continue
            if event["due_local"] >= recovery_limit:
                return event
        return None

    def _current_due_event(
        self,
        tonight_plan: list[dict[str, Any]],
        now_local: datetime,
    ) -> dict[str, Any] | None:
        fired = self._fired_event_ids(now_local.date())
        latest_due = now_local
        earliest_due = now_local - timedelta(seconds=_SOURCE_EVENT_RECOVERY_WINDOW_S)
        for event in tonight_plan:
            if event["event_id"] in fired:
                continue
            if earliest_due <= event["due_local"] <= latest_due:
                return event
        return None

    def _build_steps_from_event(self, event: dict[str, Any]) -> list[ApplyStep]:
        steps: list[ApplyStep] = []
        for raw in event["entity_steps"]:
            cfg = dict(raw) if isinstance(raw, dict) else {}
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
                        target=str(event["room_id"]),
                        action="light.turn_on",
                        params=params,
                        reason=f"security_presence_simulation:{self._reaction_id}:{event['source_reaction_id']}",
                    )
                )
            else:
                steps.append(
                    ApplyStep(
                        domain="lighting",
                        target=str(event["room_id"]),
                        action="light.turn_off",
                        params={"entity_id": entity_id},
                        reason=f"security_presence_simulation:{self._reaction_id}:{event['source_reaction_id']}",
                    )
                )
        return steps

    def _fired_event_ids(self, day: date) -> set[str]:
        return self._fired_event_ids_by_date.setdefault(day.isoformat(), set())

    def _mark_event_fired(self, event_id: str, day: date) -> None:
        self._fired_event_ids(day).add(event_id)


def build_vacation_presence_simulation_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> VacationPresenceSimulationReaction | None:
    """Build the persisted policy reaction for the security family."""
    try:
        enabled = bool(cfg.get("enabled", True))
        allowed_rooms = [
            str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()
        ]
        allowed_entities = [
            str(item).strip() for item in cfg.get("allowed_entities", []) or [] if str(item).strip()
        ]
        requires_dark_outside = bool(cfg.get("requires_dark_outside", True))
        simulation_aggressiveness = str(
            cfg.get("simulation_aggressiveness", "medium") or "medium"
        ).strip()
        if simulation_aggressiveness not in {"low", "medium", "high"}:
            simulation_aggressiveness = "medium"
        min_jitter_override_min = _optional_int(cfg.get("min_jitter_override_min"))
        max_jitter_override_min = _optional_int(cfg.get("max_jitter_override_min"))
        max_events_per_evening_override = _optional_int(cfg.get("max_events_per_evening_override"))
        latest_end_time_override = str(cfg.get("latest_end_time_override") or "").strip() or None
        skip_if_presence_detected = bool(cfg.get("skip_if_presence_detected", True))
        source_reaction_ids, source_rooms, source_profiles = _select_source_profile_from_config(cfg)
        source_profile_kind = "learned_source_profiles"
        if not source_reaction_ids:
            source_reaction_ids, source_rooms, source_profiles = _select_source_profile(
                options=dict(getattr(engine, "_entry").options),  # noqa: SLF001
                allowed_rooms=allowed_rooms,
                allowed_entities=allowed_entities,
            )
            source_profile_kind = "accepted_lighting_reactions"
    except Exception:
        return None
    return VacationPresenceSimulationReaction(
        reaction_id=proposal_id,
        enabled=enabled,
        allowed_rooms=allowed_rooms,
        allowed_entities=allowed_entities,
        requires_dark_outside=requires_dark_outside,
        simulation_aggressiveness=simulation_aggressiveness,
        min_jitter_override_min=min_jitter_override_min,
        max_jitter_override_min=max_jitter_override_min,
        max_events_per_evening_override=max_events_per_evening_override,
        latest_end_time_override=latest_end_time_override,
        skip_if_presence_detected=skip_if_presence_detected,
        source_profile_kind=source_profile_kind,
        source_reaction_ids=source_reaction_ids,
        source_rooms=source_rooms,
        source_profiles=source_profiles,
        hass=getattr(engine, "_hass", None),  # noqa: SLF001
    )


def present_vacation_presence_simulation_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    scope = ", ".join(
        str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()
    )
    if scope:
        return f"Simulazione presenza (vacanza) · {scope}"
    return "Simulazione presenza (vacanza)"


def present_admin_authored_vacation_presence_simulation_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    details = ["Tipo: policy dinamica security-driven"]
    rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
    entities = [
        str(item).strip() for item in cfg.get("allowed_entities", []) or [] if str(item).strip()
    ]
    if rooms:
        details.append(f"Stanze consentite: {', '.join(rooms)}")
    if entities:
        details.append(f"Entità consentite: {', '.join(entities)}")
    details.append("Profilo di esecuzione: derivato da automazioni luce accettate di recente")
    if bool(cfg.get("requires_dark_outside", True)):
        details.append("Buio richiesto: sì")
    if bool(cfg.get("skip_if_presence_detected", True)):
        details.append("Stop su presenza: sì")
    return details


def present_learned_vacation_presence_simulation_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    diagnostics = dict(cfg.get("learning_diagnostics", {}) or {})
    is_it = language.startswith("it")
    details = ["Tipo: policy dinamica appresa" if is_it else "Type: learned dynamic policy"]
    rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
    if rooms:
        details.append(
            f"Stanze apprese: {', '.join(rooms)}" if is_it else f"Learned rooms: {', '.join(rooms)}"
        )
    source_profile_count = diagnostics.get("source_profile_count")
    if isinstance(source_profile_count, int):
        details.append(
            f"Profili sorgente: {source_profile_count}"
            if is_it
            else f"Source profiles: {source_profile_count}"
        )
    weekdays = diagnostics.get("weekdays")
    if isinstance(weekdays, list) and weekdays:
        labels = [
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][int(item) % 7] for item in weekdays
        ]
        details.append(
            f"Giorni coperti: {', '.join(labels)}"
            if is_it
            else f"Covered weekdays: {', '.join(labels)}"
        )
    details.append(
        "Profilo di esecuzione: derivato dallo storico luci utente (escluso vacanza)"
        if is_it
        else "Execution profile: derived from non-vacation user lighting history"
    )
    return details


def present_vacation_presence_simulation_proposal_label(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> str | None:
    rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
    if rooms:
        scope = ", ".join(rooms[:2])
        if len(rooms) > 2:
            scope = f"{scope}, +{len(rooms) - 2}"
        return (
            f"Presenza (vacanza) · {scope}"
            if language.startswith("it")
            else f"Vacation presence · {scope}"
        )
    return (
        "Simulazione presenza (vacanza)"
        if language.startswith("it")
        else "Vacation presence simulation"
    )


def present_vacation_presence_simulation_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_followup: bool,
) -> str | None:
    base = present_vacation_presence_simulation_proposal_label(flow, proposal, cfg, language)
    if not base:
        return (
            "Simulazione presenza durante la vacanza"
            if language.startswith("it")
            else "Vacation presence simulation"
        )
    if getattr(proposal, "origin", "") == "admin_authored":
        return (
            "Simulazione presenza durante la vacanza"
            if language.startswith("it")
            else "Vacation presence simulation"
        )
    if language.startswith("it"):
        if is_followup:
            return f"Affinamento simulazione presenza: {base}"
        return f"Nuova simulazione presenza: {base}"
    if is_followup:
        return f"Presence simulation tuning: {base}"
    return f"New presence simulation: {base}"


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _select_source_profile(
    *,
    options: dict[str, Any],
    allowed_rooms: list[str],
    allowed_entities: list[str],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    configured = dict(options.get("reactions", {}).get("configured", {}) or {})
    room_filter = {str(item).strip() for item in allowed_rooms if str(item).strip()}
    entity_filter = {str(item).strip() for item in allowed_entities if str(item).strip()}

    candidates: list[tuple[tuple[float, float, str], dict[str, Any]]] = []
    for reaction_id, raw in configured.items():
        cfg = dict(raw) if isinstance(raw, dict) else {}
        if not _is_lighting_source_candidate(cfg):
            continue
        room_id = str(cfg.get("room_id") or "").strip()
        if room_filter and room_id not in room_filter:
            continue
        if entity_filter and not _matches_allowed_entities(cfg, entity_filter):
            continue
        candidates.append(
            (
                (
                    -_ts_score(cfg.get("updated_at")),
                    -_ts_score(cfg.get("created_at")),
                    str(reaction_id),
                ),
                {
                    "reaction_id": str(reaction_id),
                    "room_id": room_id,
                    "weekday": int(cfg.get("weekday", 0)),
                    "scheduled_min": int(cfg.get("scheduled_min", 0)),
                    "entity_steps": list(cfg.get("entity_steps", []) or []),
                    "action_kind": _event_action_kind(list(cfg.get("entity_steps", []) or [])),
                    "created_at": cfg.get("created_at"),
                    "updated_at": cfg.get("updated_at"),
                },
            )
        )

    candidates.sort(key=lambda item: item[0])
    source_profiles = [payload for _, payload in candidates]
    source_ids = [payload["reaction_id"] for payload in source_profiles]
    source_rooms = sorted({payload["room_id"] for payload in source_profiles if payload["room_id"]})
    return source_ids, source_rooms, source_profiles


def _select_source_profile_from_config(
    cfg: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    items = cfg.get("learned_source_profiles")
    if not isinstance(items, list):
        return [], [], []

    source_profiles: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        room_id = str(raw.get("room_id") or "").strip()
        reaction_id = str(raw.get("reaction_id") or "").strip()
        entity_steps = list(raw.get("entity_steps", []) or [])
        action_kind = str(raw.get("action_kind") or _event_action_kind(entity_steps)).strip()
        if not room_id or not reaction_id or not entity_steps or action_kind not in {"on", "off"}:
            continue
        source_profiles.append(
            {
                "reaction_id": reaction_id,
                "room_id": room_id,
                "weekday": int(raw.get("weekday", 0)),
                "scheduled_min": int(raw.get("scheduled_min", 0)),
                "entity_steps": entity_steps,
                "action_kind": action_kind,
                "created_at": raw.get("created_at"),
                "updated_at": raw.get("updated_at"),
            }
        )

    source_ids = [item["reaction_id"] for item in source_profiles]
    source_rooms = sorted({item["room_id"] for item in source_profiles if item["room_id"]})
    return source_ids, source_rooms, source_profiles


def _is_lighting_source_candidate(cfg: dict[str, Any]) -> bool:
    reaction_type = resolve_reaction_type(cfg)
    template_id = str(cfg.get("source_template_id") or "").strip()
    if reaction_type != "lighting_scene_schedule":
        return False
    if template_id and template_id != "lighting.scene_schedule.basic":
        return False
    room_id = str(cfg.get("room_id") or "").strip()
    entity_steps = cfg.get("entity_steps")
    return bool(room_id and isinstance(entity_steps, list) and entity_steps)


def _matches_allowed_entities(cfg: dict[str, Any], allowed_entities: set[str]) -> bool:
    for raw in cfg.get("entity_steps", []) or []:
        if not isinstance(raw, dict):
            continue
        entity_id = str(raw.get("entity_id") or "").strip()
        if entity_id and entity_id in allowed_entities:
            return True
    return False


def _closest_scheduled_gap_min(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> int:
    scheduled_min = int(candidate.get("scheduled_min") or 0)
    if not selected:
        return 24 * 60
    gaps = [abs(scheduled_min - int(item.get("scheduled_min") or 0)) for item in selected]
    return min(gaps) if gaps else 24 * 60


def _event_action_kind(entity_steps: list[dict[str, Any]]) -> str:
    actions = {
        str(step.get("action") or "").strip()
        for step in entity_steps
        if isinstance(step, dict) and str(step.get("action") or "").strip()
    }
    if actions == {"on"}:
        return "on"
    if actions == {"off"}:
        return "off"
    return "mixed"


def _ts_score(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return (
            datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
        )
    except ValueError:
        return 0.0


def _parse_dt_local(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = dt_util.parse_datetime(text)
    if parsed is None:
        return None
    return dt_util.as_local(parsed)


def _age_days(profile: dict[str, Any], today: date) -> int:
    updated = _parse_dt_local(profile.get("updated_at"))
    created = _parse_dt_local(profile.get("created_at"))
    reference = updated or created
    if reference is None:
        return _SOURCE_PROFILE_MAX_AGE_DAYS + 1
    return max(0, (today - reference.date()).days)


def _operational_state_for_security_presence(
    *,
    enabled: bool,
    tonight_plan: list[dict[str, Any]],
    blocked_reason: str,
) -> str:
    reason = str(blocked_reason or "").strip()
    if not enabled or reason == "disabled":
        return "disabled"
    if tonight_plan or reason == "awaiting_next_planned_activation":
        return "ready_tonight"
    if reason == "outside_not_dark":
        return "waiting_for_darkness"
    if reason in {
        "insufficient_learned_evidence",
        "insufficient_source_strength",
        "no_suitable_recent_sources",
    }:
        return "insufficient_evidence"
    if reason in {"waiting_for_snapshot", "sun_unavailable"}:
        return "waiting_for_readiness"
    if reason == "presence_detected":
        return "blocked_for_safety"
    if reason == "not_in_vacation":
        return "blocked_for_context"
    if not reason:
        return "idle"
    return "blocked_other"
