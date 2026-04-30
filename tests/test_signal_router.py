"""Tests for SignalRouter."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.heima.runtime.inference import (
    HeatingSignal,
    HouseStateSignal,
    Importance,
    SignalRouter,
)


def _now() -> datetime:
    return datetime(2026, 4, 30, 12, 0, tzinfo=UTC)


def _house_signal(
    *,
    source_id: str = "mod_a",
    confidence: float = 0.7,
    importance: Importance = Importance.SUGGEST,
    predicted_state: str = "home",
    ttl_s: int = 600,
) -> HouseStateSignal:
    return HouseStateSignal(
        source_id=source_id,
        confidence=confidence,
        importance=importance,
        ttl_s=ttl_s,
        label="test",
        predicted_state=predicted_state,
    )


def _heating_signal(
    *,
    source_id: str = "mod_b",
    confidence: float = 0.7,
    importance: Importance = Importance.SUGGEST,
    predicted_setpoint: float = 20.5,
    ttl_s: int = 600,
) -> HeatingSignal:
    return HeatingSignal(
        source_id=source_id,
        confidence=confidence,
        importance=importance,
        ttl_s=ttl_s,
        label="test",
        predicted_setpoint=predicted_setpoint,
        house_state_context="home",
    )


def test_signal_router_groups_signals_by_type() -> None:
    router = SignalRouter()
    now = _now()
    signals = [
        (_house_signal(), now),
        (_heating_signal(), now),
        (_house_signal(source_id="mod_c", confidence=0.5), now),
    ]

    result = router.route(signals, now)

    assert HouseStateSignal in result
    assert HeatingSignal in result
    assert len(result[HouseStateSignal]) == 2
    assert len(result[HeatingSignal]) == 1


def test_signal_router_filters_expired_signals() -> None:
    router = SignalRouter()
    now = _now()
    fresh = _house_signal(ttl_s=600)
    expired = _house_signal(source_id="old", ttl_s=10)
    emit_old = now - timedelta(seconds=60)

    result = router.route([(fresh, now), (expired, emit_old)], now)

    assert len(result[HouseStateSignal]) == 1
    assert result[HouseStateSignal][0].source_id == "mod_a"


def test_signal_router_sorts_by_confidence_desc() -> None:
    router = SignalRouter()
    now = _now()
    low = _house_signal(source_id="low", confidence=0.5, importance=Importance.OBSERVE)
    high = _house_signal(source_id="high", confidence=0.9, importance=Importance.ASSERT)
    mid = _house_signal(source_id="mid", confidence=0.7, importance=Importance.SUGGEST)

    result = router.route([(low, now), (high, now), (mid, now)], now)

    ordered = [s.source_id for s in result[HouseStateSignal]]
    assert ordered == ["high", "mid", "low"]


def test_signal_router_tiebreak_by_most_conservative_importance() -> None:
    router = SignalRouter()
    now = _now()
    suggest = _house_signal(source_id="suggest", confidence=0.7, importance=Importance.SUGGEST)
    observe = _house_signal(source_id="observe", confidence=0.7, importance=Importance.OBSERVE)
    assert_ = _house_signal(source_id="assert", confidence=0.7, importance=Importance.ASSERT)

    result = router.route([(assert_, now), (suggest, now), (observe, now)], now)

    # tie-break: most conservative = lowest importance value first
    ordered = [s.source_id for s in result[HouseStateSignal]]
    assert ordered[0] == "observe"


def test_signal_router_warns_on_conflicting_high_confidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = SignalRouter()
    now = _now()
    sig_a = _house_signal(source_id="a", confidence=0.75, predicted_state="home")
    sig_b = _house_signal(source_id="b", confidence=0.65, predicted_state="away")

    with caplog.at_level(
        logging.WARNING, logger="custom_components.heima.runtime.inference.router"
    ):
        router.route([(sig_a, now), (sig_b, now)], now)

    assert any("conflicting" in record.message for record in caplog.records)


def test_signal_router_no_warning_for_same_predicted_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = SignalRouter()
    now = _now()
    sig_a = _house_signal(source_id="a", confidence=0.75, predicted_state="home")
    sig_b = _house_signal(source_id="b", confidence=0.65, predicted_state="home")

    with caplog.at_level(
        logging.WARNING, logger="custom_components.heima.runtime.inference.router"
    ):
        router.route([(sig_a, now), (sig_b, now)], now)

    assert not any("conflicting" in record.message for record in caplog.records)


def test_signal_router_no_warning_below_confidence_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = SignalRouter()
    now = _now()
    sig_a = _house_signal(source_id="a", confidence=0.55, predicted_state="home")
    sig_b = _house_signal(source_id="b", confidence=0.50, predicted_state="away")

    with caplog.at_level(
        logging.WARNING, logger="custom_components.heima.runtime.inference.router"
    ):
        router.route([(sig_a, now), (sig_b, now)], now)

    assert not any("conflicting" in record.message for record in caplog.records)


def test_signal_router_empty_input_returns_empty() -> None:
    router = SignalRouter()
    assert router.route([], _now()) == {}


def test_signal_router_all_expired_returns_empty() -> None:
    router = SignalRouter()
    now = _now()
    expired = _house_signal(ttl_s=5)
    emit_time = now - timedelta(seconds=60)
    assert router.route([(expired, emit_time)], now) == {}
