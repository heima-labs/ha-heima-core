"""Tests for ActivityDomain foundation and hysteresis."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.heima.runtime.contracts import HeimaEvent
from custom_components.heima.runtime.domains.activity_domain import (
    ActivityDetection,
    ActivityDomain,
)
from custom_components.heima.runtime.inference import ActivitySignal, Importance
from custom_components.heima.runtime.plugin_contracts import IActivityDetector
from custom_components.heima.runtime.state_store import CanonicalState


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value


class _Detector:
    def __init__(
        self,
        *,
        activity_name: str = "stove_on",
        room_id: str | None = "kitchen",
        candidate_period_s: float = 5.0,
        grace_period_s: float = 30.0,
    ) -> None:
        self._activity_name = activity_name
        self._room_id = room_id
        self._candidate_period_s = candidate_period_s
        self._grace_period_s = grace_period_s
        self.active = False
        self.confidence = 1.0

    @property
    def activity_name(self) -> str:
        return self._activity_name

    @property
    def room_id(self) -> str | None:
        return self._room_id

    @property
    def candidate_period_s(self) -> float:
        return self._candidate_period_s

    @property
    def grace_period_s(self) -> float:
        return self._grace_period_s

    def detect(
        self,
        observation: Any,
        canonical_state: CanonicalState,
    ) -> ActivityDetection | None:
        del observation, canonical_state
        if not self.active:
            return None
        return ActivityDetection(
            activity_name=self.activity_name,
            confidence=self.confidence,
            room_id=self.room_id,
            context={"test.source": "detector"},
        )


def _domain(
    clock: _Clock,
    detector: _Detector | None = None,
    events: list[HeimaEvent] | None = None,
) -> ActivityDomain:
    domain = ActivityDomain(
        event_callback=events.append if events is not None else None, now_provider=clock.now
    )
    domain.register_detector(detector or _Detector())
    return domain


def test_activity_detector_protocol_accepts_detector() -> None:
    assert isinstance(_Detector(), IActivityDetector)


def test_absent_to_candidate_transition_writes_candidate_result() -> None:
    clock = _Clock()
    detector = _Detector()
    detector.active = True
    state = CanonicalState()
    result = _domain(clock, detector).evaluate(object(), state)

    assert [activity.name for activity in result.candidates] == ["stove_on"]
    assert result.active == ()
    assert state.get_sensor("activity.candidate_names") == ("stove_on",)
    assert state.get_sensor("activity.active_names") == ()


def test_candidate_to_absent_transition_resets_false_start() -> None:
    clock = _Clock()
    detector = _Detector()
    domain = _domain(clock, detector)
    state = CanonicalState()

    detector.active = True
    domain.evaluate(object(), state)
    detector.active = False
    clock.set(1.0)
    result = domain.evaluate(object(), state)

    assert result.candidates == ()
    assert result.active == ()
    assert state.get_sensor("activity.candidate_names") == ()


def test_candidate_to_active_transition_emits_started_event() -> None:
    clock = _Clock()
    detector = _Detector(candidate_period_s=5.0)
    events: list[HeimaEvent] = []
    domain = _domain(clock, detector, events)
    state = CanonicalState()

    detector.active = True
    domain.evaluate(object(), state)
    clock.set(5.0)
    result = domain.evaluate(object(), state)

    assert [activity.name for activity in result.active] == ["stove_on"]
    assert result.candidates == ()
    assert state.get_sensor("activity.active_names") == ("stove_on",)
    assert state.get_sensor("activity.last_started") == "5.0"
    assert [event.type for event in events] == ["activity.started"]


def test_active_to_grace_transition_removes_activity_from_result() -> None:
    clock = _Clock()
    detector = _Detector(candidate_period_s=0.0)
    domain = _domain(clock, detector)
    state = CanonicalState()

    detector.active = True
    domain.evaluate(object(), state)
    clock.set(1.0)
    domain.evaluate(object(), state)
    detector.active = False
    clock.set(3.0)
    result = domain.evaluate(object(), state)

    assert result.active == ()
    assert result.candidates == ()
    assert state.get_sensor("activity.active_names") == ()


def test_grace_to_active_transition_restores_activity_without_new_start_event() -> None:
    clock = _Clock()
    detector = _Detector(candidate_period_s=0.0)
    events: list[HeimaEvent] = []
    domain = _domain(clock, detector, events)
    state = CanonicalState()

    detector.active = True
    domain.evaluate(object(), state)
    clock.set(1.0)
    domain.evaluate(object(), state)
    detector.active = False
    clock.set(2.0)
    domain.evaluate(object(), state)
    detector.active = True
    clock.set(3.0)
    result = domain.evaluate(object(), state)

    assert [activity.name for activity in result.active] == ["stove_on"]
    assert [event.type for event in events] == ["activity.started"]


def test_grace_to_absent_transition_emits_ended_event() -> None:
    clock = _Clock()
    detector = _Detector(candidate_period_s=0.0, grace_period_s=10.0)
    events: list[HeimaEvent] = []
    domain = _domain(clock, detector, events)
    state = CanonicalState()

    detector.active = True
    domain.evaluate(object(), state)
    clock.set(1.0)
    domain.evaluate(object(), state)
    detector.active = False
    clock.set(2.0)
    domain.evaluate(object(), state)
    clock.set(12.0)
    result = domain.evaluate(object(), state)

    assert result.active == ()
    assert [event.type for event in events] == ["activity.started", "activity.ended"]
    assert events[-1].context["duration_s"] == 1.0


def test_activity_duration_accumulates_while_active() -> None:
    clock = _Clock()
    detector = _Detector(candidate_period_s=0.0)
    domain = _domain(clock, detector)

    detector.active = True
    domain.evaluate(object(), CanonicalState())
    domain.evaluate(object(), CanonicalState())
    clock.set(2.0)
    result = domain.evaluate(object(), CanonicalState())

    assert result.active[0].started_at == 0.0
    assert result.active[0].duration_s == 2.0


def test_duplicate_detector_registration_is_rejected() -> None:
    clock = _Clock()
    domain = ActivityDomain(now_provider=clock.now)
    domain.register_detector(_Detector(activity_name="stove_on"))

    with pytest.raises(ValueError, match="Duplicate activity detector"):
        domain.register_detector(_Detector(activity_name="stove_on"))


def test_reset_restores_detector_to_absent() -> None:
    clock = _Clock()
    detector = _Detector()
    detector.active = True
    domain = _domain(clock, detector)
    state = CanonicalState()
    domain.evaluate(object(), state)

    domain.reset()
    result = domain.evaluate(object(), CanonicalState())

    assert result.active == ()
    assert result.candidates
    assert domain.diagnostics()["states"]["stove_on"]["phase"] == "candidate"


def test_activity_signals_are_merged_when_confident_and_suggested() -> None:
    clock = _Clock()
    domain = ActivityDomain(now_provider=clock.now)
    state = CanonicalState()
    signal = ActivitySignal(
        source_id="activity_inference",
        confidence=0.75,
        importance=Importance.SUGGEST,
        ttl_s=600,
        label="movie pattern",
        activity_name="movie_night",
        room_id="living_room",
        context={"inference.pattern": "tv_low_lux"},
    )

    result = domain.evaluate(object(), state, activity_signals=[signal])

    assert [activity.name for activity in result.active] == ["movie_night"]
    assert result.active[0].confidence == 0.75
    assert state.get_sensor("activity.active_names") == ("movie_night",)


def test_low_confidence_or_observe_activity_signals_are_ignored() -> None:
    clock = _Clock()
    domain = ActivityDomain(now_provider=clock.now)
    state = CanonicalState()
    low_confidence = ActivitySignal(
        source_id="activity_inference",
        confidence=0.59,
        importance=Importance.SUGGEST,
        ttl_s=600,
        label="low confidence",
        activity_name="low_confidence",
        room_id=None,
    )
    observe = ActivitySignal(
        source_id="activity_inference",
        confidence=0.9,
        importance=Importance.OBSERVE,
        ttl_s=600,
        label="observe only",
        activity_name="observe_only",
        room_id=None,
    )

    result = domain.evaluate(object(), state, activity_signals=[low_confidence, observe])

    assert result.active == ()
    assert state.get_sensor("activity.active_names") == ()
