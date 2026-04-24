"""_ScheduledLightingBase — internal base class for scheduled per-entity lighting reactions."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from ..contracts import ApplyStep
from ..scheduler import ScheduledRuntimeJob
from ..snapshot import DecisionSnapshot
from ._lighting_review import render_entity_steps_tuning_details
from .base import HeimaReaction

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class _ScheduledLightingBase(HeimaReaction):
    """Internal base: fires a per-entity lighting configuration at a scheduled weekday + time.

    Not a user-facing reaction type. Subclasses (e.g. ContextConditionedLightingReaction)
    add gating logic on top of the scheduling mechanism.

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
                owner=self.__class__.__name__,
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
        delta_s = (candidate - now_local).total_seconds()
        return time.monotonic() + delta_s

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        now_local = dt_util.now()
        occurrence_date = self._window_occurrence_date(now_local)
        if occurrence_date is None:
            return []
        if self._house_state_filter and history[-1].house_state != self._house_state_filter:
            return []
        occurrence_day = occurrence_date.isoformat()
        if self._last_fired_date == occurrence_day:
            return []
        self._last_fired_date = occurrence_day
        return self._build_steps()

    def reset_learning_state(self) -> None:
        self._last_fired_date = None

    def _window_occurrence_date(self, now_local: datetime) -> date | None:
        current_min = _minute_of_day(now_local)
        start_min = self._scheduled_min - self._window_half_min
        end_min = self._scheduled_min + self._window_half_min
        configured_weekday = self._weekday
        previous_weekday = (configured_weekday - 1) % 7
        next_weekday = (configured_weekday + 1) % 7

        if 0 <= start_min and end_min < 1440:
            if now_local.weekday() == configured_weekday and start_min <= current_min <= end_min:
                return now_local.date()
            return None

        if start_min < 0:
            if now_local.weekday() == previous_weekday and current_min >= start_min + 1440:
                return now_local.date() + timedelta(days=1)
            if now_local.weekday() == configured_weekday and current_min <= end_min:
                return now_local.date()
            return None

        if end_min >= 1440:
            if now_local.weekday() == configured_weekday and current_min >= start_min:
                return now_local.date()
            if now_local.weekday() == next_weekday and current_min <= end_min - 1440:
                return now_local.date() - timedelta(days=1)
            return None

        return None

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
                steps.append(
                    ApplyStep(
                        domain="lighting",
                        target=self._room_id,
                        action="light.turn_on",
                        params=params,
                        reason=f"lighting_schedule:{self._reaction_id}",
                    )
                )
            else:
                steps.append(
                    ApplyStep(
                        domain="lighting",
                        target=self._room_id,
                        action="light.turn_off",
                        params={"entity_id": entity_id},
                        reason=f"lighting_schedule:{self._reaction_id}",
                    )
                )
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


def _minute_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute



def present_admin_authored_lighting_schedule_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return lighting-schedule-specific admin-authored review details."""
    is_it = language.startswith("it")
    details: list[str] = []

    weekday = cfg.get("weekday")
    if weekday not in (None, ""):
        weekday_label = flow._weekday_label(weekday, language)  # noqa: SLF001
        details.append(
            f"Giorno pianificato: {weekday_label}" if is_it else f"Scheduled day: {weekday_label}"
        )

    scheduled_min = cfg.get("scheduled_min")
    if isinstance(scheduled_min, (int, float)):
        hhmm = f"{int(scheduled_min) // 60:02d}:{int(scheduled_min) % 60:02d}"
        details.append(f"Orario pianificato: {hhmm}" if is_it else f"Scheduled time: {hhmm}")

    entity_steps = cfg.get("entity_steps")
    if isinstance(entity_steps, list) and entity_steps:
        details.append(
            f"Luci coinvolte: {len(entity_steps)}"
            if is_it
            else f"Lights involved: {len(entity_steps)}"
        )

    return details



def present_tuning_lighting_schedule_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return lighting-schedule-specific tuning diff lines."""
    is_it = language.startswith("it")
    diff_lines: list[str] = []

    current_scheduled = target_cfg.get("scheduled_min")
    proposed_scheduled = cfg.get("scheduled_min")
    if isinstance(current_scheduled, (int, float)) and isinstance(proposed_scheduled, (int, float)):
        current_hhmm = f"{int(current_scheduled) // 60:02d}:{int(current_scheduled) % 60:02d}"
        proposed_hhmm = f"{int(proposed_scheduled) // 60:02d}:{int(proposed_scheduled) % 60:02d}"
        if current_hhmm != proposed_hhmm:
            diff_lines.append(
                f"Orario: {current_hhmm} -> {proposed_hhmm}"
                if is_it
                else f"Time: {current_hhmm} -> {proposed_hhmm}"
            )

    current_steps = target_cfg.get("entity_steps")
    proposed_steps = cfg.get("entity_steps")
    if isinstance(current_steps, list) and isinstance(proposed_steps, list):
        diff_lines.extend(
            render_entity_steps_tuning_details(
                current_steps,
                proposed_steps,
                language=language,
            )
        )

    if not diff_lines:
        return []
    return diff_lines


