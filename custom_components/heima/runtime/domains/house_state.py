"""HouseStateDomain: house signals and house state resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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
        self._house_state_override: str | None = None
        self._house_state_override_set_by: str | None = None
        self._house_state_override_last_change_ts: str | None = None

    def reset(self) -> None:
        """Called on options reload - clears override."""
        self._house_state_override = None
        self._house_state_override_set_by = None
        self._house_state_override_last_change_ts = None
        self._house_signals_trace = {}

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

        derived_house_state, derived_house_reason = resolve_house_state(
            anyone_home=anyone_home,
            vacation_mode=vacation_mode,
            guest_mode=guest_mode,
            sleep_window=sleep_window,
            relax_mode=relax_mode,
            work_window=work_window,
        )
        override_active = self._house_state_override is not None
        if override_active:
            house_state = self._house_state_override  # type: ignore[assignment]
            house_reason = f"manual_override:{self._house_state_override}"
        else:
            house_state = derived_house_state
            house_reason = derived_house_reason

        return HouseStateResult(
            house_state=house_state,
            house_reason=house_reason,
            override_active=override_active,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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
