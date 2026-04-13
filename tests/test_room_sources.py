"""Tests for room source normalization helpers."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.room_sources import (
    autopopulate_room_signals,
    format_room_signals_for_form,
    migrate_room_darkness_reactions_to_primary_bucket,
    normalize_room_signals,
)


def test_autopopulate_room_signals_from_learning_sources():
    options = {
        "rooms": [
            {
                "room_id": "studio",
                "learning_sources": [
                    "sensor.studio_lux",
                    "sensor.studio_co2",
                    "sensor.studio_temperature",
                ],
            }
        ]
    }
    states = {
        "sensor.studio_lux": SimpleNamespace(attributes={"device_class": "illuminance"}),
        "sensor.studio_co2": SimpleNamespace(attributes={"device_class": "carbon_dioxide"}),
        "sensor.studio_temperature": SimpleNamespace(attributes={"device_class": "temperature"}),
    }

    normalized, changed = autopopulate_room_signals(options, state_getter=states.get)

    assert changed is True
    signals = normalized["rooms"][0]["signals"]
    assert [item["entity_id"] for item in signals] == [
        "sensor.studio_lux",
        "sensor.studio_co2",
        "sensor.studio_temperature",
    ]
    assert [item["signal_name"] for item in signals] == [
        "room_lux",
        "room_co2",
        "room_temperature",
    ]


def test_autopopulate_room_signals_keeps_existing_config():
    options = {
        "rooms": [
            {
                "room_id": "studio",
                "learning_sources": ["sensor.studio_lux"],
                "signals": [
                    {
                        "entity_id": "sensor.studio_lux",
                        "signal_name": "room_lux",
                        "device_class": "illuminance",
                        "buckets": [{"label": "dark", "upper_bound": 30.0}],
                    }
                ],
            }
        ]
    }

    normalized, changed = autopopulate_room_signals(options, state_getter=lambda _eid: None)

    assert changed is False
    assert normalized == options


def test_migrate_room_darkness_reaction_threshold_to_primary_bucket():
    options = {
        "rooms": [
            {
                "room_id": "studio",
                "signals": [
                    {
                        "entity_id": "sensor.studio_lux",
                        "signal_name": "room_lux",
                        "device_class": "illuminance",
                        "buckets": [
                            {"label": "dark", "upper_bound": 30.0},
                            {"label": "dim", "upper_bound": 100.0},
                            {"label": "ok", "upper_bound": 300.0},
                            {"label": "bright", "upper_bound": None},
                        ],
                    }
                ],
            }
        ],
        "reactions": {
            "configured": {
                "rx-1": {
                    "reaction_type": "room_darkness_lighting_assist",
                    "room_id": "studio",
                    "primary_signal_name": "room_lux",
                    "primary_threshold": 90.0,
                    "primary_threshold_mode": "below",
                    "primary_signal_entities": ["sensor.studio_lux"],
                    "entity_steps": [{"entity_id": "light.studio_main", "action": "on"}],
                }
            }
        },
    }

    normalized, changed = migrate_room_darkness_reactions_to_primary_bucket(options)

    assert changed is True
    cfg = normalized["reactions"]["configured"]["rx-1"]
    assert cfg["primary_bucket"] == "dim"
    assert "primary_threshold" not in cfg
    assert "primary_threshold_mode" not in cfg


def test_normalize_room_signals_parses_json_form_payload():
    raw = """
    [
      {
        "entity_id": "sensor.studio_lux",
        "signal_name": "room_lux",
        "device_class": "illuminance",
        "buckets": [
          {"label": "dark", "upper_bound": 30},
          {"label": "dim", "upper_bound": 100},
          {"label": "bright", "upper_bound": null}
        ]
      }
    ]
    """

    signals = normalize_room_signals(raw)

    assert signals == [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [
                {"label": "dark", "upper_bound": 30.0},
                {"label": "dim", "upper_bound": 100.0},
                {"label": "bright", "upper_bound": None},
            ],
        }
    ]


def test_normalize_room_signals_rejects_duplicate_signal_names():
    raw = [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [{"label": "dark", "upper_bound": 30.0}],
        },
        {
            "entity_id": "sensor.studio_lux_aux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [{"label": "dark", "upper_bound": 30.0}],
        },
    ]

    try:
        normalize_room_signals(raw)
    except ValueError as exc:
        assert str(exc) == "duplicate_signal_name"
    else:
        raise AssertionError("duplicate signal names should be rejected")


def test_format_room_signals_for_form_pretty_prints_json():
    rendered = format_room_signals_for_form(
        [
            {
                "entity_id": "sensor.studio_lux",
                "signal_name": "room_lux",
                "device_class": "illuminance",
                "buckets": [{"label": "dark", "upper_bound": 30.0}],
            }
        ]
    )

    assert '"signal_name": "room_lux"' in rendered
    assert rendered.strip().startswith("[")
