"""Heating invariant checks."""

from __future__ import annotations

from typing import Any

from ..domain_result_bag import DomainResultBag
from ..plugin_contracts import InvariantViolation


class HeatingHomeEmpty:
    """Detect active heating while the home is away and empty."""

    @property
    def check_id(self) -> str:
        return "heating_home_empty"

    @property
    def default_debounce_s(self) -> float:
        return 600.0

    def check(self, snapshot: Any, domain_results: DomainResultBag) -> InvariantViolation | None:
        heating = domain_results.get("heating")
        trace = dict(getattr(heating, "trace", {}) or {})
        heating_state = str(trace.get("state") or "")
        target_temperature = trace.get("target_temperature")
        heating_active = bool(trace.get("apply_allowed")) or target_temperature is not None
        if not heating_active or heating_state in {"inactive", "idle"}:
            return None
        if bool(getattr(snapshot, "anyone_home", False)):
            return None
        if str(getattr(snapshot, "house_state", "") or "") != "away":
            return None
        return InvariantViolation(
            check_id=self.check_id,
            severity="warning",
            anomaly_type=self.check_id,
            description="Heating is active while the home is away and empty.",
            context={
                "heating_state": heating_state,
                "target_temperature": target_temperature,
            },
        )
