"""HeatingDomain: heating policy, vacation curve, safe apply."""

# mypy: ignore-errors

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from ..contracts import HeimaEvent
from ..domain_result_bag import DomainResultBag
from ..normalization.service import InputNormalizer
from ..state_store import CanonicalState
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)

_HEATING_MIN_SECONDS_BETWEEN_APPLIES = 60


@dataclass(frozen=True)
class HeatingDomainResult:
    """Current-cycle Heating plugin output."""

    trace: dict[str, Any]
    current_setpoint: float | None
    observed_source: str
    observed_provenance: dict[str, Any] | None


class HeatingDomain:
    """Computes heating intent and safe-apply state per evaluation cycle."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._heating_trace: dict[str, Any] = {}
        self._heating_vacation_curve_start_temp: float | None = None
        self._heating_last_target_temp: float | None = None
        self._heating_last_apply_ts: float | None = None
        self._heating_last_apply_provenance: dict[str, Any] | None = None
        self._heating_last_reported_phase: str | None = None
        self._heating_last_reported_target: float | None = None
        self._heating_last_reported_branch: str | None = None
        self._plugin_heating_config_provider: Callable[[], dict[str, Any]] | None = None
        self._plugin_events_provider: Callable[[], EventsDomain] | None = None
        self._plugin_schedule_recheck: Callable[..., None] | None = None
        self._plugin_external_outdoor_temp_provider: Callable[[], float | None] | None = None

    @property
    def domain_id(self) -> str:
        return "heating"

    @property
    def depends_on(self) -> list[str]:
        return ["house_state"]

    def bind_plugin_runtime(
        self,
        *,
        heating_config_provider: Callable[[], dict[str, Any]],
        events_provider: Callable[[], EventsDomain],
        schedule_recheck: Callable[..., None],
        external_outdoor_temp_provider: Callable[[], float | None],
    ) -> None:
        """Bind engine-owned dependencies used by the plugin wrapper."""
        self._plugin_heating_config_provider = heating_config_provider
        self._plugin_events_provider = events_provider
        self._plugin_schedule_recheck = schedule_recheck
        self._plugin_external_outdoor_temp_provider = external_outdoor_temp_provider

    def reset(self) -> None:
        """Called on options reload. Clears transient heating state."""
        self._heating_trace = {}
        self._heating_vacation_curve_start_temp = None
        self._heating_last_target_temp = None
        self._heating_last_apply_ts = None
        self._heating_last_apply_provenance = None
        self._heating_last_reported_phase = None
        self._heating_last_reported_target = None
        self._heating_last_reported_branch = None

    @property
    def trace(self) -> dict[str, Any]:
        return self._heating_trace

    def mark_applied(
        self,
        target_temperature: float,
        *,
        source: str = "",
        origin_reaction_id: str | None = None,
        origin_reaction_type: str | None = None,
        climate_entity: str | None = None,
    ) -> None:
        """Called by engine after a successful climate.set_temperature apply."""
        self._heating_last_target_temp = target_temperature
        self._heating_last_apply_ts = time.monotonic()
        self._heating_last_apply_provenance = {
            "source": source,
            "origin_reaction_id": origin_reaction_id,
            "origin_reaction_type": origin_reaction_type,
            "expected_domains": ["climate"],
            "expected_subject_ids": [climate_entity] if climate_entity else [],
        }

    def diagnostics(self) -> dict[str, Any]:
        return dict(self._heating_trace)

    # ------------------------------------------------------------------
    # Core compute
    # ------------------------------------------------------------------

    def compute(
        self,
        canonical_state: CanonicalState,
        domain_results: DomainResultBag,
        signals: list[Any] | None = None,
    ) -> HeatingDomainResult:
        """Compute heating through the plugin contract."""
        del signals
        if (
            self._plugin_heating_config_provider is None
            or self._plugin_events_provider is None
            or self._plugin_schedule_recheck is None
            or self._plugin_external_outdoor_temp_provider is None
        ):
            raise RuntimeError("Heating plugin runtime is not bound")

        house_state_result = domain_results.require("house_state")
        self.compute_policy(
            house_state=str(house_state_result.house_state),
            heating_cfg=dict(self._plugin_heating_config_provider()),
            state=canonical_state,
            events=self._plugin_events_provider(),
            schedule_recheck=self._plugin_schedule_recheck,
            ext_outdoor_temp=self._plugin_external_outdoor_temp_provider(),
        )
        return HeatingDomainResult(
            trace=dict(self._heating_trace),
            current_setpoint=self._heating_trace.get("current_setpoint"),
            observed_source=str(self._heating_trace.get("observed_source") or "unknown"),
            observed_provenance=self._heating_trace.get("observed_provenance"),
        )

    def compute_policy(
        self,
        *,
        house_state: str,
        heating_cfg: dict[str, Any],
        state: CanonicalState,
        events: EventsDomain,
        schedule_recheck: Callable[..., None],
        ext_outdoor_temp: float | None = None,
    ) -> None:
        """Compute heating intent and update canonical state in-place."""
        if not heating_cfg:
            self._heating_vacation_curve_start_temp = None
            self._heating_trace = {
                "configured": False,
                "state": "idle",
                "reason": "not_configured",
                "phase": "normal",
                "target_temperature": None,
            }
            return

        climate_entity = str(heating_cfg.get("climate_entity", "")).strip()
        apply_mode = str(
            heating_cfg.get("apply_mode", "delegate_to_scheduler") or "delegate_to_scheduler"
        )
        hvac_mode_override = heating_cfg.get("hvac_mode") or None
        branches = heating_cfg.get("override_branches", {})
        branch_cfg = dict(branches.get(house_state, {})) if isinstance(branches, dict) else {}
        branch_type = str(branch_cfg.get("branch", "disabled") or "disabled")
        previous_selected_branch = str(
            self._heating_trace.get("selected_branch", "disabled") or "disabled"
        )
        manual_guard_enabled = bool(heating_cfg.get("manual_override_guard", True))
        manual_hold = bool(state.get_binary("heima_heating_manual_hold"))
        temperature_step = self._coerce_positive_float(
            heating_cfg.get("temperature_step"), default=0.5
        )
        current_setpoint = self._current_climate_setpoint(climate_entity)
        observed_source = self._infer_observed_source(
            current_setpoint=current_setpoint,
            temperature_step=temperature_step,
        )
        observed_provenance = self._observed_provenance(observed_source=observed_source)
        outdoor_temperature = self._coerce_float_from_entity(
            heating_cfg.get("outdoor_temperature_entity")
        )
        if outdoor_temperature is None:
            outdoor_temperature = ext_outdoor_temp
        climate_preset_mode = self._coerce_text(self._state_attr(climate_entity, "preset_mode"))
        climate_manual_override = self._heating_climate_manual_override_detected(
            climate_preset_mode
        )
        manual_override_active = manual_hold or climate_manual_override
        manual_override_source = (
            "heima_manual_hold"
            if manual_hold
            else "climate_preset"
            if climate_manual_override
            else None
        )

        previous_reason = state.get_sensor("heima_heating_reason")
        heating_state = "delegated"
        reason = "normal_scheduler_delegate"
        phase = "normal"
        target_temperature: float | None = None
        apply_allowed = False
        applying_guard = False
        skip_small_delta = False
        skip_rate_limited = False
        vacation_meta: dict[str, Any] = {}

        if branch_type == "scheduler_delegate":
            reason = "scheduler_delegate_branch"
            phase = "scheduler_delegate"
        elif branch_type == "fixed_target":
            phase = "fixed_target"
            target_temperature = self._coerce_positive_float(
                branch_cfg.get("target_temperature"), default=None
            )
            if target_temperature is None:
                heating_state = "inactive"
                reason = "invalid_target_temperature"
                applying_guard = True
            else:
                (
                    heating_state,
                    reason,
                    apply_allowed,
                    applying_guard,
                    skip_small_delta,
                    skip_rate_limited,
                ) = self._finalize_heating_target(
                    branch_reason="fixed_target_branch",
                    target_temperature=target_temperature,
                    apply_mode=apply_mode,
                    manual_override_active=manual_override_active
                    if manual_guard_enabled
                    else False,
                    current_setpoint=current_setpoint,
                    temperature_step=temperature_step,
                )
        elif branch_type == "vacation_curve":
            if previous_selected_branch != "vacation_curve":
                self._heating_vacation_curve_start_temp = current_setpoint
            (
                target_temperature,
                phase,
                vacation_meta,
                vacation_error,
            ) = self._resolve_vacation_curve_target(
                heating_cfg=heating_cfg,
                branch_cfg=branch_cfg,
                outdoor_temperature=outdoor_temperature,
                temperature_step=temperature_step,
                start_temperature=self._heating_vacation_curve_start_temp,
            )
            if vacation_error:
                heating_state = "inactive"
                reason = vacation_error
                applying_guard = True
            elif target_temperature is None:
                heating_state = "inactive"
                reason = "vacation_curve_not_resolved"
                applying_guard = True
            else:
                (
                    heating_state,
                    reason,
                    apply_allowed,
                    applying_guard,
                    skip_small_delta,
                    skip_rate_limited,
                ) = self._finalize_heating_target(
                    branch_reason="vacation_curve_branch",
                    target_temperature=target_temperature,
                    apply_mode=apply_mode,
                    manual_override_active=manual_override_active
                    if manual_guard_enabled
                    else False,
                    current_setpoint=current_setpoint,
                    temperature_step=temperature_step,
                )
        else:
            branch_type = "disabled"

        if branch_type != "vacation_curve":
            self._heating_vacation_curve_start_temp = None

        state.set_sensor("heima_heating_state", heating_state)
        state.set_sensor("heima_heating_reason", reason)
        state.set_sensor("heima_heating_phase", phase)
        state.set_sensor("heima_heating_branch", branch_type)
        state.set_sensor("heima_heating_target_temp", target_temperature)
        state.set_sensor("heima_heating_current_setpoint", current_setpoint)
        state.set_sensor("heima_heating_last_applied_target", self._heating_last_target_temp)
        state.set_binary("heima_heating_applying_guard", applying_guard)

        self._heating_trace = {
            "configured": True,
            "climate_entity": climate_entity,
            "apply_mode": apply_mode,
            "hvac_mode_override": hvac_mode_override,
            "current_house_state": house_state,
            "selected_branch": branch_type,
            "current_setpoint": current_setpoint,
            "observed_source": observed_source,
            "observed_provenance": observed_provenance,
            "outdoor_temperature": outdoor_temperature,
            "target_temperature": target_temperature,
            "temperature_step": temperature_step,
            "manual_override_guard_enabled": manual_guard_enabled,
            "manual_hold": manual_hold,
            "climate_preset_mode": climate_preset_mode,
            "climate_manual_override_detected": climate_manual_override,
            "manual_override_active": manual_override_active if manual_guard_enabled else False,
            "manual_override_source": manual_override_source if manual_guard_enabled else None,
            "state": heating_state,
            "reason": reason,
            "phase": phase,
            "apply_allowed": apply_allowed,
            "applying_guard": applying_guard,
            "skip_small_delta": skip_small_delta,
            "skip_rate_limited": skip_rate_limited,
            "rate_limit_window_s": _HEATING_MIN_SECONDS_BETWEEN_APPLIES,
            "last_applied_target": self._heating_last_target_temp,
            "last_apply_ts": self._heating_last_apply_ts,
            "vacation": dict(vacation_meta),
            "vacation_curve_start_temp": self._heating_vacation_curve_start_temp,
        }

        self._queue_heating_runtime_events(
            selected_branch=branch_type,
            previous_reason=str(previous_reason) if previous_reason not in (None, "") else None,
            reason=reason,
            phase=phase,
            manual_override_source=manual_override_source if manual_guard_enabled else None,
            target_temperature=target_temperature,
            apply_allowed=apply_allowed,
            skip_small_delta=skip_small_delta,
            events=events,
        )
        self._schedule_heating_recheck(
            selected_branch=branch_type,
            phase=phase,
            vacation_meta=vacation_meta,
            temperature_step=temperature_step,
            schedule_recheck=schedule_recheck,
        )

    def _infer_observed_source(
        self,
        *,
        current_setpoint: float | None,
        temperature_step: float,
    ) -> str:
        """Infer whether the currently observed thermostat state likely came from Heima.

        The learning recorder should classify the observed setpoint, not the currently
        planned target. If the thermostat now reflects the last target that Heima
        successfully applied, attribute it to `heima`; otherwise treat it as `user`.
        """
        if (
            current_setpoint is None
            or self._heating_last_target_temp is None
            or self._heating_last_apply_ts is None
        ):
            return "user"
        tolerance = max(0.05, float(temperature_step) / 2.0)
        if abs(float(current_setpoint) - float(self._heating_last_target_temp)) <= tolerance:
            return "heima"
        return "user"

    def _observed_provenance(self, *, observed_source: str) -> dict[str, Any] | None:
        if observed_source != "heima":
            return None
        if not isinstance(self._heating_last_apply_provenance, dict):
            return None
        return dict(self._heating_last_apply_provenance)

    # ------------------------------------------------------------------
    # Event queuing
    # ------------------------------------------------------------------

    def _queue_heating_runtime_events(
        self,
        *,
        selected_branch: str,
        previous_reason: str | None,
        reason: str,
        phase: str,
        manual_override_source: str | None,
        target_temperature: float | None,
        apply_allowed: bool,
        skip_small_delta: bool,
        events: EventsDomain,
    ) -> None:
        if self._heating_last_reported_branch is None:
            self._heating_last_reported_branch = selected_branch
        elif self._heating_last_reported_branch != selected_branch:
            events.queue_event(
                HeimaEvent(
                    type="heating.branch_changed",
                    key="heating.branch_changed",
                    severity="info",
                    title="Heating branch changed",
                    message=f"Heating branch changed to '{selected_branch}'.",
                    context={
                        "previous": self._heating_last_reported_branch,
                        "current": selected_branch,
                    },
                )
            )
            self._heating_last_reported_branch = selected_branch

        if selected_branch == "vacation_curve" and self._heating_last_reported_phase != phase:
            events.queue_event(
                HeimaEvent(
                    type="heating.vacation_phase_changed",
                    key="heating.vacation_phase_changed",
                    severity="info",
                    title="Heating vacation phase changed",
                    message=f"Heating vacation phase changed to '{phase}'.",
                    context={"phase": phase},
                )
            )
            self._heating_last_reported_phase = phase
        elif selected_branch != "vacation_curve":
            self._heating_last_reported_phase = None

        if (
            apply_allowed
            and target_temperature is not None
            and self._heating_last_reported_target != target_temperature
        ):
            events.queue_event(
                HeimaEvent(
                    type="heating.target_changed",
                    key="heating.target_changed",
                    severity="info",
                    title="Heating target changed",
                    message=f"Heating target updated to {target_temperature}.",
                    context={
                        "target_temperature": target_temperature,
                        "branch": selected_branch,
                        "phase": phase,
                    },
                )
            )
            self._heating_last_reported_target = target_temperature

        if reason == "manual_override_blocked" and previous_reason != "manual_override_blocked":
            events.queue_event(
                HeimaEvent(
                    type="heating.manual_override_blocked",
                    key="heating.manual_override_blocked",
                    severity="info",
                    title="Heating blocked by manual override",
                    message="Heating apply skipped because manual override is active.",
                    context={
                        "branch": selected_branch,
                        "source": manual_override_source or "unknown",
                    },
                )
            )

        if skip_small_delta and previous_reason != "small_delta_skip":
            events.queue_event(
                HeimaEvent(
                    type="heating.apply_skipped_small_delta",
                    key="heating.apply_skipped_small_delta",
                    severity="info",
                    title="Heating apply skipped",
                    message="Heating target change is below the configured temperature step.",
                    context={
                        "branch": selected_branch,
                        "target_temperature": target_temperature,
                    },
                )
            )

        if reason == "apply_rate_limited" and previous_reason != "apply_rate_limited":
            events.queue_event(
                HeimaEvent(
                    type="heating.apply_rate_limited",
                    key="heating.apply_rate_limited",
                    severity="info",
                    title="Heating apply rate-limited",
                    message="Heating apply skipped because the minimum apply interval is still active.",
                    context={
                        "branch": selected_branch,
                        "target_temperature": target_temperature,
                    },
                )
            )

        if (
            reason == "vacation_bindings_unavailable"
            and previous_reason != "vacation_bindings_unavailable"
        ):
            events.queue_event(
                HeimaEvent(
                    type="heating.vacation_bindings_unavailable",
                    key="heating.vacation_bindings_unavailable",
                    severity="warn",
                    title="Heating vacation bindings unavailable",
                    message="Heating vacation branch could not compute a target because required bindings are unavailable.",
                    context={"branch": selected_branch},
                )
            )

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def _schedule_heating_recheck(
        self,
        *,
        selected_branch: str,
        phase: str,
        vacation_meta: dict[str, Any],
        temperature_step: float,
        schedule_recheck: Callable[..., None],
    ) -> None:
        if selected_branch != "vacation_curve" or not vacation_meta:
            return
        delay_s = self._heating_vacation_recheck_delay_s(
            phase=phase,
            vacation_meta=vacation_meta,
            temperature_step=temperature_step,
        )
        if delay_s is None:
            return
        schedule_recheck(
            job_id="heating:vacation_curve",
            deadline=time.monotonic() + delay_s,
            owner="heating",
            label="Heating vacation curve recheck",
        )

    @staticmethod
    def _heating_vacation_recheck_delay_s(
        *,
        phase: str,
        vacation_meta: dict[str, Any],
        temperature_step: float,
    ) -> float | None:
        candidates: list[float] = []
        if phase == "ramp_down":
            remaining_h = float(vacation_meta["ramp_down_h"]) - float(
                vacation_meta["hours_from_start"]
            )
            if remaining_h > 0:
                candidates.append(remaining_h * 3600)
            exact_change = HeatingDomain._heating_vacation_next_quantized_change_delay_s(
                phase=phase,
                vacation_meta=vacation_meta,
                temperature_step=temperature_step,
            )
            if exact_change is not None:
                candidates.append(exact_change)
        elif phase == "cruise":
            remaining_h = float(vacation_meta["hours_to_end"]) - float(vacation_meta["ramp_up_h"])
            if remaining_h > 0:
                candidates.append(remaining_h * 3600)
        elif phase == "ramp_up":
            remaining_h = float(vacation_meta["hours_to_end"])
            if remaining_h > 0:
                candidates.append(remaining_h * 3600)
            exact_change = HeatingDomain._heating_vacation_next_quantized_change_delay_s(
                phase=phase,
                vacation_meta=vacation_meta,
                temperature_step=temperature_step,
            )
            if exact_change is not None:
                candidates.append(exact_change)
        if not candidates:
            return None
        delay_s = min(c for c in candidates if c > 0)
        return max(1.0, float(delay_s))

    @staticmethod
    def _heating_vacation_next_quantized_change_delay_s(
        *,
        phase: str,
        vacation_meta: dict[str, Any],
        temperature_step: float,
    ) -> float | None:
        if temperature_step <= 0:
            return None
        raw_target = float(vacation_meta.get("raw_target", 0.0))
        quantized_target = float(vacation_meta.get("quantized_target", 0.0))
        slope_per_hour = 0.0
        if phase == "ramp_down":
            ramp_down_h = float(vacation_meta.get("ramp_down_h", 0.0))
            if ramp_down_h <= 0:
                return None
            slope_per_hour = (
                float(vacation_meta.get("min_safety", 0.0))
                - float(vacation_meta.get("start_temp", 0.0))
            ) / ramp_down_h
        elif phase == "ramp_up":
            ramp_up_h = float(vacation_meta.get("ramp_up_h", 0.0))
            if ramp_up_h <= 0:
                return None
            slope_per_hour = (
                float(vacation_meta.get("return_preheat_target", 0.0))
                - float(vacation_meta.get("min_safety", 0.0))
            ) / ramp_up_h
        else:
            return None
        if slope_per_hour == 0:
            return None
        half_step = temperature_step / 2.0
        if slope_per_hour < 0:
            threshold = quantized_target - half_step
            if raw_target < threshold:
                threshold -= temperature_step
            delta = raw_target - threshold
        else:
            threshold = quantized_target + half_step
            if raw_target > threshold:
                threshold += temperature_step
            delta = threshold - raw_target
        if delta <= 0:
            return 1.0
        return max(1.0, float(delta / abs(slope_per_hour) * 3600))

    # ------------------------------------------------------------------
    # Target resolution helpers
    # ------------------------------------------------------------------

    def _finalize_heating_target(
        self,
        *,
        branch_reason: str,
        target_temperature: float,
        apply_mode: str,
        manual_override_active: bool,
        current_setpoint: float | None,
        temperature_step: float,
    ) -> tuple[str, str, bool, bool, bool, bool]:
        if apply_mode != "set_temperature":
            return ("delegated", "apply_mode_delegate_to_scheduler", False, False, False, False)
        if manual_override_active:
            return ("blocked", "manual_override_blocked", False, True, False, False)
        diff = (
            None
            if current_setpoint is None
            else abs(float(target_temperature) - float(current_setpoint))
        )
        if diff is not None and diff < temperature_step:
            return ("idle", "small_delta_skip", False, True, True, False)
        if (
            self._heating_last_target_temp == target_temperature
            and self._heating_last_apply_ts is not None
        ):
            if (
                time.monotonic() - self._heating_last_apply_ts
            ) < _HEATING_MIN_SECONDS_BETWEEN_APPLIES:
                return ("idle", "apply_rate_limited", False, True, False, True)
        return ("target_active", branch_reason, True, False, False, False)

    def _resolve_vacation_curve_target(
        self,
        *,
        heating_cfg: dict[str, Any],
        branch_cfg: dict[str, Any],
        outdoor_temperature: float | None,
        temperature_step: float,
        start_temperature: float | None,
    ) -> tuple[float | None, str, dict[str, Any], str | None]:
        hours_from = self._coerce_float_from_entity(
            heating_cfg.get("vacation_hours_from_start_entity")
        )
        hours_to = self._coerce_float_from_entity(heating_cfg.get("vacation_hours_to_end_entity"))
        total_hours = self._coerce_float_from_entity(heating_cfg.get("vacation_total_hours_entity"))
        explicit_is_long = self._coerce_bool_from_entity(heating_cfg.get("vacation_is_long_entity"))
        ramp_down = self._coerce_non_negative_float(
            branch_cfg.get("vacation_ramp_down_h"), default=None
        )
        ramp_up = self._coerce_non_negative_float(
            branch_cfg.get("vacation_ramp_up_h"), default=None
        )
        min_total_hours_for_ramp = self._coerce_non_negative_float(
            branch_cfg.get("vacation_min_total_hours_for_ramp"), default=None
        )
        min_temp = self._coerce_positive_float(branch_cfg.get("vacation_min_temp"), default=None)
        return_preheat_temp = self._coerce_positive_float(
            branch_cfg.get("vacation_comfort_temp"), default=None
        )
        start_temp = self._coerce_positive_float(start_temperature, default=None)

        if None in (
            hours_from,
            hours_to,
            total_hours,
            ramp_down,
            ramp_up,
            min_total_hours_for_ramp,
            min_temp,
            return_preheat_temp,
            start_temp,
            outdoor_temperature,
        ):
            return (None, "vacation_curve", {}, "vacation_bindings_unavailable")

        is_long = (
            explicit_is_long
            if explicit_is_long is not None
            else bool(total_hours >= min_total_hours_for_ramp)
        )
        min_safety = self._heating_vacation_min_safety(
            min_temp=min_temp, outdoor_temperature=outdoor_temperature
        )

        if not is_long:
            phase = "eco_only"
            raw_target = min_safety
        else:
            eco = min_safety
            raw_target = eco
            phase = "cruise"
            if total_hours <= 0:
                phase = "cruise"
            elif ramp_down > 0 and hours_from < ramp_down:
                raw_target = start_temp + (eco - start_temp) * (hours_from / ramp_down)
                phase = "ramp_down"
            elif ramp_up > 0 and hours_to < ramp_up:
                raw_target = eco + (return_preheat_temp - eco) * (1 - (hours_to / ramp_up))
                phase = "ramp_up"

        quantized = round(raw_target / temperature_step) * temperature_step
        target = round(float(quantized), 2)
        return (
            target,
            phase,
            {
                "hours_from_start": hours_from,
                "hours_to_end": hours_to,
                "total_hours": total_hours,
                "is_long": is_long,
                "ramp_down_h": ramp_down,
                "ramp_up_h": ramp_up,
                "min_total_hours_for_ramp": min_total_hours_for_ramp,
                "min_temp": min_temp,
                "return_preheat_target": return_preheat_temp,
                "start_temp": start_temp,
                "raw_target": round(float(raw_target), 4),
                "quantized_target": target,
                "min_safety": min_safety,
                "scheduler_handoff_on_exit": True,
            },
            None,
        )

    @staticmethod
    def _heating_vacation_min_safety(*, min_temp: float, outdoor_temperature: float) -> float:
        if outdoor_temperature <= 0:
            return max(min_temp, 17.0)
        if outdoor_temperature <= 3:
            return max(min_temp, 16.5)
        return min_temp

    # ------------------------------------------------------------------
    # HA state helpers
    # ------------------------------------------------------------------

    def _current_climate_setpoint(self, entity_id: str) -> float | None:
        return self._coerce_positive_float(self._state_attr(entity_id, "temperature"), default=None)

    @staticmethod
    def _heating_climate_manual_override_detected(preset_mode: str | None) -> bool:
        if not preset_mode:
            return False
        normalized = preset_mode.casefold().replace(" ", "").replace("_", "").replace("-", "")
        if normalized in {"", "none", "null", "schedule", "scheduled", "auto"}:
            return False
        return normalized in {
            "hold",
            "manual",
            "manualhold",
            "override",
            "permanenthold",
            "temporaryhold",
        }

    def _state_attr(self, entity_id: str | None, attr_name: str) -> Any:
        if not entity_id:
            return None
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        attrs = getattr(state, "attributes", {}) or {}
        if not isinstance(attrs, dict):
            return None
        return attrs.get(attr_name)

    def _coerce_float_from_entity(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self._hass.states.get(str(entity_id))
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _coerce_bool_from_entity(self, entity_id: str | None) -> bool | None:
        if not entity_id:
            return None
        if self._hass.states.get(str(entity_id)) is None:
            return None
        obs = self._normalizer.boolean_signal(str(entity_id))
        if obs.state == "unknown":
            return None
        return obs.state == "on"

    @staticmethod
    def _coerce_text(value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _coerce_positive_float(value: Any, *, default: float | None) -> float | None:
        if value in (None, ""):
            return default
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if parsed <= 0:
            return default
        return parsed

    @staticmethod
    def _coerce_non_negative_float(value: Any, *, default: float | None) -> float | None:
        if value in (None, ""):
            return default
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if parsed < 0:
            return default
        return parsed
