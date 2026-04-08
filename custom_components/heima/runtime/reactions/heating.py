"""Heating reactions built from accepted learning proposals."""

from __future__ import annotations

import time
from typing import Any

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction


class HeatingPreferenceReaction(HeimaReaction):
    """Apply a learned target when entering a specific house state."""

    def __init__(
        self,
        *,
        climate_entity: str,
        house_state: str,
        target_temperature: float,
        tolerance: float = 0.25,
        reaction_id: str | None = None,
    ) -> None:
        self._climate_entity = climate_entity
        self._house_state = house_state
        self._target_temperature = float(target_temperature)
        self._tolerance = float(tolerance)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._fire_count = 0
        self._last_fired_ts: float | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        current = history[-1]
        previous = history[-2] if len(history) >= 2 else None
        if current.house_state != self._house_state:
            return []
        if previous is not None and previous.house_state == current.house_state:
            return []
        if self._matches_target(current.heating_setpoint):
            return []
        self._fire_count += 1
        self._last_fired_ts = time.monotonic()
        return [self._build_step(reason=f"heating_preference:{self._house_state}")]

    def _matches_target(self, current_setpoint: float | None) -> bool:
        if current_setpoint is None:
            return False
        return abs(float(current_setpoint) - self._target_temperature) <= self._tolerance

    def _build_step(self, *, reason: str) -> ApplyStep:
        return ApplyStep(
            domain="heating",
            target=self._climate_entity,
            action="climate.set_temperature",
            params={
                "entity_id": self._climate_entity,
                "temperature": self._target_temperature,
            },
            reason=reason,
        )

    def diagnostics(self) -> dict[str, Any]:
        return {
            "house_state": self._house_state,
            "target_temperature": self._target_temperature,
            "fire_count": self._fire_count,
            "last_fired_ts": self._last_fired_ts,
        }


class HeatingEcoReaction(HeimaReaction):
    """Apply a learned eco target when entering away mode."""

    def __init__(
        self,
        *,
        climate_entity: str,
        eco_target_temperature: float,
        tolerance: float = 0.25,
        reaction_id: str | None = None,
    ) -> None:
        self._climate_entity = climate_entity
        self._eco_target_temperature = float(eco_target_temperature)
        self._tolerance = float(tolerance)
        self._reaction_id = reaction_id or self.__class__.__name__
        self._fire_count = 0
        self._last_fired_ts: float | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        current = history[-1]
        previous = history[-2] if len(history) >= 2 else None
        if current.house_state != "away":
            return []
        if previous is not None and previous.house_state == "away":
            return []
        if self._matches_target(current.heating_setpoint):
            return []
        self._fire_count += 1
        self._last_fired_ts = time.monotonic()
        return [
            ApplyStep(
                domain="heating",
                target=self._climate_entity,
                action="climate.set_temperature",
                params={
                    "entity_id": self._climate_entity,
                    "temperature": self._eco_target_temperature,
                },
                reason="heating_eco:away",
            )
        ]

    def _matches_target(self, current_setpoint: float | None) -> bool:
        if current_setpoint is None:
            return False
        return abs(float(current_setpoint) - self._eco_target_temperature) <= self._tolerance

    def diagnostics(self) -> dict[str, Any]:
        return {
            "eco_target_temperature": self._eco_target_temperature,
            "fire_count": self._fire_count,
            "last_fired_ts": self._last_fired_ts,
        }


def build_heating_preference_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> HeatingPreferenceReaction | None:
    """Build a HeatingPreferenceReaction from persisted config."""
    climate_entity = str(
        dict(engine._entry.options).get("heating", {}).get("climate_entity") or ""
    ).strip()  # noqa: SLF001
    try:
        house_state = str(cfg["house_state"]).strip()
        target_temperature = float(cfg["target_temperature"])
        tolerance = float(cfg.get("tolerance", 0.25))
        if not climate_entity or not house_state:
            raise ValueError("climate_entity or house_state missing")
    except (KeyError, TypeError, ValueError):
        return None
    return HeatingPreferenceReaction(
        climate_entity=climate_entity,
        house_state=house_state,
        target_temperature=target_temperature,
        tolerance=tolerance,
        reaction_id=proposal_id,
    )


def build_heating_eco_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> HeatingEcoReaction | None:
    """Build a HeatingEcoReaction from persisted config."""
    climate_entity = str(
        dict(engine._entry.options).get("heating", {}).get("climate_entity") or ""
    ).strip()  # noqa: SLF001
    try:
        eco_target_temperature = float(cfg["eco_target_temperature"])
        tolerance = float(cfg.get("tolerance", 0.25))
        if not climate_entity:
            raise ValueError("climate_entity missing")
    except (KeyError, TypeError, ValueError):
        return None
    return HeatingEcoReaction(
        climate_entity=climate_entity,
        eco_target_temperature=eco_target_temperature,
        tolerance=tolerance,
        reaction_id=proposal_id,
    )
