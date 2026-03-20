"""Reusable runtime composite signal matcher utilities for room-scoped reactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from homeassistant.core import HomeAssistant


StateReader = Callable[[str], float | None]


@dataclass(frozen=True)
class RuntimeCompositeSignalSpec:
    """One runtime-observed signal used inside a composite reaction."""

    name: str
    entity_ids: tuple[str, ...]
    threshold: float
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
        self._last_values: dict[str, tuple[float, datetime]] = {}

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
            self._last_values[entity_id] = (current, now)
            if previous is None:
                continue
            previous_value, previous_ts = previous
            if (now - previous_ts).total_seconds() > window_s:
                continue
            if current - previous_value >= spec.threshold:
                triggered = True
        return triggered

    def _default_state_reader(self, entity_id: str) -> float | None:
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None


def parse_snapshot_ts(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except (TypeError, ValueError):
        return None
