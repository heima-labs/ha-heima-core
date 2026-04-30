"""Presence invariant checks."""

from __future__ import annotations

from typing import Any

from ..domain_result_bag import DomainResultBag
from ..plugin_contracts import InvariantViolation


class PresenceWithoutOccupancy:
    """Detect people home while no sensorized room is occupied."""

    @property
    def check_id(self) -> str:
        return "presence_without_occupancy"

    @property
    def default_debounce_s(self) -> float:
        return 300.0

    def check(self, snapshot: Any, domain_results: DomainResultBag) -> InvariantViolation | None:
        occupancy = domain_results.get("occupancy")
        sensorized_room_count = int(getattr(occupancy, "sensorized_room_count", 0) or 0)
        if not bool(getattr(snapshot, "anyone_home", False)):
            return None
        occupied_rooms = list(getattr(snapshot, "occupied_rooms", []) or [])
        if occupied_rooms or sensorized_room_count <= 0:
            return None
        return InvariantViolation(
            check_id=self.check_id,
            severity="warning",
            anomaly_type=self.check_id,
            description="Presence is home but no sensorized room is occupied.",
            context={"sensorized_room_count": sensorized_room_count},
        )
