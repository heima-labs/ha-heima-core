"""Tests for built-in primitive activity detectors."""

from __future__ import annotations

import pytest

from custom_components.heima.runtime.activity_detectors import (
    DishwasherDetector,
    OvenOnDetector,
    PcActiveDetector,
    StoveOnDetector,
    TvActiveDetector,
    WashingMachineDetector,
)
from custom_components.heima.runtime.domains.activity_domain import ActivityDetection
from custom_components.heima.runtime.normalization import NormalizedObservation
from custom_components.heima.runtime.plugin_contracts import IActivityDetector
from custom_components.heima.runtime.state_store import CanonicalState


def _obs(
    *,
    entity_id: str = "sensor.device_power",
    state: str = "250",
    raw_state: str | None = None,
    available: bool = True,
    stale: bool = False,
    confidence: int = 100,
) -> NormalizedObservation:
    return NormalizedObservation(
        kind="sensor",
        state=state,
        confidence=confidence,
        raw_state=raw_state if raw_state is not None else state,
        source_entity_id=entity_id,
        available=available,
        stale=stale,
    )


@pytest.mark.parametrize(
    ("detector", "expected_name", "candidate_s", "grace_s"),
    [
        (StoveOnDetector(entity_id="sensor.device_power"), "stove_on", 5.0, 30.0),
        (OvenOnDetector(entity_id="sensor.device_power"), "oven_on", 10.0, 120.0),
        (PcActiveDetector(entity_id="sensor.device_power"), "pc_active", 30.0, 60.0),
        (
            WashingMachineDetector(entity_id="sensor.device_power"),
            "washing_machine_running",
            60.0,
            300.0,
        ),
        (
            DishwasherDetector(entity_id="sensor.device_power"),
            "dishwasher_running",
            60.0,
            300.0,
        ),
        (TvActiveDetector(entity_id="sensor.device_power"), "tv_active", 10.0, 120.0),
    ],
)
def test_detectors_expose_activity_contract(
    detector: IActivityDetector,
    expected_name: str,
    candidate_s: float,
    grace_s: float,
) -> None:
    assert isinstance(detector, IActivityDetector)
    assert detector.activity_name == expected_name
    assert detector.candidate_period_s == candidate_s
    assert detector.grace_period_s == grace_s


@pytest.mark.parametrize(
    ("detector", "active_state", "inactive_state"),
    [
        (StoveOnDetector(entity_id="sensor.device_power"), "200", "199.9"),
        (OvenOnDetector(entity_id="sensor.device_power"), "500", "499.9"),
        (PcActiveDetector(entity_id="sensor.device_power"), "50", "49.9"),
        (WashingMachineDetector(entity_id="sensor.device_power"), "200", "199.9"),
        (DishwasherDetector(entity_id="sensor.device_power"), "200", "199.9"),
    ],
)
def test_power_detectors_fire_at_configured_threshold(
    detector: IActivityDetector,
    active_state: str,
    inactive_state: str,
) -> None:
    assert isinstance(
        detector.detect(_obs(state=active_state), CanonicalState()), ActivityDetection
    )
    assert detector.detect(_obs(state=inactive_state), CanonicalState()) is None


def test_detector_is_inactive_when_unbound() -> None:
    detector = StoveOnDetector()

    assert detector.detect(_obs(), CanonicalState()) is None


def test_detector_ignores_unmatched_entity() -> None:
    detector = StoveOnDetector(entity_id="sensor.stove_power")

    assert detector.detect(_obs(entity_id="sensor.other_power"), CanonicalState()) is None


@pytest.mark.parametrize(
    "observation",
    [
        _obs(available=False),
        _obs(stale=True),
        _obs(state="unknown", raw_state="unknown"),
    ],
)
def test_power_detector_ignores_unavailable_stale_or_non_numeric_observation(
    observation: NormalizedObservation,
) -> None:
    detector = StoveOnDetector(entity_id="sensor.device_power")

    assert detector.detect(observation, CanonicalState()) is None


def test_detector_uses_raw_state_when_normalized_state_is_not_numeric() -> None:
    detector = StoveOnDetector(entity_id="sensor.device_power")

    detection = detector.detect(_obs(state="on", raw_state="250"), CanonicalState())

    assert detection is not None
    assert detection.context["activity.reason"] == "power_gte_200w"


def test_detector_preserves_room_and_confidence() -> None:
    detector = StoveOnDetector(entity_id="sensor.stove_power", room_id="kitchen")

    detection = detector.detect(
        _obs(entity_id="sensor.stove_power", state="250", confidence=87),
        CanonicalState(),
    )

    assert detection is not None
    assert detection.room_id == "kitchen"
    assert detection.confidence == 0.87
    assert detection.context["activity.entity_id"] == "sensor.stove_power"


@pytest.mark.parametrize("state", ["playing", "paused"])
def test_tv_detector_fires_on_media_active_state(state: str) -> None:
    detector = TvActiveDetector(entity_id="media_player.tv")

    detection = detector.detect(
        _obs(entity_id="media_player.tv", state=state, raw_state=state),
        CanonicalState(),
    )

    assert detection is not None
    assert detection.context["activity.reason"] == "media_active"


def test_tv_detector_fires_on_power_above_threshold() -> None:
    detector = TvActiveDetector(entity_id="sensor.tv_power")

    detection = detector.detect(_obs(entity_id="sensor.tv_power", state="20.1"), CanonicalState())

    assert detection is not None
    assert detection.context["activity.reason"] == "power_gt_20w"


def test_tv_detector_does_not_fire_at_power_threshold() -> None:
    detector = TvActiveDetector(entity_id="sensor.tv_power")

    assert detector.detect(_obs(entity_id="sensor.tv_power", state="20"), CanonicalState()) is None


@pytest.mark.parametrize(
    "detector",
    [
        WashingMachineDetector(entity_id="switch.washer"),
        DishwasherDetector(entity_id="switch.dishwasher"),
    ],
)
def test_appliance_detectors_fire_on_on_or_running_state(detector: IActivityDetector) -> None:
    detection = detector.detect(
        _obs(entity_id=str(getattr(detector, "entity_id")), state="on", raw_state="on"),
        CanonicalState(),
    )

    assert detection is not None
    assert detection.context["activity.reason"] == "state_on"


def test_custom_threshold_and_timing_can_be_configured() -> None:
    detector = StoveOnDetector(
        entity_id="sensor.stove_power",
        threshold_w=150,
        candidate_period_s=2,
        grace_period_s=9,
    )

    detection = detector.detect(_obs(entity_id="sensor.stove_power", state="150"), CanonicalState())

    assert detection is not None
    assert detector.candidate_period_s == 2.0
    assert detector.grace_period_s == 9.0


def test_public_detector_modules_export_expected_classes() -> None:
    from custom_components.heima.runtime.activity_detectors.dishwasher import (
        DishwasherDetector as D,
    )
    from custom_components.heima.runtime.activity_detectors.oven import OvenOnDetector as O
    from custom_components.heima.runtime.activity_detectors.pc import PcActiveDetector as P
    from custom_components.heima.runtime.activity_detectors.stove import StoveOnDetector as S
    from custom_components.heima.runtime.activity_detectors.tv import TvActiveDetector as T
    from custom_components.heima.runtime.activity_detectors.washing import (
        WashingMachineDetector as W,
    )

    assert [cls.__name__ for cls in (D, O, P, S, T, W)] == [
        "DishwasherDetector",
        "OvenOnDetector",
        "PcActiveDetector",
        "StoveOnDetector",
        "TvActiveDetector",
        "WashingMachineDetector",
    ]
