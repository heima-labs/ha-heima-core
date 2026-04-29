"""ExternalContext: normalized slot values from Heima adapter entities."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Canonical slot names — must match the contract spec
SLOTS = (
    "outdoor_temp",
    "outdoor_humidity",
    "outdoor_lux",
    "wind_speed",
    "rain_last_1h",
    "rain_forecast_next_6h",
    "weather_condition",
    "weather_alert_level",
    "weather_alert_phenomena",
)


@dataclass
class ExternalContext:
    outdoor_temp: float | None = None
    outdoor_humidity: float | None = None
    outdoor_lux: float | None = None
    wind_speed: float | None = None
    rain_last_1h: float | None = None
    rain_forecast_next_6h: float | None = None
    weather_condition: str | None = None
    weather_alert_level: int | None = None
    weather_alert_phenomena: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> ExternalContext:
        return cls()


class ExternalContextNormalizer:
    """Reads adapter entities from HA state and produces an ExternalContext.

    Config mapping (from OPT_EXTERNAL_CONTEXT options key):
        { "outdoor_temp": "sensor.heima_ext_owm_outdoor_temp", ... }

    Any slot not present in the mapping is left as None (feature disabled).
    Unavailable or unknown entity states are treated as None.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._mapping: dict[str, str] = {}  # slot -> entity_id

    def update_config(self, options: dict[str, Any]) -> None:
        from ..const import OPT_EXTERNAL_CONTEXT

        raw = options.get(OPT_EXTERNAL_CONTEXT) or {}
        self._mapping = {k: v for k, v in raw.items() if v and k in SLOTS}

    def compute(self) -> ExternalContext:
        ctx = ExternalContext()

        for slot, entity_id in self._mapping.items():
            value = self._read(entity_id, slot)
            if value is None:
                continue
            try:
                if slot == "weather_condition":
                    setattr(ctx, slot, str(value))
                elif slot == "weather_alert_level":
                    setattr(ctx, slot, int(float(value)))
                elif slot == "weather_alert_phenomena":
                    raw = str(value).strip()
                    setattr(ctx, slot, [p for p in raw.split(",") if p] if raw else [])
                else:
                    setattr(ctx, slot, float(value))
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "ExternalContext: cannot coerce slot '%s' from entity '%s' (value=%r)",
                    slot,
                    entity_id,
                    value,
                )

        return ctx

    def _read(self, entity_id: str, slot: str) -> str | None:
        state = self._hass.states.get(entity_id)
        if state is None:
            _LOGGER.debug("ExternalContext: entity '%s' (slot '%s') not found", entity_id, slot)
            return None
        if state.state in ("unavailable", "unknown"):
            return None
        return state.state
