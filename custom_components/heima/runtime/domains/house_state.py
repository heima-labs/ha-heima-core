"""HouseStateDomain: house signals and house state resolution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from .calendar import CalendarResult
from ..normalization.config import (
    HOUSE_SIGNAL_STRATEGY_CONTRACT,
    build_signal_set_strategy_cfg_for_contract,
)
from ..normalization.service import InputNormalizer
from ..policy import resolve_house_state
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)

_HOUSE_STATE_TIMER_DEFAULTS = {
    "sleep_enter_min": 10,
    "sleep_exit_min": 2,
    "work_enter_min": 5,
    "relax_enter_min": 2,
    "relax_exit_min": 10,
}


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
        self._candidate_state: dict[str, bool] = {}
        self._candidate_since: dict[str, str | None] = {}
        self._candidate_since_monotonic: dict[str, float] = {}
        self._resolution_trace: dict[str, Any] = {}
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
        self._candidate_state = {}
        self._candidate_since = {}
        self._candidate_since_monotonic = {}
        self._resolution_trace = {}

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
            "timers": dict(_HOUSE_STATE_TIMER_DEFAULTS),
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
            self._house_state_override_last_change_ts = datetime.now(
                timezone.utc
            ).isoformat()

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
        vacation_mode = self._compute_house_signal(
            "vacation_mode",
            [house_signal_entities["vacation_mode"]]
            if "vacation_mode" in house_signal_entities
            else [],
        )
        guest_mode = self._compute_house_signal(
            "guest_mode",
            [house_signal_entities["guest_mode"]]
            if "guest_mode" in house_signal_entities
            else [],
        )
        sleep_window = self._compute_house_signal(
            "sleep_window",
            [house_signal_entities["sleep_window"]]
            if "sleep_window" in house_signal_entities
            else [],
        )
        relax_mode = self._compute_house_signal(
            "relax_mode",
            [house_signal_entities["relax_mode"]]
            if "relax_mode" in house_signal_entities
            else [],
        )
        work_window = self._compute_house_signal(
            "work_window",
            [house_signal_entities["work_window"]]
            if "work_window" in house_signal_entities
            else [],
        )

        # Calendar overrides: calendar signals take precedence over entity-based signals
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
            calendar_result=calendar_result,
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
        sticky_retention = False
        if override_active:
            house_state = self._house_state_override  # type: ignore[assignment]
            house_reason = f"manual_override:{self._house_state_override}"
        elif vacation_mode:
            house_state = "vacation"
            house_reason = "vacation_mode"
        elif guest_mode:
            house_state = "guest"
            house_reason = "guest_mode"
        elif not anyone_home:
            house_state = "away"
            house_reason = "no_presence"
        else:
            house_state, house_reason, sticky_retention = self._resolve_home_substate(
                current_state_before=str(current_state_before or "home"),
                now_monotonic=now_monotonic,
                schedule_recheck=schedule_recheck,
            )

        self._resolution_trace = {
            "current_state_before": current_state_before,
            "derived_state_direct": derived_house_state,
            "derived_reason_direct": derived_house_reason,
            "resolved_state_after": house_state,
            "winning_reason": house_reason,
            "override_active": override_active,
            "sticky_retention": sticky_retention,
            "home_substate_candidate": (
                house_state
                if house_state in {"sleeping", "relax", "working", "home"}
                else None
            ),
        }

        return HouseStateResult(
            house_state=house_state,
            house_reason=house_reason,
            override_active=override_active,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_candidate_inputs(
        self,
        *,
        anyone_home: bool,
        sleep_window: bool,
        relax_mode: bool,
        work_window: bool,
        calendar_result: CalendarResult | None,
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
        return {
            "sleep_candidate": {
                "state": bool(anyone_home and sleep_window),
                "reason": "anyone_home+sleep_window",
                "inputs": {
                    "anyone_home": anyone_home,
                    "sleep_window": sleep_window,
                },
            },
            "wake_candidate": {
                "state": bool(anyone_home and (not sleep_window)),
                "reason": "anyone_home+sleep_window_off",
                "inputs": {
                    "anyone_home": anyone_home,
                    "sleep_window": sleep_window,
                },
            },
            "work_candidate": {
                "state": bool(anyone_home and work_window),
                "reason": "anyone_home+work_window",
                "inputs": {
                    "anyone_home": anyone_home,
                    "work_window": work_window,
                    **calendar_flags,
                },
            },
            "relax_candidate": {
                "state": bool(anyone_home and relax_mode),
                "reason": "anyone_home+relax_mode",
                "inputs": {
                    "anyone_home": anyone_home,
                    "relax_mode": relax_mode,
                },
            },
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
                max(0.0, now_monotonic - since_monotonic)
                if since_monotonic is not None
                else 0.0
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
    ) -> tuple[str, str, bool]:
        current = (
            current_state_before
            if current_state_before in {"sleeping", "relax", "working", "home"}
            else "home"
        )
        sleep_on = bool(self._candidate_state.get("sleep_candidate", False))
        wake_on = bool(self._candidate_state.get("wake_candidate", False))
        relax_on = bool(self._candidate_state.get("relax_candidate", False))
        work_on = bool(self._candidate_state.get("work_candidate", False))

        sleep_enter_s = _HOUSE_STATE_TIMER_DEFAULTS["sleep_enter_min"] * 60
        sleep_exit_s = _HOUSE_STATE_TIMER_DEFAULTS["sleep_exit_min"] * 60
        work_enter_s = _HOUSE_STATE_TIMER_DEFAULTS["work_enter_min"] * 60
        relax_enter_s = _HOUSE_STATE_TIMER_DEFAULTS["relax_enter_min"] * 60
        relax_exit_s = _HOUSE_STATE_TIMER_DEFAULTS["relax_exit_min"] * 60

        wake_for = self._candidate_active_for("wake_candidate", now_monotonic)
        if current == "sleeping":
            if wake_on and wake_for < sleep_exit_s:
                self._schedule_candidate_recheck(
                    schedule_recheck=schedule_recheck,
                    candidate="wake_candidate",
                    delay_s=sleep_exit_s - wake_for,
                    label="sleep_exit_threshold",
                )
                return "sleeping", "sleep_sticky_until_wake", True
            if not wake_on:
                return "sleeping", "sleep_sticky_until_wake", True

        sleep_for = self._candidate_active_for("sleep_candidate", now_monotonic)
        if sleep_on and sleep_for >= sleep_enter_s:
            return "sleeping", "sleep_candidate_confirmed", False
        if sleep_on and sleep_for < sleep_enter_s:
            self._schedule_candidate_recheck(
                schedule_recheck=schedule_recheck,
                candidate="sleep_candidate",
                delay_s=sleep_enter_s - sleep_for,
                label="sleep_enter_threshold",
            )

        if current == "relax":
            if relax_on:
                return "relax", "relax_explicit_signal", True
            relax_off_for = self._candidate_inactive_for("relax_candidate", now_monotonic)
            if relax_off_for < relax_exit_s:
                self._schedule_candidate_recheck(
                    schedule_recheck=schedule_recheck,
                    candidate="relax_candidate",
                    delay_s=relax_exit_s - relax_off_for,
                    label="relax_exit_threshold",
                )
                return "relax", "relax_sticky_exit_guard", True

        if relax_on:
            relax_reason = str(self._candidate_trace.get("relax_candidate", {}).get("reason", ""))
            if relax_reason == "anyone_home+relax_mode":
                return "relax", "relax_explicit_signal", False
            relax_for = self._candidate_active_for("relax_candidate", now_monotonic)
            if relax_for >= relax_enter_s:
                return "relax", "relax_candidate_confirmed", False
            self._schedule_candidate_recheck(
                schedule_recheck=schedule_recheck,
                candidate="relax_candidate",
                delay_s=relax_enter_s - relax_for,
                label="relax_enter_threshold",
            )

        if current == "working" and work_on:
            return "working", "work_candidate_confirmed", True

        work_for = self._candidate_active_for("work_candidate", now_monotonic)
        if work_on and work_for >= work_enter_s:
            return "working", "work_candidate_confirmed", False
        if work_on and work_for < work_enter_s:
            self._schedule_candidate_recheck(
                schedule_recheck=schedule_recheck,
                candidate="work_candidate",
                delay_s=work_enter_s - work_for,
                label="work_enter_threshold",
            )

        return "home", "default", False

    def _compute_house_signal(self, trace_key: str, entity_ids: list[str]) -> bool:
        observations = [
            self._normalizer.boolean_signal(entity_id) for entity_id in entity_ids
        ]
        fused = self._normalizer.derive(
            kind="boolean_signal",
            inputs=observations,
            strategy_cfg=build_signal_set_strategy_cfg_for_contract(
                contract=HOUSE_SIGNAL_STRATEGY_CONTRACT,
            ),
            context={"source": "house_signal", "signal": trace_key},
        )
        self._house_signals_trace[trace_key] = {
            "configured_entities": list(entity_ids),
            "source_observations": [obs.as_dict() for obs in observations],
            "fused_observation": fused.as_dict(),
            "plugin_id": fused.plugin_id,
            "used_plugin_fallback": fused.reason == "plugin_error_fallback",
        }
        return fused.state == "on"
