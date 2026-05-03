"""Tests for activity bindings and shower detector."""

from __future__ import annotations

from custom_components.heima.const import DEFAULT_ACTIVITY_BINDINGS, OPT_ACTIVITY_BINDINGS
from custom_components.heima.runtime.activity_detectors import (
    ShowerRunningDetector,
    build_activity_detectors,
    normalize_activity_bindings,
)
from custom_components.heima.runtime.normalization import NormalizedObservation
from custom_components.heima.runtime.state_store import CanonicalState


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value


def _humidity(
    value: float | str,
    *,
    entity_id: str = "sensor.bathroom_humidity",
    available: bool = True,
    stale: bool = False,
) -> NormalizedObservation:
    return NormalizedObservation(
        kind="sensor",
        state=str(value),
        confidence=100,
        raw_state=str(value),
        source_entity_id=entity_id,
        available=available,
        stale=stale,
    )


def test_activity_bindings_constants_include_expected_key_and_defaults() -> None:
    assert OPT_ACTIVITY_BINDINGS == "activity_bindings"
    assert DEFAULT_ACTIVITY_BINDINGS["shower_running"]["entity_key"] == "bathroom_humidity_entity"
    assert DEFAULT_ACTIVITY_BINDINGS["shower_running"]["candidate_period_s"] == 60.0
    assert DEFAULT_ACTIVITY_BINDINGS["shower_running"]["grace_period_s"] == 300.0


def test_normalize_activity_bindings_accepts_spec_binding_names() -> None:
    normalized = normalize_activity_bindings(
        {
            "stove_on": {
                "stove_power_entity": "sensor.stove_power",
                "room_id": "kitchen",
                "threshold_w": 150,
            },
            "shower_running": {
                "bathroom_humidity_entity": "sensor.bathroom_humidity",
                "humidity_threshold": 62,
            },
        }
    )

    assert normalized["stove_on"]["entity_id"] == "sensor.stove_power"
    assert normalized["stove_on"]["room_id"] == "kitchen"
    assert normalized["stove_on"]["threshold_w"] == 150
    assert normalized["shower_running"]["entity_id"] == "sensor.bathroom_humidity"
    assert normalized["shower_running"]["humidity_threshold"] == 62


def test_build_activity_detectors_skips_unbound_detectors() -> None:
    detectors = build_activity_detectors(
        {
            "stove_on": {"stove_power_entity": "sensor.stove_power"},
            "shower_running": {},
        }
    )

    assert [detector.activity_name for detector in detectors] == ["stove_on"]


def test_build_activity_detectors_builds_shower_detector_from_binding() -> None:
    detectors = build_activity_detectors(
        {
            "shower_running": {
                "bathroom_humidity_entity": "sensor.bathroom_humidity",
                "room_id": "bathroom",
                "humidity_threshold": 60,
                "min_rate_per_min": 0.2,
            }
        }
    )

    assert len(detectors) == 1
    detector = detectors[0]
    assert isinstance(detector, ShowerRunningDetector)
    assert detector.activity_name == "shower_running"
    assert detector.room_id == "bathroom"


def test_shower_detector_is_inactive_when_unbound() -> None:
    detector = ShowerRunningDetector()

    assert detector.detect(_humidity(70), CanonicalState()) is None


def test_shower_detector_needs_previous_sample() -> None:
    clock = _Clock()
    detector = ShowerRunningDetector(
        entity_id="sensor.bathroom_humidity",
        humidity_threshold=60,
        now_provider=clock.now,
    )

    assert detector.detect(_humidity(61), CanonicalState()) is None


def test_shower_detector_fires_when_humidity_is_above_threshold_and_rising() -> None:
    clock = _Clock()
    detector = ShowerRunningDetector(
        entity_id="sensor.bathroom_humidity",
        room_id="bathroom",
        humidity_threshold=60,
        min_rate_per_min=0.1,
        now_provider=clock.now,
    )

    detector.detect(_humidity(59), CanonicalState())
    clock.set(60)
    detection = detector.detect(_humidity(62), CanonicalState())

    assert detection is not None
    assert detection.activity_name == "shower_running"
    assert detection.room_id == "bathroom"
    assert detection.context["activity.reason"] == "humidity_rising"
    assert detection.context["activity.humidity"] == 62.0
    assert detection.context["activity.humidity_rate_per_min"] == 3.0


def test_shower_detector_requires_threshold_and_positive_rate() -> None:
    clock = _Clock()
    detector = ShowerRunningDetector(
        entity_id="sensor.bathroom_humidity",
        humidity_threshold=60,
        min_rate_per_min=0.1,
        now_provider=clock.now,
    )

    detector.detect(_humidity(61), CanonicalState())
    clock.set(60)
    assert detector.detect(_humidity(59), CanonicalState()) is None
    clock.set(120)
    assert detector.detect(_humidity(59.05), CanonicalState()) is None


def test_shower_detector_ignores_unavailable_stale_unmatched_or_non_numeric_samples() -> None:
    clock = _Clock()
    detector = ShowerRunningDetector(
        entity_id="sensor.bathroom_humidity",
        humidity_threshold=60,
        now_provider=clock.now,
    )

    assert detector.detect(_humidity(70, available=False), CanonicalState()) is None
    assert detector.detect(_humidity(70, stale=True), CanonicalState()) is None
    assert detector.detect(_humidity(70, entity_id="sensor.other"), CanonicalState()) is None
    assert detector.detect(_humidity("unknown"), CanonicalState()) is None
