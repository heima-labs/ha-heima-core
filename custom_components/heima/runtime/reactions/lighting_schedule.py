"""LightingScheduleReaction — fires a learned per-entity lighting config at a scheduled time."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.util import dt as dt_util

from ..contracts import ApplyStep
from ..scheduler import ScheduledRuntimeJob
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class LightingScheduleReaction(HeimaReaction):
    """Applies a learned per-entity lighting configuration at a scheduled weekday + time.

    Built from an accepted `lighting_scene_schedule` proposal. Fires at
    `scheduled_min ± window_half_min` on the configured weekday, applying each
    entity_step as a separate ApplyStep (light.turn_on or light.turn_off).

    Debounced: fires at most once per calendar day.
    """

    def __init__(
        self,
        *,
        room_id: str,
        weekday: int,
        scheduled_min: int,
        window_half_min: int = 10,
        house_state_filter: str | None = None,
        entity_steps: list[dict[str, Any]],
        reaction_id: str | None = None,
    ) -> None:
        self._room_id = room_id
        self._weekday = weekday
        self._scheduled_min = scheduled_min
        self._window_half_min = window_half_min
        self._house_state_filter = house_state_filter
        self._entity_steps = list(entity_steps)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._last_fired_date: str | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    # ------------------------------------------------------------------
    # Scheduler integration
    # ------------------------------------------------------------------

    def scheduled_jobs(self, entry_id: str) -> dict[str, ScheduledRuntimeJob]:
        due_monotonic = self._next_due_monotonic()
        job_id = f"lighting_schedule:{self._reaction_id}"
        return {
            job_id: ScheduledRuntimeJob(
                job_id=job_id,
                owner="LightingScheduleReaction",
                entry_id=entry_id,
                due_monotonic=due_monotonic,
                label=(
                    f"lighting: {self._room_id} "
                    f"{_WEEKDAY_NAMES[self._weekday]} ~{_hhmm(self._scheduled_min)}"
                ),
            )
        }

    def _next_due_monotonic(self) -> float:
        """Compute monotonic timestamp for the next trigger point.

        Trigger point = (scheduled_min - window_half_min) on the configured weekday.
        If that moment has already passed this week, project to next week.
        """
        trigger_min = self._scheduled_min - self._window_half_min
        now_local = dt_util.now()
        days_ahead = (self._weekday - now_local.weekday()) % 7
        candidate = now_local.replace(
            hour=trigger_min // 60,
            minute=trigger_min % 60,
            second=0,
            microsecond=0,
        ) + timedelta(days=days_ahead)
        if candidate <= now_local:
            candidate += timedelta(weeks=1)
        delta_s = (candidate - now_local).total_seconds()
        return time.monotonic() + delta_s

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        now_local = dt_util.now()
        if now_local.weekday() != self._weekday:
            return []
        current_min = now_local.hour * 60 + now_local.minute
        lo = self._scheduled_min - self._window_half_min
        hi = self._scheduled_min + self._window_half_min
        if not (lo <= current_min <= hi):
            return []
        if self._house_state_filter and history[-1].house_state != self._house_state_filter:
            return []
        today = now_local.date().isoformat()
        if self._last_fired_date == today:
            return []
        self._last_fired_date = today
        return self._build_steps()

    def _build_steps(self) -> list[ApplyStep]:
        steps = []
        for cfg in self._entity_steps:
            entity_id = cfg.get("entity_id", "")
            action = cfg.get("action", "")
            if not entity_id or action not in ("on", "off"):
                continue
            if action == "on":
                params: dict[str, Any] = {"entity_id": entity_id}
                if cfg.get("brightness") is not None:
                    params["brightness"] = cfg["brightness"]
                if cfg.get("rgb_color") is not None:
                    params["rgb_color"] = cfg["rgb_color"]
                elif cfg.get("color_temp_kelvin") is not None:
                    params["color_temp_kelvin"] = cfg["color_temp_kelvin"]
                steps.append(ApplyStep(
                    domain="lighting",
                    target=self._room_id,
                    action="light.turn_on",
                    params=params,
                    reason=f"lighting_schedule:{self._reaction_id}",
                ))
            else:
                steps.append(ApplyStep(
                    domain="lighting",
                    target=self._room_id,
                    action="light.turn_off",
                    params={"entity_id": entity_id},
                    reason=f"lighting_schedule:{self._reaction_id}",
                ))
        return steps

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "weekday": self._weekday,
            "scheduled_min": self._scheduled_min,
            "window_half_min": self._window_half_min,
            "house_state_filter": self._house_state_filter,
            "entity_steps": len(self._entity_steps),
            "last_fired_date": self._last_fired_date,
        }


def _hhmm(minute_of_day: int) -> str:
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"
