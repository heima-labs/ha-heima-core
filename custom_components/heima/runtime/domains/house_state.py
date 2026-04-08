"""HouseStateDomain: house signals and house state resolution."""

# mypy: ignore-errors

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from ...const import DEFAULT_HOUSE_STATE_CONFIG, OPT_HOUSE_STATE_CONFIG
from ..normalization.config import (
    HOUSE_SIGNAL_STRATEGY_CONTRACT,
    build_signal_set_strategy_cfg_for_contract,
)
from ..normalization.service import InputNormalizer
from ..policy import resolve_house_state
from .calendar import CalendarResult
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)
_MEDIA_ACTIVE_STATES = {"on", "playing", "paused", "buffering"}


@dataclass(frozen=True)
class HouseStateResult:
    """Result of HouseStateDomain.compute()."""

    house_state: str
    house_reason: str
    override_active: bool


class HouseStateDomain:
    """Computes house signals and resolves house state."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._house_signals_trace: dict[str, dict[str, Any]] = {}
        self._candidate_trace: dict[str, dict[str, Any]] = {}
        self._candidate_summary: dict[str, dict[str, Any]] = {}
        self._candidate_state: dict[str, bool] = {}
        self._candidate_since: dict[str, str | None] = {}
        self._candidate_since_monotonic: dict[str, float] = {}
        self._resolution_trace: dict[str, Any] = {}
        self._current_config: dict[str, Any] = dict(DEFAULT_HOUSE_STATE_CONFIG)
        self._house_state_override: str | None = None
        self._house_state_override_set_by: str | None = None
        self._house_state_override_last_change_ts: str | None = None

    def reset(self) -> None:
        """Called on options reload - clears override."""
        self._house_state_override = None
        self._house_state_override_set_by = None
        self._house_state_override_last_change_ts = None
        self._house_signals_trace = {}
        self._candidate_trace = {}
        self._candidate_summary = {}
        self._candidate_state = {}
        self._candidate_since = {}
        self._candidate_since_monotonic = {}
        self._resolution_trace = {}
        self._current_config = dict(DEFAULT_HOUSE_STATE_CONFIG)

    @property
    def house_signals_trace(self) -> dict[str, dict[str, Any]]:
        return self._house_signals_trace

    @property
    def override_info(self) -> dict[str, Any]:
        return {
            "house_state_override": self._house_state_override,
            "house_state_override_active": self._house_state_override is not None,
            "house_state_override_set_by": self._house_state_override_set_by,
            "house_state_override_last_change_ts": self._house_state_override_last_change_ts,
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "house_signals_trace": dict(self._house_signals_trace),
            "candidate_trace": dict(self._candidate_trace),
            "candidate_summary": dict(self._candidate_summary),
            "config": dict(self._current_config),
            "timers": self._timer_config(self._current_config),
            "resolution_trace": dict(self._resolution_trace),
            "override": self.override_info,
        }

    # ------------------------------------------------------------------
    # Override
    # ------------------------------------------------------------------

    def set_override(
        self,
        *,
        mode: str,
        enabled: bool,
        source: str,
    ) -> tuple[str, str | None, str | None]:
        previous = self._house_state_override
        current = previous
        action = "noop"

        if enabled:
            if previous != mode:
                current = mode
                action = "set"
        elif previous == mode:
            current = None
            action = "clear"

        if action != "noop":
            self._house_state_override = current
            self._house_state_override_set_by = source
            self._house_state_override_last_change_ts = datetime.now(timezone.utc).isoformat()

        return action, previous, current

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    def compute(
        self,
        options: dict[str, Any],
        house_signal_entities: dict[str, str],
        anyone_home: bool,
        events: EventsDomain,
        state: Any,
        calendar_result: CalendarResult | None = None,
        schedule_recheck: Callable[..., None] | None = None,
    ) -> HouseStateResult:
        house_state_cfg = self._normalized_config(options)
        self._current_config = dict(house_state_cfg)
        vacation_mode = self._compute_house_signal(
            "vacation_mode",
            [house_signal_entities["vacation_mode"]]
            if "vacation_mode" in house_signal_entities
            else [],
        )
        guest_mode = self._compute_house_signal(
            "guest_mode",
            [house_signal_entities["guest_mode"]] if "guest_mode" in house_signal_entities else [],
        )
        sleep_window = self._compute_house_signal(
            "sleep_window",
            [house_signal_entities["sleep_window"]]
            if "sleep_window" in house_signal_entities
            else [],
        )
        relax_mode = self._compute_house_signal(
            "relax_mode",
            [house_signal_entities["relax_mode"]] if "relax_mode" in house_signal_entities else [],
        )
        work_window = self._compute_house_signal(
            "work_window",
            [house_signal_entities["work_window"]]
            if "work_window" in house_signal_entities
            else [],
        )
        media_active, media_inputs = self._compute_media_active(
            list(house_state_cfg.get("media_active_entities", []))
        )
        charging_evidence = self._compute_boolean_count_evidence(
            list(house_state_cfg.get("sleep_charging_entities", []))
        )
        workday_evidence = self._compute_workday_evidence(
            workday_entity=str(house_state_cfg.get("workday_entity", "") or ""),
            calendar_result=calendar_result,
        )

        # Calendar overrides: hard-state signals still take precedence over entity-based signals.
        # Keep legacy WFH/office behavior on work_window for backward compatibility,
        # then refine work_candidate through workday_evidence below.
        if calendar_result is not None:
            if calendar_result.is_vacation_active:
                vacation_mode = True
            if calendar_result.is_office_today:
                work_window = False
            elif calendar_result.is_wfh_today:
                work_window = True

        now = datetime.now(timezone.utc).isoformat()
        now_monotonic = time.monotonic()
        current_state_before = state.get_sensor("heima_house_state")
        candidate_inputs = self._build_candidate_inputs(
            anyone_home=anyone_home,
            sleep_window=sleep_window,
            relax_mode=relax_mode,
            work_window=work_window,
            media_active=media_active,
            media_inputs=media_inputs,
            charging_evidence=charging_evidence,
            workday_evidence=workday_evidence,
            calendar_result=calendar_result,
            house_state_cfg=house_state_cfg,
        )
        self._update_candidate_trace(
            candidate_inputs=candidate_inputs,
            now=now,
            now_monotonic=now_monotonic,
        )

        derived_house_state, derived_house_reason = resolve_house_state(
            anyone_home=anyone_home,
            vacation_mode=vacation_mode,
            guest_mode=guest_mode,
            sleep_window=sleep_window,
            relax_mode=relax_mode,
            work_window=work_window,
        )
        override_active = self._house_state_override is not None
        resolution_path = "home_substate"
        resolution_detail: dict[str, Any] = {}
        if override_active:
            house_state = self._house_state_override  # type: ignore[assignment]
            house_reason = f"manual_override:{self._house_state_override}"
            resolution_path = "override"
            resolution_detail = {
                "action": "override",
                "source": "manual_override",
            }
        elif vacation_mode:
            house_state = "vacation"
            house_reason = "vacation_mode"
            resolution_path = "hard_state"
            resolution_detail = {
                "action": "hard_state",
                "source": "vacation_mode",
            }
        elif guest_mode:
            house_state = "guest"
            house_reason = "guest_mode"
            resolution_path = "hard_state"
            resolution_detail = {
                "action": "hard_state",
                "source": "guest_mode",
            }
        elif not anyone_home:
            house_state = "away"
            house_reason = "no_presence"
            resolution_path = "hard_state"
            resolution_detail = {
                "action": "hard_state",
                "source": "no_presence",
            }
        else:
            house_state, house_reason, resolution_detail = self._resolve_home_substate(
                current_state_before=str(current_state_before or "home"),
                now_monotonic=now_monotonic,
                schedule_recheck=schedule_recheck,
                house_state_cfg=house_state_cfg,
            )

        self._candidate_summary = self._build_candidate_summary(
            now_monotonic=now_monotonic,
            house_state_cfg=house_state_cfg,
            current_house_state=house_state,
        )

        self._resolution_trace = {
            "current_state_before": current_state_before,
            "current_home_state_before": (
                current_state_before
                if current_state_before in {"sleeping", "relax", "working", "home"}
                else "home"
            ),
            "derived_state_direct": derived_house_state,
            "derived_reason_direct": derived_house_reason,
            "resolved_state_after": house_state,
            "winning_reason": house_reason,
            "resolution_path": resolution_path,
            "override_active": override_active,
            "sticky_retention": bool(resolution_detail.get("action") == "retain"),
            "home_substate_candidate": (
                house_state if house_state in {"sleeping", "relax", "working", "home"} else None
            ),
            "active_candidates": [
                name for name, trace in self._candidate_trace.items() if bool(trace.get("state"))
            ],
            "decision": dict(resolution_detail),
        }

        return HouseStateResult(
            house_state=house_state,
            house_reason=house_reason,
            override_active=override_active,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _normalized_config(self, options: dict[str, Any]) -> dict[str, Any]:
        current = options.get(OPT_HOUSE_STATE_CONFIG, {})
        merged = dict(DEFAULT_HOUSE_STATE_CONFIG)
        if isinstance(current, dict):
            merged.update(current)
        merged["media_active_entities"] = [
            str(entity_id).strip()
            for entity_id in list(merged.get("media_active_entities", []) or [])
            if str(entity_id).strip()
        ]
        merged["sleep_charging_entities"] = [
            str(entity_id).strip()
            for entity_id in list(merged.get("sleep_charging_entities", []) or [])
            if str(entity_id).strip()
        ]
        merged["workday_entity"] = str(merged.get("workday_entity", "") or "").strip()
        merged["sleep_enter_min"] = int(merged.get("sleep_enter_min", 10))
        merged["sleep_exit_min"] = int(merged.get("sleep_exit_min", 2))
        merged["work_enter_min"] = int(merged.get("work_enter_min", 5))
        merged["relax_enter_min"] = int(merged.get("relax_enter_min", 2))
        merged["relax_exit_min"] = int(merged.get("relax_exit_min", 10))
        merged["sleep_requires_media_off"] = bool(merged.get("sleep_requires_media_off", True))
        raw_charging = merged.get("sleep_charging_min_count")
        merged["sleep_charging_min_count"] = (
            int(raw_charging) if raw_charging not in (None, "") else None
        )
        return merged

    @staticmethod
    def _timer_config(cfg: dict[str, Any]) -> dict[str, int]:
        return {
            "sleep_enter_min": int(cfg["sleep_enter_min"]),
            "sleep_exit_min": int(cfg["sleep_exit_min"]),
            "work_enter_min": int(cfg["work_enter_min"]),
            "relax_enter_min": int(cfg["relax_enter_min"]),
            "relax_exit_min": int(cfg["relax_exit_min"]),
        }

    def _build_candidate_inputs(
        self,
        *,
        anyone_home: bool,
        sleep_window: bool,
        relax_mode: bool,
        work_window: bool,
        media_active: bool,
        media_inputs: dict[str, Any],
        charging_evidence: dict[str, Any],
        workday_evidence: dict[str, Any],
        calendar_result: CalendarResult | None,
        house_state_cfg: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        calendar_flags = {
            "is_vacation_active": bool(calendar_result.is_vacation_active)
            if calendar_result is not None
            else False,
            "is_office_today": bool(calendar_result.is_office_today)
            if calendar_result is not None
            else False,
            "is_wfh_today": bool(calendar_result.is_wfh_today)
            if calendar_result is not None
            else False,
        }
        sleep_requires_media_off = bool(house_state_cfg.get("sleep_requires_media_off", True))
        sleep_allowed_by_media = (not sleep_requires_media_off) or (not media_active)
        sleep_charging_min_count = house_state_cfg.get("sleep_charging_min_count")
        sleep_allowed_by_charging = sleep_charging_min_count is None or int(
            charging_evidence.get("active_count", 0)
        ) >= int(sleep_charging_min_count)
        relax_reason = (
            "anyone_home+relax_mode"
            if bool(anyone_home and relax_mode)
            else "anyone_home+media_active"
            if bool(anyone_home and media_active)
            else "anyone_home+relax_mode_or_media_active"
        )
        return {
            "sleep_candidate": {
                "state": bool(
                    anyone_home
                    and sleep_window
                    and sleep_allowed_by_media
                    and sleep_allowed_by_charging
                ),
                "reason": (
                    "anyone_home+sleep_window+media_off+charging"
                    if sleep_requires_media_off and sleep_charging_min_count is not None
                    else "anyone_home+sleep_window+media_off"
                    if sleep_requires_media_off
                    else "anyone_home+sleep_window+charging"
                    if sleep_charging_min_count is not None
                    else "anyone_home+sleep_window"
                ),
                "inputs": {
                    "anyone_home": anyone_home,
                    "sleep_window": sleep_window,
                    "media_active": media_active,
                    "media": media_inputs,
                    "sleep_requires_media_off": sleep_requires_media_off,
                    "sleep_media_requirement_met": sleep_allowed_by_media,
                    "sleep_charging_min_count": sleep_charging_min_count,
                    "charging": charging_evidence,
                    "sleep_charging_requirement_met": sleep_allowed_by_charging,
                },
            },
            "wake_candidate": {
                "state": bool(anyone_home and ((not sleep_window) or media_active)),
                "reason": (
                    "anyone_home+media_active" if media_active else "anyone_home+sleep_window_off"
                ),
                "inputs": {
                    "anyone_home": anyone_home,
                    "sleep_window": sleep_window,
                    "media_active": media_active,
                    "media": media_inputs,
                },
            },
            "work_candidate": {
                "state": bool(
                    anyone_home and work_window and bool(workday_evidence.get("is_workday", True))
                ),
                "reason": (
                    "anyone_home+work_window+workday"
                    if bool(workday_evidence.get("is_workday", True))
                    else "anyone_home+work_window+not_workday"
                ),
                "inputs": {
                    "anyone_home": anyone_home,
                    "work_window": work_window,
                    "workday_entity": str(house_state_cfg.get("workday_entity", "") or ""),
                    "workday_evidence": dict(workday_evidence),
                    **calendar_flags,
                },
            },
            "relax_candidate": {
                "state": bool(anyone_home and (relax_mode or media_active)),
                "reason": relax_reason,
                "inputs": {
                    "anyone_home": anyone_home,
                    "relax_mode": relax_mode,
                    "media_active": media_active,
                    "media": media_inputs,
                    "media_active_entities": list(house_state_cfg.get("media_active_entities", [])),
                },
            },
        }

    def _compute_media_active(self, entity_ids: list[str]) -> tuple[bool, dict[str, Any]]:
        states: dict[str, str | None] = {}
        active_entities: list[str] = []
        for entity_id in entity_ids:
            state_obj = self._hass.states.get(entity_id)
            raw_state = getattr(state_obj, "state", None) if state_obj is not None else None
            raw = str(raw_state).strip() if raw_state is not None else None
            states[entity_id] = raw
            if self._is_media_entity_active(entity_id, raw):
                active_entities.append(entity_id)
        return bool(active_entities), {
            "configured_entities": list(entity_ids),
            "entity_states": states,
            "active_entities": active_entities,
        }

    def _compute_boolean_count_evidence(self, entity_ids: list[str]) -> dict[str, Any]:
        entity_states: dict[str, str | None] = {}
        active_entities: list[str] = []
        observations: dict[str, dict[str, Any]] = {}
        for entity_id in entity_ids:
            observation = self._normalizer.boolean_signal(entity_id)
            entity_states[entity_id] = observation.raw_state
            observations[entity_id] = observation.as_dict()
            if observation.state == "on":
                active_entities.append(entity_id)
        return {
            "configured_entities": list(entity_ids),
            "entity_states": entity_states,
            "active_entities": active_entities,
            "active_count": len(active_entities),
            "observations": observations,
        }

    def _compute_workday_evidence(
        self,
        *,
        workday_entity: str,
        calendar_result: CalendarResult | None,
    ) -> dict[str, Any]:
        if calendar_result is not None and calendar_result.is_office_today:
            return {
                "is_workday": False,
                "source": "calendar_office",
                "entity_id": workday_entity or None,
                "raw_state": None,
            }
        if calendar_result is not None and calendar_result.is_wfh_today:
            return {
                "is_workday": True,
                "source": "calendar_wfh",
                "entity_id": workday_entity or None,
                "raw_state": None,
            }
        if workday_entity:
            observation = self._normalizer.boolean_signal(workday_entity)
            return {
                "is_workday": observation.state == "on",
                "source": "workday_entity",
                "entity_id": workday_entity,
                "raw_state": observation.raw_state,
                "normalized_state": observation.state,
                "reason": observation.reason,
            }
        return {
            "is_workday": True,
            "source": "default_true",
            "entity_id": None,
            "raw_state": None,
        }

    @staticmethod
    def _is_media_entity_active(entity_id: str, raw_state: str | None) -> bool:
        lowered = str(raw_state or "").strip().lower()
        if lowered in {"", "unknown", "unavailable", "none"}:
            return False
        if str(entity_id).startswith("media_player."):
            return lowered in _MEDIA_ACTIVE_STATES
        return lowered in _MEDIA_ACTIVE_STATES or lowered in {
            "open",
            "occupied",
            "detected",
            "true",
            "1",
        }

    def _update_candidate_trace(
        self,
        *,
        candidate_inputs: dict[str, dict[str, Any]],
        now: str,
        now_monotonic: float,
    ) -> None:
        updated: dict[str, dict[str, Any]] = {}
        for candidate, payload in candidate_inputs.items():
            current = bool(payload.get("state"))
            previous = self._candidate_state.get(candidate)
            since = self._candidate_since.get(candidate)
            since_monotonic = self._candidate_since_monotonic.get(candidate)
            changed = previous is None or previous != current
            if changed:
                since = now
                since_monotonic = now_monotonic
                self._candidate_state[candidate] = current
                self._candidate_since[candidate] = since
                self._candidate_since_monotonic[candidate] = since_monotonic
            duration_s = (
                max(0.0, now_monotonic - since_monotonic) if since_monotonic is not None else 0.0
            )
            updated[candidate] = {
                "state": current,
                "state_since": since,
                "duration_s": duration_s,
                "changed_this_cycle": changed,
                "reason": payload.get("reason"),
                "inputs": dict(payload.get("inputs", {})),
            }
        self._candidate_trace = updated

    def _build_candidate_summary(
        self,
        *,
        now_monotonic: float,
        house_state_cfg: dict[str, Any],
        current_house_state: str,
    ) -> dict[str, dict[str, Any]]:
        timers = self._timer_config(house_state_cfg)
        threshold_map = {
            "sleep_candidate": {"enter_s": timers["sleep_enter_min"] * 60, "exit_s": None},
            "wake_candidate": {"enter_s": None, "exit_s": timers["sleep_exit_min"] * 60},
            "work_candidate": {"enter_s": timers["work_enter_min"] * 60, "exit_s": None},
            "relax_candidate": {
                "enter_s": timers["relax_enter_min"] * 60,
                "exit_s": timers["relax_exit_min"] * 60,
            },
        }
        summary: dict[str, dict[str, Any]] = {}
        for candidate, trace in self._candidate_trace.items():
            active = bool(trace.get("state"))
            active_for = self._candidate_active_for(candidate, now_monotonic)
            inactive_for = self._candidate_inactive_for(candidate, now_monotonic)
            enter_s = threshold_map.get(candidate, {}).get("enter_s")
            exit_s = threshold_map.get(candidate, {}).get("exit_s")
            if active:
                if enter_s is None:
                    status = "active"
                elif active_for >= float(enter_s):
                    status = "confirmed"
                else:
                    status = "pending_enter"
            else:
                if exit_s is None:
                    status = "inactive"
                elif inactive_for < float(exit_s) and (
                    (candidate == "wake_candidate" and current_house_state == "sleeping")
                    or (candidate == "relax_candidate" and current_house_state == "relax")
                ):
                    status = "pending_exit_guard"
                else:
                    status = "inactive"
            summary[candidate] = {
                "status": status,
                "active_for_s": active_for,
                "inactive_for_s": inactive_for,
                "enter_threshold_s": enter_s,
                "exit_threshold_s": exit_s,
                "remaining_enter_s": (
                    max(0.0, float(enter_s) - active_for)
                    if active and enter_s is not None and active_for < float(enter_s)
                    else 0.0
                ),
                "remaining_exit_s": (
                    max(0.0, float(exit_s) - inactive_for)
                    if (not active) and exit_s is not None and inactive_for < float(exit_s)
                    else 0.0
                ),
            }
        return summary

    def _candidate_active_for(self, candidate: str, now_monotonic: float) -> float:
        if not self._candidate_state.get(candidate, False):
            return 0.0
        since = self._candidate_since_monotonic.get(candidate)
        if since is None:
            return 0.0
        return max(0.0, now_monotonic - since)

    def _candidate_inactive_for(self, candidate: str, now_monotonic: float) -> float:
        if self._candidate_state.get(candidate, False):
            return 0.0
        since = self._candidate_since_monotonic.get(candidate)
        if since is None:
            return 0.0
        return max(0.0, now_monotonic - since)

    def _schedule_candidate_recheck(
        self,
        *,
        schedule_recheck: Callable[..., None] | None,
        candidate: str,
        delay_s: float,
        label: str,
    ) -> None:
        if schedule_recheck is None or delay_s <= 0:
            return
        schedule_recheck(
            job_id=f"house_state:{candidate}:{label}",
            deadline=time.monotonic() + delay_s,
            owner="house_state",
            label=label,
        )

    def _resolve_home_substate(
        self,
        *,
        current_state_before: str,
        now_monotonic: float,
        schedule_recheck: Callable[..., None] | None,
        house_state_cfg: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        current = (
            current_state_before
            if current_state_before in {"sleeping", "relax", "working", "home"}
            else "home"
        )
        sleep_on = bool(self._candidate_state.get("sleep_candidate", False))
        wake_on = bool(self._candidate_state.get("wake_candidate", False))
        relax_on = bool(self._candidate_state.get("relax_candidate", False))
        work_on = bool(self._candidate_state.get("work_candidate", False))

        timers = self._timer_config(house_state_cfg)
        sleep_enter_s = timers["sleep_enter_min"] * 60
        sleep_exit_s = timers["sleep_exit_min"] * 60
        work_enter_s = timers["work_enter_min"] * 60
        relax_enter_s = timers["relax_enter_min"] * 60
        relax_exit_s = timers["relax_exit_min"] * 60

        wake_for = self._candidate_active_for("wake_candidate", now_monotonic)
        if current == "sleeping":
            if wake_on and wake_for < sleep_exit_s:
                self._schedule_candidate_recheck(
                    schedule_recheck=schedule_recheck,
                    candidate="wake_candidate",
                    delay_s=sleep_exit_s - wake_for,
                    label="sleep_exit_threshold",
                )
                return (
                    "sleeping",
                    "sleep_sticky_until_wake",
                    {
                        "action": "retain",
                        "source_candidate": "wake_candidate",
                        "retained_state": "sleeping",
                        "pending_kind": "exit_threshold",
                        "pending_remaining_s": sleep_exit_s - wake_for,
                    },
                )
            if not wake_on:
                return (
                    "sleeping",
                    "sleep_sticky_until_wake",
                    {
                        "action": "retain",
                        "source_candidate": "wake_candidate",
                        "retained_state": "sleeping",
                        "pending_kind": "wait_for_candidate",
                    },
                )

        sleep_for = self._candidate_active_for("sleep_candidate", now_monotonic)
        if sleep_on and sleep_for >= sleep_enter_s:
            return (
                "sleeping",
                "sleep_candidate_confirmed",
                {
                    "action": "enter",
                    "source_candidate": "sleep_candidate",
                    "entered_state": "sleeping",
                },
            )
        if sleep_on and sleep_for < sleep_enter_s:
            self._schedule_candidate_recheck(
                schedule_recheck=schedule_recheck,
                candidate="sleep_candidate",
                delay_s=sleep_enter_s - sleep_for,
                label="sleep_enter_threshold",
            )
            return (
                "home",
                "default",
                {
                    "action": "pending",
                    "source_candidate": "sleep_candidate",
                    "pending_kind": "enter_threshold",
                    "pending_remaining_s": sleep_enter_s - sleep_for,
                },
            )

        if current == "relax":
            if relax_on:
                relax_reason = str(
                    self._candidate_trace.get("relax_candidate", {}).get("reason", "")
                )
                if relax_reason == "anyone_home+relax_mode":
                    return (
                        "relax",
                        "relax_explicit_signal",
                        {
                            "action": "retain",
                            "source_candidate": "relax_candidate",
                            "retained_state": "relax",
                            "retention_reason": "explicit_signal",
                        },
                    )
                return (
                    "relax",
                    "relax_candidate_active",
                    {
                        "action": "retain",
                        "source_candidate": "relax_candidate",
                        "retained_state": "relax",
                        "retention_reason": "candidate_still_active",
                    },
                )
            relax_off_for = self._candidate_inactive_for("relax_candidate", now_monotonic)
            if relax_off_for < relax_exit_s:
                self._schedule_candidate_recheck(
                    schedule_recheck=schedule_recheck,
                    candidate="relax_candidate",
                    delay_s=relax_exit_s - relax_off_for,
                    label="relax_exit_threshold",
                )
                return (
                    "relax",
                    "relax_sticky_exit_guard",
                    {
                        "action": "retain",
                        "source_candidate": "relax_candidate",
                        "retained_state": "relax",
                        "pending_kind": "exit_threshold",
                        "pending_remaining_s": relax_exit_s - relax_off_for,
                    },
                )

        if relax_on:
            relax_reason = str(self._candidate_trace.get("relax_candidate", {}).get("reason", ""))
            if relax_reason == "anyone_home+relax_mode":
                return (
                    "relax",
                    "relax_explicit_signal",
                    {
                        "action": "enter",
                        "source_candidate": "relax_candidate",
                        "entered_state": "relax",
                        "entry_mode": "explicit_signal",
                    },
                )
            relax_for = self._candidate_active_for("relax_candidate", now_monotonic)
            if relax_for >= relax_enter_s:
                return (
                    "relax",
                    "relax_candidate_confirmed",
                    {
                        "action": "enter",
                        "source_candidate": "relax_candidate",
                        "entered_state": "relax",
                    },
                )
            self._schedule_candidate_recheck(
                schedule_recheck=schedule_recheck,
                candidate="relax_candidate",
                delay_s=relax_enter_s - relax_for,
                label="relax_enter_threshold",
            )
            return (
                "home",
                "default",
                {
                    "action": "pending",
                    "source_candidate": "relax_candidate",
                    "pending_kind": "enter_threshold",
                    "pending_remaining_s": relax_enter_s - relax_for,
                },
            )

        if current == "working" and work_on:
            return (
                "working",
                "work_candidate_confirmed",
                {
                    "action": "retain",
                    "source_candidate": "work_candidate",
                    "retained_state": "working",
                    "retention_reason": "candidate_still_active",
                },
            )

        work_for = self._candidate_active_for("work_candidate", now_monotonic)
        if work_on and work_for >= work_enter_s:
            return (
                "working",
                "work_candidate_confirmed",
                {
                    "action": "enter",
                    "source_candidate": "work_candidate",
                    "entered_state": "working",
                },
            )
        if work_on and work_for < work_enter_s:
            self._schedule_candidate_recheck(
                schedule_recheck=schedule_recheck,
                candidate="work_candidate",
                delay_s=work_enter_s - work_for,
                label="work_enter_threshold",
            )
            return (
                "home",
                "default",
                {
                    "action": "pending",
                    "source_candidate": "work_candidate",
                    "pending_kind": "enter_threshold",
                    "pending_remaining_s": work_enter_s - work_for,
                },
            )

        return (
            "home",
            "default",
            {
                "action": "fallback_home",
            },
        )

    def _compute_house_signal(self, trace_key: str, entity_ids: list[str]) -> bool:
        observations = [self._normalizer.boolean_signal(entity_id) for entity_id in entity_ids]
        fused = self._normalizer.derive(
            kind="boolean_signal",
            inputs=observations,
            strategy_cfg=build_signal_set_strategy_cfg_for_contract(
                contract=HOUSE_SIGNAL_STRATEGY_CONTRACT,
            ),
            context={"source": "house_signal", "signal": trace_key},
        )
        unavailable_inputs = [
            obs.source_entity_id
            for obs in observations
            if (obs.source_entity_id and not bool(obs.available))
        ]
        unknown_inputs = [
            obs.source_entity_id
            for obs in observations
            if (obs.source_entity_id and obs.state == "unknown")
        ]
        resolved_bool = fused.state == "on"
        self._house_signals_trace[trace_key] = {
            "configured_entities": list(entity_ids),
            "source_observations": [obs.as_dict() for obs in observations],
            "fused_observation": fused.as_dict(),
            "fused_state": fused.state,
            "resolved_bool": resolved_bool,
            "resolved_reason": (
                "derived_on"
                if fused.state == "on"
                else "derived_off"
                if fused.state == "off"
                else "derived_unknown_treated_as_false"
            ),
            "plugin_id": fused.plugin_id,
            "used_plugin_fallback": fused.reason == "plugin_error_fallback",
            "has_unknown_inputs": bool(unknown_inputs),
            "unknown_inputs": unknown_inputs,
            "has_unavailable_inputs": bool(unavailable_inputs),
            "unavailable_inputs": unavailable_inputs,
        }
        return resolved_bool
