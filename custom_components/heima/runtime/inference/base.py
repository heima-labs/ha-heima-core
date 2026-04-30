"""Base contracts for v2 inference modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .signals import InferenceSignal


@dataclass(frozen=True)
class InferenceContext:
    """Read-only per-cycle context passed to learning modules."""

    now_local: datetime
    weekday: int
    minute_of_day: int
    anyone_home: bool
    named_present: tuple[str, ...]
    room_occupancy: dict[str, bool]
    previous_house_state: str
    previous_heating_setpoint: float | None
    previous_lighting_scenes: dict[str, str]
    previous_activity_names: tuple[str, ...] = field(default_factory=tuple)


class ILearningModule(Protocol):
    """Offline/online contract for v2 learning modules."""

    @property
    def module_id(self) -> str:
        """Stable module identifier."""
        ...

    async def analyze(self, store: object) -> None:
        """Read snapshot history and update the module model."""
        ...

    def infer(self, context: InferenceContext) -> list[InferenceSignal]:
        """Return synchronous inference signals for the current cycle."""
        ...

    def diagnostics(self) -> dict[str, object]:
        """Return module diagnostics."""
        ...


class HeimaLearningModule:
    """Minimal base class for learning modules before first analysis."""

    module_id = "heima_learning_module"

    async def analyze(self, store: object) -> None:
        """Default modules have no offline model."""
        del store

    def infer(self, context: InferenceContext) -> list[InferenceSignal]:
        """Return no signals until a concrete module implements inference."""
        del context
        return []

    def diagnostics(self) -> dict[str, object]:
        """Return default diagnostics."""
        return {"module_id": self.module_id, "ready": False}
