"""Typed inference signals emitted by learning modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Importance(IntEnum):
    """Signal strength used by domain resolution policies."""

    OBSERVE = 0
    SUGGEST = 1
    ASSERT = 2


@dataclass(frozen=True)
class InferenceSignal:
    """Base class for synchronous inference outputs."""

    source_id: str
    confidence: float
    importance: Importance
    ttl_s: int
    label: str


@dataclass(frozen=True)
class HouseStateSignal(InferenceSignal):
    """Predicted house state signal."""

    predicted_state: str


@dataclass(frozen=True)
class HeatingSignal(InferenceSignal):
    """Predicted heating setpoint signal."""

    predicted_setpoint: float
    house_state_context: str


@dataclass(frozen=True)
class LightingSignal(InferenceSignal):
    """Predicted lighting scene signal."""

    room_id: str
    predicted_scene: str


@dataclass(frozen=True)
class ActivitySignal(InferenceSignal):
    """Predicted composite activity signal."""

    activity_name: str
    room_id: str | None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OccupancySignal(InferenceSignal):
    """Predicted occupancy signal accepted as a v2 stub."""

    room_id: str
    predicted_occupied: bool
