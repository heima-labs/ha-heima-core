"""Admin-authored scheduled routine reaction."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from ..contracts import ApplyStep
from ..scheduler import ScheduledRuntimeJob
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_SUPPORTED_DOMAINS = {"scene", "script", "light", "switch", "input_boolean"}
_ENTITY_ACTIONS = {"turn_on", "turn_off"}
_ROUTINE_KINDS = {"scene", "script", "entity_action"}


class ScheduledRoutineReaction(HeimaReaction):
    """Bounded admin-authored weekday/time routine."""

    def __init__(
        self,
        *,
        weekday: int,
        scheduled_min: int,
        window_half_min: int,
        steps: list[dict[str, Any]],
        house_state_in: list[str] | None = None,
        skip_if_anyone_home: bool = False,
        reaction_id: str | None = None,
    ) -> None:
        self._weekday = weekday
        self._scheduled_min = scheduled_min
        self._window_half_min = window_half_min
        self._steps = [dict(step) for step in steps]
        self._house_state_in = [
            str(v).strip() for v in list(house_state_in or []) if str(v).strip()
        ]
        self._skip_if_anyone_home = bool(skip_if_anyone_home)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._last_fired_date: str | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def scheduled_jobs(self, entry_id: str) -> dict[str, ScheduledRuntimeJob]:
        due_monotonic = self._next_due_monotonic()
        job_id = f"scheduled_routine:{self._reaction_id}"
        return {
            job_id: ScheduledRuntimeJob(
                job_id=job_id,
                owner=self.__class__.__name__,
                entry_id=entry_id,
                due_monotonic=due_monotonic,
                label=f"routine: {_WEEKDAY_NAMES[self._weekday]} ~{_hhmm(self._scheduled_min)}",
            )
        }

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        current = history[-1]
        if self._house_state_in and current.house_state not in self._house_state_in:
            return []
        if self._skip_if_anyone_home and current.anyone_home:
            return []
        now_local = dt_util.now()
        occurrence_date = self._window_occurrence_date(now_local)
        if occurrence_date is None:
            return []
        occurrence_day = occurrence_date.isoformat()
        if self._last_fired_date == occurrence_day:
            return []
        self._last_fired_date = occurrence_day
        return self._build_steps()

    def reset_learning_state(self) -> None:
        self._last_fired_date = None

    def diagnostics(self) -> dict[str, Any]:
        return {
            "weekday": self._weekday,
            "scheduled_min": self._scheduled_min,
            "window_half_min": self._window_half_min,
            "steps": len(self._steps),
            "house_state_in": list(self._house_state_in),
            "skip_if_anyone_home": self._skip_if_anyone_home,
            "last_fired_date": self._last_fired_date,
        }

    def _build_steps(self) -> list[ApplyStep]:
        steps: list[ApplyStep] = []
        for raw_step in self._steps:
            domain = str(raw_step.get("domain") or "").strip()
            action = str(raw_step.get("action") or "").strip()
            target = str(raw_step.get("target") or "").strip()
            params = dict(raw_step.get("params") or {})
            if not domain or not action or not target:
                continue
            steps.append(
                ApplyStep(
                    domain=domain,
                    target=target,
                    action=action,
                    params=params,
                    reason=f"scheduled_routine:{self._reaction_id}",
                )
            )
        return steps

    def _next_due_monotonic(self) -> float:
        now_local = dt_util.now()
        days_ahead = (self._weekday - now_local.weekday()) % 7
        candidate = now_local.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(days=days_ahead, minutes=self._scheduled_min - self._window_half_min)
        if candidate <= now_local:
            candidate += timedelta(weeks=1)
        return time.monotonic() + (candidate - now_local).total_seconds()

    def _window_occurrence_date(self, now_local: datetime) -> date | None:
        current_min = _minute_of_day(now_local)
        start_min = self._scheduled_min - self._window_half_min
        end_min = self._scheduled_min + self._window_half_min
        previous_weekday = (self._weekday - 1) % 7
        next_weekday = (self._weekday + 1) % 7

        if 0 <= start_min and end_min < 1440:
            if now_local.weekday() == self._weekday and start_min <= current_min <= end_min:
                return now_local.date()
            return None
        if start_min < 0:
            if now_local.weekday() == previous_weekday and current_min >= start_min + 1440:
                return now_local.date() + timedelta(days=1)
            if now_local.weekday() == self._weekday and current_min <= end_min:
                return now_local.date()
            return None
        if end_min >= 1440:
            if now_local.weekday() == self._weekday and current_min >= start_min:
                return now_local.date()
            if now_local.weekday() == next_weekday and current_min <= end_min - 1440:
                return now_local.date() - timedelta(days=1)
            return None
        return None


def normalize_scheduled_routine_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted scheduled-routine config to one bounded contract."""
    weekday = int(cfg.get("weekday", 0))
    scheduled_min = int(cfg.get("scheduled_min", 0))
    window_half_min = max(0, int(cfg.get("window_half_min", 0)))
    house_state_in = _normalize_house_state_in(cfg.get("house_state_in"))
    skip_if_anyone_home = bool(cfg.get("skip_if_anyone_home", False))
    routine_kind = str(cfg.get("routine_kind") or "").strip().lower()
    if routine_kind not in _ROUTINE_KINDS:
        routine_kind = ""
    target_entities = _normalize_target_entities(cfg.get("target_entities"))
    entity_action = str(cfg.get("entity_action") or "turn_on").strip().lower()
    if entity_action not in _ENTITY_ACTIONS:
        entity_action = "turn_on"
    steps = _normalize_steps(cfg.get("steps"))
    if not steps and routine_kind and target_entities:
        steps = _steps_from_targets(
            routine_kind=routine_kind,
            target_entities=target_entities,
            entity_action=entity_action,
        )
    entity_domains = [
        domain
        for domain in list(cfg.get("entity_domains") or [])
        if isinstance(domain, str) and domain in _SUPPORTED_DOMAINS
    ]
    if not entity_domains and target_entities:
        entity_domains = sorted({entity_id.split(".", 1)[0] for entity_id in target_entities})
    return {
        "reaction_type": "scheduled_routine",
        "weekday": weekday,
        "scheduled_min": scheduled_min,
        "window_half_min": window_half_min,
        "house_state_in": house_state_in,
        "skip_if_anyone_home": skip_if_anyone_home,
        "routine_kind": routine_kind,
        "target_entities": target_entities,
        "entity_action": entity_action,
        "entity_domains": entity_domains,
        "steps": steps,
    }


def build_scheduled_routine_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> ScheduledRoutineReaction | None:
    try:
        normalized = normalize_scheduled_routine_config(cfg)
        steps = list(normalized.get("steps") or [])
        if not steps:
            raise ValueError("steps missing")
        return ScheduledRoutineReaction(
            weekday=int(normalized["weekday"]),
            scheduled_min=int(normalized["scheduled_min"]),
            window_half_min=int(normalized["window_half_min"]),
            steps=steps,
            house_state_in=list(normalized.get("house_state_in") or []),
            skip_if_anyone_home=bool(normalized.get("skip_if_anyone_home", False)),
            reaction_id=proposal_id,
        )
    except (KeyError, TypeError, ValueError):
        return None


def present_scheduled_routine_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    normalized = normalize_scheduled_routine_config(cfg)
    weekday = int(normalized.get("weekday", 0))
    scheduled_min = int(normalized.get("scheduled_min", 0))
    targets = list(normalized.get("target_entities") or [])
    target_summary = ""
    if targets:
        target_summary = f" · {targets[0]}" if len(targets) == 1 else f" · {len(targets)} targets"
    return f"Routine {_WEEKDAY_NAMES[weekday]} ~{_hhmm(scheduled_min)}{target_summary}"


def _normalize_house_state_in(raw: Any) -> list[str]:
    states: list[str] = []
    seen: set[str] = set()
    for value in list(raw or []):
        state = str(value).strip()
        if not state or state in seen:
            continue
        seen.add(state)
        states.append(state)
    return states


def _normalize_target_entities(raw: Any) -> list[str]:
    entities: list[str] = []
    for value in list(raw or []):
        entity_id = str(value).strip()
        if not entity_id or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        if domain not in _SUPPORTED_DOMAINS:
            continue
        entities.append(entity_id)
    return entities


def _normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for raw_step in list(raw_steps or []):
        if not isinstance(raw_step, dict):
            continue
        params = dict(raw_step.get("params") or {})
        target = str(raw_step.get("target") or params.get("entity_id") or "").strip()
        action = str(raw_step.get("action") or "").strip()
        domain = str(raw_step.get("domain") or "").strip()
        if not target or "." not in target:
            continue
        target_domain = target.split(".", 1)[0]
        if target_domain not in _SUPPORTED_DOMAINS:
            continue
        if not domain:
            domain = target_domain
        if domain != target_domain:
            continue
        if not _is_supported_action(domain, action):
            continue
        normalized_params = dict(params)
        normalized_params["entity_id"] = target
        steps.append(
            {
                "domain": domain,
                "target": target,
                "action": action,
                "params": normalized_params,
            }
        )
    return steps


def _steps_from_targets(
    *,
    routine_kind: str,
    target_entities: list[str],
    entity_action: str,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for entity_id in target_entities:
        domain = entity_id.split(".", 1)[0]
        if routine_kind == "scene" and domain == "scene":
            action = "scene.turn_on"
        elif routine_kind == "script" and domain == "script":
            action = "script.turn_on"
        elif routine_kind == "entity_action" and domain in {"light", "switch", "input_boolean"}:
            action = f"{domain}.{entity_action}"
        else:
            continue
        steps.append(
            {
                "domain": domain,
                "target": entity_id,
                "action": action,
                "params": {"entity_id": entity_id},
            }
        )
    return steps


def _is_supported_action(domain: str, action: str) -> bool:
    if domain in {"scene", "script"}:
        return action == f"{domain}.turn_on"
    if domain in {"light", "switch", "input_boolean"}:
        return action in {f"{domain}.turn_on", f"{domain}.turn_off"}
    return False


def _hhmm(minute_of_day: int) -> str:
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def _minute_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute
