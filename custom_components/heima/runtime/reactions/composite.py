"""Reusable runtime composite signal matcher utilities for room-scoped reactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Literal

from homeassistant.core import HomeAssistant


StateReader = Callable[[str], str | None]
ThresholdMode = Literal[
    "rise",
    "drop",
    "above",
    "below",
    "switch_on",
    "switch_off",
    "state_change",
]


@dataclass(frozen=True)
class RuntimeCompositeSignalSpec:
    """One runtime-observed signal used inside a composite reaction."""

    name: str
    entity_ids: tuple[str, ...]
    threshold: float
    threshold_mode: ThresholdMode = "rise"
    required: bool = False


@dataclass(frozen=True)
class RuntimeCompositePatternSpec:
    """Definition of a runtime composite room-scoped matcher."""

    primary: RuntimeCompositeSignalSpec
    corroborations: tuple[RuntimeCompositeSignalSpec, ...] = ()
    correlation_window_s: int = 0


@dataclass(frozen=True)
class RuntimeCompositeMatch:
    """Result of one runtime composite evaluation cycle."""

    primary_triggered: bool
    corroborations_triggered: dict[str, bool]
    pending_since: datetime | None
    ready: bool


class RuntimeCompositeMatcher:
    """Observe numeric entity state bursts across evaluate cycles."""

    def __init__(self, hass: HomeAssistant, *, state_reader: StateReader | None = None) -> None:
        self._hass = hass
        self._state_reader = state_reader or self._default_state_reader
        self._last_values: dict[str, tuple[str, float | None, datetime]] = {}

    def reset(self) -> None:
        self._last_values.clear()

    def observe(
        self,
        *,
        now: datetime,
        pending_since: datetime | None,
        spec: RuntimeCompositePatternSpec,
    ) -> RuntimeCompositeMatch:
        primary_triggered = self._observe_signal(now=now, spec=spec.primary, window_s=spec.correlation_window_s)
        corroborations_triggered = {
            signal.name: self._observe_signal(now=now, spec=signal, window_s=spec.correlation_window_s)
            for signal in spec.corroborations
        }

        next_pending = pending_since
        if primary_triggered:
            if spec.corroborations:
                next_pending = now
            else:
                next_pending = None

        if pending_since is not None and not primary_triggered:
            age = (now - pending_since).total_seconds()
            if age > spec.correlation_window_s:
                next_pending = None

        required_signals = [signal for signal in spec.corroborations if signal.required]
        optional_signals = [signal for signal in spec.corroborations if not signal.required]

        ready = False
        if primary_triggered and not spec.corroborations:
            ready = True
        elif next_pending is not None:
            required_ok = all(corroborations_triggered.get(signal.name, False) for signal in required_signals)
            optional_ok = True if not optional_signals else any(
                corroborations_triggered.get(signal.name, False) for signal in optional_signals
            )
            if required_ok and optional_ok:
                ready = True
                next_pending = None

        return RuntimeCompositeMatch(
            primary_triggered=primary_triggered,
            corroborations_triggered=corroborations_triggered,
            pending_since=next_pending,
            ready=ready,
        )

    def _observe_signal(
        self,
        *,
        now: datetime,
        spec: RuntimeCompositeSignalSpec,
        window_s: int,
    ) -> bool:
        triggered = False
        for entity_id in spec.entity_ids:
            current = self._state_reader(entity_id)
            if current is None:
                continue
            previous = self._last_values.get(entity_id)
            current_num = _parse_numeric_state(current)
            self._last_values[entity_id] = (current, current_num, now)
            if previous is None:
                continue
            previous_raw, previous_num, previous_ts = previous
            if (now - previous_ts).total_seconds() > window_s:
                continue
            if _matches_threshold(
                previous_raw=previous_raw,
                previous_value=previous_num,
                current_raw=current,
                current_value=current_num,
                threshold=spec.threshold,
                mode=spec.threshold_mode,
            ):
                triggered = True
        return triggered

    def _default_state_reader(self, entity_id: str) -> str | None:
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return str(state.state)
        except Exception:
            return None


def parse_snapshot_ts(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _matches_threshold(
    *,
    previous_raw: str,
    previous_value: float | None,
    current_raw: str,
    current_value: float | None,
    threshold: float,
    mode: ThresholdMode,
) -> bool:
    if mode == "rise":
        if previous_value is None or current_value is None:
            return False
        return (current_value - previous_value) >= threshold
    if mode == "drop":
        if previous_value is None or current_value is None:
            return False
        return (previous_value - current_value) >= threshold
    if mode == "above":
        if previous_value is None or current_value is None:
            return False
        return previous_value < threshold and current_value >= threshold
    if mode == "below":
        if previous_value is None or current_value is None:
            return False
        return previous_value > threshold and current_value <= threshold
    previous_norm = previous_raw.strip().lower()
    current_norm = current_raw.strip().lower()
    if mode == "switch_on":
        return previous_norm != "on" and current_norm == "on"
    if mode == "switch_off":
        return previous_norm != "off" and current_norm == "off"
    if mode == "state_change":
        return previous_norm != current_norm
    return False


def _parse_numeric_state(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
