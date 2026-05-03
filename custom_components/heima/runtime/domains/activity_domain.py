"""Core ActivityDomain and hysteresis state machine."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from ..contracts import HeimaEvent
from ..inference import ActivitySignal, Importance
from ..plugin_contracts import IActivityDetector
from ..state_store import CanonicalState

ActivityPhase = Literal["absent", "candidate", "active", "grace"]


@dataclass(frozen=True)
class Activity:
    """Observed activity emitted by ActivityDomain."""

    name: str
    confidence: float
    room_id: str | None
    started_at: float
    duration_s: float
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActivityResult:
    """ActivityDomain per-cycle output."""

    active: tuple[Activity, ...] = ()
    candidates: tuple[Activity, ...] = ()


@dataclass(frozen=True)
class ActivityDetection:
    """Primitive activity detector output."""

    activity_name: str
    confidence: float = 1.0
    room_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivityHysteresisState:
    """Per-detector activity hysteresis state."""

    activity_name: str
    phase: ActivityPhase = "absent"
    phase_since_ts: float = 0.0
    duration_s: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    room_id: str | None = None
    active_started_ts: float | None = None


class ActivityDomain:
    """Core activity domain evaluated after occupancy and before house state."""

    def __init__(
        self,
        *,
        event_callback: Callable[[HeimaEvent], None] | None = None,
        now_provider: Callable[[], float] | None = None,
    ) -> None:
        self._detectors: dict[str, IActivityDetector] = {}
        self._states: dict[str, ActivityHysteresisState] = {}
        self._event_callback = event_callback
        self._now_provider = now_provider or time.monotonic

    def register_detector(self, detector: IActivityDetector) -> None:
        """Register a primitive activity detector."""
        if detector.activity_name in self._detectors:
            raise ValueError(f"Duplicate activity detector: {detector.activity_name}")
        self._detectors[detector.activity_name] = detector
        self._states[detector.activity_name] = ActivityHysteresisState(
            activity_name=detector.activity_name,
            room_id=detector.room_id,
        )

    def evaluate(
        self,
        observation: Any,
        canonical_state: CanonicalState,
        activity_signals: list[ActivitySignal] | None = None,
    ) -> ActivityResult:
        """Evaluate primitive detector hysteresis and merge approved composite signals."""
        now = self._now_provider()
        active: list[Activity] = []
        candidates: list[Activity] = []

        for detector in self._detectors.values():
            detection = detector.detect(observation, canonical_state)
            state = self._states[detector.activity_name]
            self._advance_state(detector, state, detection, now)
            if state.phase == "active":
                active.append(self._activity_from_state(state, now))
            elif state.phase == "candidate":
                candidates.append(self._activity_from_state(state, now))

        active.extend(self._activities_from_signals(activity_signals or [], now))
        result = ActivityResult(
            active=tuple(sorted(active, key=lambda item: (-item.confidence, item.name))),
            candidates=tuple(sorted(candidates, key=lambda item: (-item.confidence, item.name))),
        )
        self._write_canonical_state(canonical_state, result)
        return result

    def reset(self) -> None:
        """Reset detector hysteresis state."""
        self._states = {
            name: ActivityHysteresisState(activity_name=name, room_id=detector.room_id)
            for name, detector in self._detectors.items()
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return ActivityDomain diagnostics."""
        return {
            "detectors": list(self._detectors),
            "states": {
                name: {
                    "phase": state.phase,
                    "duration_s": state.duration_s,
                    "room_id": state.room_id,
                }
                for name, state in self._states.items()
            },
        }

    def _advance_state(
        self,
        detector: IActivityDetector,
        state: ActivityHysteresisState,
        detection: ActivityDetection | None,
        now: float,
    ) -> None:
        if state.phase == "absent":
            if detection is not None:
                self._apply_detection(state, detection)
                state.phase = "candidate"
                state.phase_since_ts = now
            return

        if state.phase == "candidate":
            if detection is None:
                self._reset_state(state, now)
                return
            self._apply_detection(state, detection)
            if now - state.phase_since_ts >= detector.candidate_period_s:
                state.phase = "active"
                state.phase_since_ts = now
                state.active_started_ts = now
                state.duration_s = 0.0
                self._emit_started(state)
            return

        if state.phase == "active":
            if detection is not None:
                state.duration_s += max(0.0, now - state.phase_since_ts)
                state.phase_since_ts = now
                self._apply_detection(state, detection)
                return
            state.duration_s += max(0.0, now - state.phase_since_ts)
            state.phase = "grace"
            state.phase_since_ts = now
            return

        if state.phase == "grace":
            if detection is not None:
                self._apply_detection(state, detection)
                state.phase = "active"
                state.phase_since_ts = now
                if state.active_started_ts is None:
                    state.active_started_ts = now
                return
            if now - state.phase_since_ts >= detector.grace_period_s:
                self._emit_ended(state)
                self._reset_state(state, now)

    @staticmethod
    def _apply_detection(state: ActivityHysteresisState, detection: ActivityDetection) -> None:
        state.context = dict(detection.context)
        state.confidence = detection.confidence
        state.room_id = detection.room_id

    @staticmethod
    def _reset_state(state: ActivityHysteresisState, now: float) -> None:
        state.phase = "absent"
        state.phase_since_ts = now
        state.duration_s = 0.0
        state.context = {}
        state.confidence = 1.0
        state.active_started_ts = None

    @staticmethod
    def _activity_from_state(state: ActivityHysteresisState, now: float) -> Activity:
        active_started_at = state.active_started_ts
        if active_started_at is None:
            active_started_at = state.phase_since_ts
        duration = state.duration_s
        if state.phase == "active":
            duration += max(0.0, now - state.phase_since_ts)
        return Activity(
            name=state.activity_name,
            confidence=state.confidence,
            room_id=state.room_id,
            started_at=active_started_at,
            duration_s=duration,
            context=dict(state.context),
        )

    @staticmethod
    def _activities_from_signals(signals: list[ActivitySignal], now: float) -> list[Activity]:
        activities: list[Activity] = []
        for signal in signals:
            if signal.confidence < 0.60 or signal.importance < Importance.SUGGEST:
                continue
            activities.append(
                Activity(
                    name=signal.activity_name,
                    confidence=signal.confidence,
                    room_id=signal.room_id,
                    started_at=now,
                    duration_s=0.0,
                    context=dict(signal.context),
                )
            )
        return activities

    @staticmethod
    def _write_canonical_state(canonical_state: CanonicalState, result: ActivityResult) -> None:
        active_names = tuple(sorted(activity.name for activity in result.active))
        candidate_names = tuple(sorted(activity.name for activity in result.candidates))
        previous_active = canonical_state.get_sensor("activity.active_names")
        canonical_state.set_sensor("activity.active_names", active_names)
        canonical_state.set_sensor("activity.candidate_names", candidate_names)
        if active_names and active_names != previous_active:
            canonical_state.set_sensor(
                "activity.last_started",
                str(max(activity.started_at for activity in result.active)),
            )

    def _emit_started(self, state: ActivityHysteresisState) -> None:
        self._emit_activity_event(
            event_type="activity.started",
            key=f"activity.started.{state.activity_name}",
            title="Activity started",
            message=f"Activity '{state.activity_name}' started.",
            state=state,
        )

    def _emit_ended(self, state: ActivityHysteresisState) -> None:
        self._emit_activity_event(
            event_type="activity.ended",
            key=f"activity.ended.{state.activity_name}",
            title="Activity ended",
            message=f"Activity '{state.activity_name}' ended.",
            state=state,
        )

    def _emit_activity_event(
        self,
        *,
        event_type: str,
        key: str,
        title: str,
        message: str,
        state: ActivityHysteresisState,
    ) -> None:
        if self._event_callback is None:
            return
        self._event_callback(
            HeimaEvent(
                type=event_type,
                key=key,
                severity="info",
                title=title,
                message=message,
                context={
                    "activity_name": state.activity_name,
                    "room_id": state.room_id,
                    "duration_s": state.duration_s,
                    **dict(state.context),
                },
            )
        )
