"""Tests for coordinator learning threshold option parsing."""

from __future__ import annotations

from custom_components.heima.coordinator import _learning_module_threshold_kwargs


def test_learning_module_threshold_kwargs_reads_valid_values() -> None:
    kwargs = _learning_module_threshold_kwargs(
        {
            "weekday_state_min_support": "5",
            "weekday_state_confidence_threshold": "0.75",
        },
        "weekday_state",
    )

    assert kwargs == {
        "min_support": 5,
        "confidence_threshold": 0.75,
    }


def test_learning_module_threshold_kwargs_ignores_invalid_values() -> None:
    kwargs = _learning_module_threshold_kwargs(
        {
            "weekday_state_min_support": 0,
            "weekday_state_confidence_threshold": 1.5,
            "heating_preference_min_support": 4,
            "heating_preference_confidence_threshold": 0.6,
        },
        "weekday_state",
    )

    assert kwargs == {}


def test_learning_module_threshold_kwargs_can_skip_confidence_threshold() -> None:
    kwargs = _learning_module_threshold_kwargs(
        {
            "heating_preference_min_support": 4,
            "heating_preference_confidence_threshold": 0.6,
        },
        "heating_preference",
        confidence_threshold=False,
    )

    assert kwargs == {"min_support": 4}
