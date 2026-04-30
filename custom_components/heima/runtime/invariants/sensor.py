"""Sensor invariant checks."""

from __future__ import annotations

from typing import Any

from ..domain_result_bag import DomainResultBag
from ..plugin_contracts import InvariantViolation


class SensorStuck:
    """Detect externally supplied stuck sensor markers."""

    @property
    def check_id(self) -> str:
        return "sensor_stuck"

    @property
    def default_debounce_s(self) -> float:
        return 3600.0

    def check(self, snapshot: Any, domain_results: DomainResultBag) -> InvariantViolation | None:
        del snapshot
        status = domain_results.get("sensor_status", {})
        stuck = []
        if isinstance(status, dict):
            raw_stuck = status.get("stuck", [])
            if isinstance(raw_stuck, list):
                stuck = [str(item) for item in raw_stuck if str(item).strip()]
        if not stuck:
            return None
        return InvariantViolation(
            check_id=self.check_id,
            severity="info",
            anomaly_type=self.check_id,
            description="One or more presence or occupancy sensors appear stuck.",
            context={"entity_ids": stuck},
        )
