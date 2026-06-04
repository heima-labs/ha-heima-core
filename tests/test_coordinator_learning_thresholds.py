"""Tests for coordinator learning threshold option parsing."""

from __future__ import annotations

from custom_components.heima.coordinator import _bool_option, _learning_module_threshold_kwargs


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


def test_learning_module_threshold_kwargs_reads_house_state_tier_supports() -> None:
    kwargs = _learning_module_threshold_kwargs(
        {
            "house_state_inference_min_support": 10,
            "house_state_inference_rich_min_support": "15",
            "house_state_inference_minimal_min_support": "5",
            "house_state_inference_confidence_threshold": "0.65",
        },
        "house_state_inference",
    )

    assert kwargs == {
        "min_support": 10,
        "rich_min_support": 15,
        "minimal_min_support": 5,
        "confidence_threshold": 0.65,
    }


def test_bool_option_parses_common_learning_option_values() -> None:
    assert _bool_option(True) is True
    assert _bool_option("true") is True
    assert _bool_option("false") is False
    assert _bool_option(0) is False
    assert _bool_option(1) is True
