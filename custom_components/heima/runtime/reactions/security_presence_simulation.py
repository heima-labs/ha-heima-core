"""Security-owned vacation presence simulation reaction bootstrap."""

from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.util import dt as dt_util

from ..contracts import ApplyStep
from ..scheduler import ScheduledRuntimeJob
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction

_SOURCE_EVENT_RECOVERY_WINDOW_S = 120
_SOURCE_PROFILE_MAX_AGE_DAYS = 90
_SOURCE_PROFILE_PREFERRED_AGE_DAYS = 45
_MIN_EVENT_GAP_MIN = 18


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
        self._source_reaction_ids = list(source_reaction_ids)
        self._source_rooms = list(source_rooms)
        self._source_profiles = list(source_profiles)
        self._last_blocked_reason = (
            "insufficient_learned_evidence" if not self._source_reaction_ids else "waiting_for_snapshot"
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
            "source_profile_kind": "accepted_lighting_reactions",
            "source_profile_ready": bool(self._source_reaction_ids),
            "source_reaction_count": len(self._source_reaction_ids),
            "source_reaction_ids": list(self._source_reaction_ids),
            "source_rooms": list(self._source_rooms),
            "recent_source_reaction_count": len(recent_profiles),
            "recent_source_reaction_ids": [item["reaction_id"] for item in recent_profiles],
            "active_tonight": bool(self._enabled and tonight_plan),
            "tonight_plan_count": len(tonight_plan),
            "tonight_plan_preview": [
                {
                    "source_reaction_id": item["source_reaction_id"],
                    "room_id": item["room_id"],
                    "due_local": item["due_local"].isoformat(),
                    "jitter_min": item.get("jitter_min", 0),
                    "entity_steps": len(item["entity_steps"]),
                }
                for item in tonight_plan
            ],
            "next_planned_activation": next_event["due_local"].isoformat() if next_event else None,
            "last_simulated_activation": self._last_simulated_activation,
            "fire_count": self._fire_count,
            "last_fired_ts": self._last_fired_ts,
            "blocked_reason": self._last_blocked_reason,
        }

    def reset_learning_state(self) -> None:
        self._fired_event_ids_by_date = {}
        self._last_blocked_reason = (
            "insufficient_learned_evidence" if not self._source_reaction_ids else "waiting_for_snapshot"
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

        budget = self._event_budget()
        selected = self._select_plan_sources(source_candidates, budget)
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
                }
            )
        if not plan:
            return [], "plan_empty_after_guardrails"
        return plan, ""

    def _select_plan_sources(
        self,
        source_candidates: list[dict[str, Any]],
        budget: int,
    ) -> list[dict[str, Any]]:
        if budget <= 0 or not source_candidates:
            return []

        selected: list[dict[str, Any]] = []
        seen_rooms: set[str] = set()

        # First pass: prefer covering distinct rooms when credible alternatives exist.
        for item in source_candidates:
            room_id = str(item.get("room_id") or "").strip()
            if room_id and room_id in seen_rooms:
                continue
            selected.append(item)
            if room_id:
                seen_rooms.add(room_id)
            if len(selected) >= budget:
                return selected

        # Second pass: fill any remaining budget with the next best chronological candidates.
        selected_ids = {str(item.get("reaction_id") or "") for item in selected}
        for item in source_candidates:
            reaction_id = str(item.get("reaction_id") or "")
            if reaction_id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(reaction_id)
            if len(selected) >= budget:
                break

        return selected

    def _candidate_sources_for_tonight(self, today: date) -> list[dict[str, Any]]:
        recent_profiles = self._recent_source_profiles(today)
        if not recent_profiles:
            return []
        weekday = today.weekday()
        preferred_same_weekday = [
            item
            for item in recent_profiles
            if item["weekday"] == weekday and _age_days(item, today) <= _SOURCE_PROFILE_PREFERRED_AGE_DAYS
        ]
        same_weekday = [item for item in recent_profiles if item["weekday"] == weekday]
        pool = preferred_same_weekday or same_weekday or recent_profiles
        evening = [item for item in pool if 16 * 60 <= int(item["scheduled_min"]) <= 23 * 60 + 59]
        selected_pool = evening or pool
        return sorted(
            selected_pool,
            key=lambda item: (int(item["scheduled_min"]), -_ts_score(item.get("updated_at")), item["reaction_id"]),
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

    def _event_budget(self) -> int:
        if self._max_events_per_evening_override is not None:
            return max(1, self._max_events_per_evening_override)
        if self._simulation_aggressiveness == "low":
            return 1
        if self._simulation_aggressiveness == "high":
            return 3
        return 2

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
        attrs = getattr(sun_state, "attributes", {}) or {}

        last_setting = _parse_dt_local(attrs.get("last_setting"))
        if last_setting is not None and last_setting.date() == now_local.date():
            return last_setting

        next_setting = _parse_dt_local(attrs.get("next_setting"))
        if next_setting is not None and next_setting.date() == now_local.date():
            return next_setting

        return None

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
        allowed_rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
        allowed_entities = [str(item).strip() for item in cfg.get("allowed_entities", []) or [] if str(item).strip()]
        requires_dark_outside = bool(cfg.get("requires_dark_outside", True))
        simulation_aggressiveness = str(cfg.get("simulation_aggressiveness", "medium") or "medium").strip()
        if simulation_aggressiveness not in {"low", "medium", "high"}:
            simulation_aggressiveness = "medium"
        min_jitter_override_min = _optional_int(cfg.get("min_jitter_override_min"))
        max_jitter_override_min = _optional_int(cfg.get("max_jitter_override_min"))
        max_events_per_evening_override = _optional_int(cfg.get("max_events_per_evening_override"))
        latest_end_time_override = str(cfg.get("latest_end_time_override") or "").strip() or None
        skip_if_presence_detected = bool(cfg.get("skip_if_presence_detected", True))
        source_reaction_ids, source_rooms, source_profiles = _select_source_profile(
            options=dict(getattr(engine, "_entry").options),  # noqa: SLF001
            allowed_rooms=allowed_rooms,
            allowed_entities=allowed_entities,
        )
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
    scope = ", ".join(str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip())
    if scope:
        return f"Simulazione presenza vacation · {scope}"
    return "Simulazione presenza vacation"


def present_admin_authored_vacation_presence_simulation_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    details = ["Tipo: policy dinamica security-driven"]
    rooms = [str(item).strip() for item in cfg.get("allowed_rooms", []) or [] if str(item).strip()]
    entities = [str(item).strip() for item in cfg.get("allowed_entities", []) or [] if str(item).strip()]
    if rooms:
        details.append(f"Stanze consentite: {', '.join(rooms)}")
    if entities:
        details.append(f"Entità consentite: {', '.join(entities)}")
    details.append(
        "Profilo di esecuzione: derivato da lighting reactions accettate recenti"
    )
    if bool(cfg.get("requires_dark_outside", True)):
        details.append("Buio richiesto: sì")
    if bool(cfg.get("skip_if_presence_detected", True)):
        details.append("Stop su presenza: sì")
    return details


def present_vacation_presence_simulation_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_admin_authored: bool,
) -> str | None:
    return "Simulazione presenza in vacation"


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


def _is_lighting_source_candidate(cfg: dict[str, Any]) -> bool:
    reaction_type = str(cfg.get("reaction_type") or "").strip()
    reaction_class = str(cfg.get("reaction_class") or "").strip()
    template_id = str(cfg.get("source_template_id") or "").strip()
    if reaction_type != "lighting_scene_schedule" and reaction_class != "LightingScheduleReaction":
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


def _ts_score(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
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
