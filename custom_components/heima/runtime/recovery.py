"""Runtime recovery state classification for startup and power instability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

RecoveryState = Literal[
    "normal",
    "startup_recovery",
    "power_recovery",
    "degraded_recovery",
    "recovery_settling",
]

RecoveryReason = Literal[
    "normal",
    "startup_requested",
    "critical_entities_unavailable",
    "critical_entities_restored",
    "critical_entities_flapping",
    "degraded_timeout",
    "stabilized",
]

CheckpointDifferenceKind = Literal["unknown_during_downtime", "power_restore_candidate"]


@dataclass(frozen=True)
class CriticalEntityState:
    """Availability-relevant state for one entity used by recovery classification."""

    entity_id: str
    state: str
    domain: str = ""

    @property
    def available(self) -> bool:
        return self.state not in {"unavailable", "unknown", ""}

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "domain": self.domain,
            "state": self.state,
            "available": self.available,
        }


@dataclass(frozen=True)
class CheckpointDifference:
    """Difference between latest checkpoint and current HA state."""

    entity_id: str
    domain: str
    checkpoint_state: str
    current_state: str
    kind: CheckpointDifferenceKind

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "domain": self.domain,
            "checkpoint_state": self.checkpoint_state,
            "current_state": self.current_state,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class CheckpointRecoveryStatus:
    """Recovery-facing status of the latest runtime checkpoint."""

    available: bool = False
    usable: bool = False
    stale: bool = False
    checkpoint_id: str | None = None
    age_s: float | None = None
    reason: str = "missing"
    ha_started_at: str | None = None
    heima_started_at: str | None = None
    ha_restarted_since_checkpoint: bool | None = None
    differences: tuple[CheckpointDifference, ...] = ()

    @property
    def difference_count(self) -> int:
        return len(self.differences)

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "usable": self.usable,
            "stale": self.stale,
            "checkpoint_id": self.checkpoint_id,
            "age_s": self.age_s,
            "reason": self.reason,
            "ha_started_at": self.ha_started_at,
            "heima_started_at": self.heima_started_at,
            "ha_restarted_since_checkpoint": self.ha_restarted_since_checkpoint,
            "difference_count": self.difference_count,
            "differences": [difference.as_dict() for difference in self.differences],
        }


@dataclass(frozen=True)
class RecoveryConfig:
    """Configuration knobs for runtime recovery classification."""

    critical_entity_unavailable_ratio: float = 0.35
    startup_stabilization_s: float = 120.0
    power_restore_stabilization_s: float = 60.0
    checkpoint_freshness_s: float = 15 * 60.0
    degraded_timeout_s: float = 10 * 60.0


@dataclass(frozen=True)
class RecoveryEvaluationInput:
    """Inputs required to classify recovery state for one evaluation cycle."""

    now_monotonic: float
    now_utc: str | None = None
    critical_entities: tuple[CriticalEntityState, ...] = ()
    startup_requested: bool = False
    stable_snapshot_available: bool = False
    reconciliation_pending: bool = False
    checkpoint_status: CheckpointRecoveryStatus = field(default_factory=CheckpointRecoveryStatus)


@dataclass(frozen=True)
class RecoveryContext:
    """Read-only recovery context exposed to runtime consumers."""

    state: RecoveryState = "normal"
    reason: RecoveryReason = "normal"
    active: bool = False
    started_at_monotonic: float | None = None
    settling_started_at_monotonic: float | None = None
    degraded_started_at_monotonic: float | None = None
    started_at: str | None = None
    settling_started_at: str | None = None
    degraded_started_at: str | None = None
    stabilization_deadline_at: str | None = None
    degraded_timeout_at: str | None = None
    parent_state: RecoveryState | None = None
    unavailable_ratio: float = 0.0
    unavailable_count: int = 0
    critical_entity_count: int = 0
    stabilization_deadline_monotonic: float | None = None
    stable_snapshot_available: bool = False
    reconciliation_pending: bool = False
    critical_entities: tuple[CriticalEntityState, ...] = field(default_factory=tuple)
    checkpoint_status: CheckpointRecoveryStatus = field(default_factory=CheckpointRecoveryStatus)

    def as_runtime_context(self) -> dict[str, Any]:
        """Return the reserved engine-owned runtime context namespace."""
        return {
            "runtime.recovery.state": self.state,
            "runtime.recovery.reason": self.reason,
            "runtime.recovery.active": self.active,
            "runtime.recovery.unavailable_ratio": self.unavailable_ratio,
            "runtime.recovery.unavailable_count": self.unavailable_count,
            "runtime.recovery.critical_entity_count": self.critical_entity_count,
            "runtime.recovery.stabilization_deadline_monotonic": (
                self.stabilization_deadline_monotonic
            ),
            "runtime.recovery.started_at": self.started_at,
            "runtime.recovery.settling_started_at": self.settling_started_at,
            "runtime.recovery.degraded_started_at": self.degraded_started_at,
            "runtime.recovery.stabilization_deadline_at": self.stabilization_deadline_at,
            "runtime.recovery.degraded_timeout_at": self.degraded_timeout_at,
            "runtime.recovery.stable_snapshot_available": self.stable_snapshot_available,
            "runtime.recovery.reconciliation_pending": self.reconciliation_pending,
            "runtime.recovery.checkpoint.available": self.checkpoint_status.available,
            "runtime.recovery.checkpoint.usable": self.checkpoint_status.usable,
            "runtime.recovery.checkpoint.stale": self.checkpoint_status.stale,
            "runtime.recovery.checkpoint.reason": self.checkpoint_status.reason,
            "runtime.recovery.checkpoint.age_s": self.checkpoint_status.age_s,
            "runtime.recovery.checkpoint.difference_count": (
                self.checkpoint_status.difference_count
            ),
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "active": self.active,
            "started_at_monotonic": self.started_at_monotonic,
            "settling_started_at_monotonic": self.settling_started_at_monotonic,
            "degraded_started_at_monotonic": self.degraded_started_at_monotonic,
            "started_at": self.started_at,
            "settling_started_at": self.settling_started_at,
            "degraded_started_at": self.degraded_started_at,
            "parent_state": self.parent_state,
            "unavailable_ratio": self.unavailable_ratio,
            "unavailable_count": self.unavailable_count,
            "critical_entity_count": self.critical_entity_count,
            "stabilization_deadline_monotonic": self.stabilization_deadline_monotonic,
            "stabilization_deadline_at": self.stabilization_deadline_at,
            "degraded_timeout_at": self.degraded_timeout_at,
            "stable_snapshot_available": self.stable_snapshot_available,
            "reconciliation_pending": self.reconciliation_pending,
            "critical_entities": [entity.as_dict() for entity in self.critical_entities],
            "checkpoint": self.checkpoint_status.as_dict(),
        }


class RecoveryManager:
    """State machine for runtime recovery classification.

    This component only classifies recovery state. AQ1 intentionally does not
    suppress learning, block applies, or alter manual-hold behavior.
    """

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        self._config = config or RecoveryConfig()
        self._context = RecoveryContext()

    @property
    def context(self) -> RecoveryContext:
        return self._context

    @property
    def config(self) -> RecoveryConfig:
        return self._config

    def evaluate(self, inputs: RecoveryEvaluationInput) -> RecoveryContext:
        entities = tuple(inputs.critical_entities)
        total = len(entities)
        unavailable = sum(1 for entity in entities if not entity.available)
        ratio = (unavailable / total) if total else 0.0
        above_threshold = total > 0 and ratio >= self._config.critical_entity_unavailable_ratio

        current = self._context
        state = current.state
        reason: RecoveryReason = "normal"
        started_at = current.started_at_monotonic
        settling_started_at = current.settling_started_at_monotonic
        degraded_started_at = current.degraded_started_at_monotonic
        started_at_wall = current.started_at
        settling_started_at_wall = current.settling_started_at
        degraded_started_at_wall = current.degraded_started_at
        parent_state = current.parent_state

        if state == "normal":
            if inputs.startup_requested:
                state = "startup_recovery"
                reason = "startup_requested"
                started_at = inputs.now_monotonic
                started_at_wall = inputs.now_utc
                settling_started_at = None
                settling_started_at_wall = None
                degraded_started_at = None
                degraded_started_at_wall = None
                parent_state = "startup_recovery"
            elif above_threshold:
                state = "power_recovery"
                reason = "critical_entities_unavailable"
                started_at = inputs.now_monotonic
                started_at_wall = inputs.now_utc
                settling_started_at = None
                settling_started_at_wall = None
                degraded_started_at = None
                degraded_started_at_wall = None
                parent_state = "power_recovery"
        elif state in {"startup_recovery", "power_recovery"}:
            parent_state = state
            if above_threshold:
                reason = "critical_entities_unavailable"
                if self._stabilization_elapsed(state, started_at, inputs.now_monotonic):
                    state = "degraded_recovery"
                    reason = "degraded_timeout"
                    degraded_started_at = inputs.now_monotonic
                    degraded_started_at_wall = inputs.now_utc
            else:
                state = "recovery_settling"
                reason = "critical_entities_restored"
                settling_started_at = inputs.now_monotonic
                settling_started_at_wall = inputs.now_utc
                degraded_started_at = None
                degraded_started_at_wall = None
        elif state == "degraded_recovery":
            if above_threshold:
                reason = "degraded_timeout"
            else:
                state = "recovery_settling"
                reason = "critical_entities_restored"
                settling_started_at = inputs.now_monotonic
                settling_started_at_wall = inputs.now_utc
                degraded_started_at = None
                degraded_started_at_wall = None
        elif state == "recovery_settling":
            fallback_parent = (
                parent_state
                if parent_state in {"startup_recovery", "power_recovery"}
                else "power_recovery"
            )
            if above_threshold:
                state = fallback_parent
                reason = "critical_entities_flapping"
                settling_started_at = None
                settling_started_at_wall = None
            elif self._can_exit_settling(
                settling_started_at=settling_started_at,
                now_monotonic=inputs.now_monotonic,
                parent_state=fallback_parent,
                stable_snapshot_available=inputs.stable_snapshot_available,
                reconciliation_pending=inputs.reconciliation_pending,
            ):
                state = "normal"
                reason = "stabilized"
                started_at = None
                settling_started_at = None
                degraded_started_at = None
                started_at_wall = None
                settling_started_at_wall = None
                degraded_started_at_wall = None
                parent_state = None
            else:
                reason = "critical_entities_restored"

        deadline = self._stabilization_deadline(
            state=state,
            started_at=started_at,
            settling_started_at=settling_started_at,
            parent_state=parent_state,
        )
        degraded_deadline = (
            degraded_started_at + self._config.degraded_timeout_s
            if state == "degraded_recovery" and degraded_started_at is not None
            else None
        )
        self._context = RecoveryContext(
            state=state,
            reason=reason,
            active=state != "normal",
            started_at_monotonic=started_at,
            settling_started_at_monotonic=settling_started_at,
            degraded_started_at_monotonic=degraded_started_at,
            started_at=started_at_wall,
            settling_started_at=settling_started_at_wall,
            degraded_started_at=degraded_started_at_wall,
            parent_state=parent_state,
            unavailable_ratio=ratio,
            unavailable_count=unavailable,
            critical_entity_count=total,
            stabilization_deadline_monotonic=deadline,
            stabilization_deadline_at=_deadline_at(
                now_monotonic=inputs.now_monotonic,
                now_utc=inputs.now_utc,
                deadline_monotonic=deadline,
            ),
            degraded_timeout_at=_deadline_at(
                now_monotonic=inputs.now_monotonic,
                now_utc=inputs.now_utc,
                deadline_monotonic=degraded_deadline,
            ),
            stable_snapshot_available=inputs.stable_snapshot_available,
            reconciliation_pending=inputs.reconciliation_pending,
            critical_entities=entities,
            checkpoint_status=inputs.checkpoint_status,
        )
        return self._context

    def diagnostics(self) -> dict[str, Any]:
        return self._context.diagnostics()

    def _stabilization_elapsed(
        self,
        state: RecoveryState,
        started_at: float | None,
        now_monotonic: float,
    ) -> bool:
        if started_at is None:
            return False
        return (now_monotonic - started_at) >= self._stabilization_window_s(state)

    def _can_exit_settling(
        self,
        *,
        settling_started_at: float | None,
        now_monotonic: float,
        parent_state: RecoveryState,
        stable_snapshot_available: bool,
        reconciliation_pending: bool,
    ) -> bool:
        if settling_started_at is None or reconciliation_pending or not stable_snapshot_available:
            return False
        return (now_monotonic - settling_started_at) >= self._stabilization_window_s(parent_state)

    def _stabilization_deadline(
        self,
        *,
        state: RecoveryState,
        started_at: float | None,
        settling_started_at: float | None,
        parent_state: RecoveryState | None,
    ) -> float | None:
        if state in {"startup_recovery", "power_recovery"} and started_at is not None:
            return started_at + self._stabilization_window_s(state)
        if state == "recovery_settling" and settling_started_at is not None:
            source_state = (
                parent_state
                if parent_state in {"startup_recovery", "power_recovery"}
                else "power_recovery"
            )
            return settling_started_at + self._stabilization_window_s(source_state)
        return None

    def _stabilization_window_s(self, state: RecoveryState) -> float:
        if state == "startup_recovery":
            return self._config.startup_stabilization_s
        return self._config.power_restore_stabilization_s


def _deadline_at(
    *,
    now_monotonic: float,
    now_utc: str | None,
    deadline_monotonic: float | None,
) -> str | None:
    if deadline_monotonic is None or not now_utc:
        return None
    try:
        parsed = datetime.fromisoformat(now_utc)
    except ValueError:
        return None
    delta_s = max(0.0, float(deadline_monotonic) - float(now_monotonic))
    return (parsed + timedelta(seconds=delta_s)).isoformat()
