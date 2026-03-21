"""Tests for HeimaEngine._rebuild_configured_reactions()."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.reactions import (
    builtin_reaction_plugin_builders,
    builtin_reaction_plugin_descriptors,
)
from custom_components.heima.runtime.reactions.heating import HeatingEcoReaction, HeatingPreferenceReaction
from custom_components.heima.runtime.reactions.presence import PresencePatternReaction
from custom_components.heima.runtime.reactions.signal_assist import RoomSignalAssistReaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(options: dict | None = None) -> HeimaEngine:
    hass = MagicMock()
    hass.states.get.return_value = None
    entry = MagicMock()
    entry.options = options or {}
    entry.entry_id = "test_entry"

    engine = HeimaEngine.__new__(HeimaEngine)
    engine._hass = hass
    engine._entry = entry
    engine._reactions = []
    engine._muted_reactions = set()
    engine._configured_reaction_ids = set()
    engine._reaction_plugin_builders = builtin_reaction_plugin_builders()
    return engine


def _presence_cfg(
    weekday: int = 0,
    median_arrival_min: int = 480,
    **kwargs,
) -> dict:
    return {
        "reaction_class": "PresencePatternReaction",
        "weekday": weekday,
        "median_arrival_min": median_arrival_min,
        "window_half_min": kwargs.get("window_half_min", 15),
        "pre_condition_min": kwargs.get("pre_condition_min", 20),
        "min_arrivals": kwargs.get("min_arrivals", 5),
        "steps": kwargs.get("steps", []),
    }


def _heating_options(configured: dict[str, dict]) -> dict:
    return {
        "heating": {"climate_entity": "climate.test_heating"},
        "reactions": {"configured": configured},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_configured_entries_noop():
    engine = _make_engine()
    engine._rebuild_configured_reactions()
    assert engine._reactions == []
    assert engine._configured_reaction_ids == set()


def test_builtin_reaction_plugin_registry_exposes_current_rebuildable_plugins():
    registry = builtin_reaction_plugin_builders()

    assert set(registry) == {
        "PresencePatternReaction",
        "LightingScheduleReaction",
        "HeatingPreferenceReaction",
        "HeatingEcoReaction",
        "RoomSignalAssistReaction",
    }


def test_builtin_reaction_plugin_descriptors_expose_minimal_metadata():
    descriptors = builtin_reaction_plugin_descriptors()

    assert [d.reaction_class for d in descriptors] == [
        "PresencePatternReaction",
        "LightingScheduleReaction",
        "HeatingPreferenceReaction",
        "HeatingEcoReaction",
        "RoomSignalAssistReaction",
    ]
    assert descriptors[-1].supported_config_contracts == (
        "room_signal_assist",
        "room_cooling_assist",
    )
    assert descriptors[-1].supports_normalizer is True


def test_presence_reaction_built_and_registered():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "proposal-abc": _presence_cfg(weekday=1, median_arrival_min=480),
            }
        }
    })
    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    r = engine._reactions[0]
    assert isinstance(r, PresencePatternReaction)
    assert r.reaction_id == "proposal-abc"
    assert "proposal-abc" in engine._configured_reaction_ids


def test_reaction_pre_seeded_with_synthetic_arrivals():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "p1": _presence_cfg(weekday=2, median_arrival_min=540, min_arrivals=5),
            }
        }
    })
    engine._rebuild_configured_reactions()

    r = engine._reactions[0]
    # Should have min_arrivals synthetic records for weekday 2 at minute 540
    arrivals = r.arrivals_for_weekday(2)
    assert len(arrivals) >= 5
    assert all(a == 540 for a in arrivals)


def test_unknown_reaction_class_skipped(caplog):
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "p1": {"reaction_class": "UnknownReaction", "weekday": 0},
            }
        }
    })
    import logging
    with caplog.at_level(logging.DEBUG, logger="custom_components.heima.runtime.engine"):
        engine._rebuild_configured_reactions()

    assert engine._reactions == []
    assert engine._configured_reaction_ids == set()


def test_malformed_config_skipped(caplog):
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "bad": {
                    "reaction_class": "PresencePatternReaction",
                    # missing weekday and median_arrival_min
                },
            }
        }
    })
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.heima.runtime.engine"):
        engine._rebuild_configured_reactions()

    assert engine._reactions == []
    assert "bad" not in engine._configured_reaction_ids


def test_rebuild_replaces_previous_configured_reactions():
    """Calling rebuild twice should not accumulate duplicates."""
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "p1": _presence_cfg(weekday=0, median_arrival_min=480),
            }
        }
    })
    engine._rebuild_configured_reactions()
    assert len(engine._reactions) == 1

    engine._rebuild_configured_reactions()
    assert len(engine._reactions) == 1  # not 2


def test_non_configured_reactions_preserved_on_rebuild():
    """Code-registered reactions must survive rebuild."""
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "p1": _presence_cfg(weekday=0, median_arrival_min=480),
            }
        }
    })
    # Manually register a non-configured reaction
    manual = PresencePatternReaction(steps=[], reaction_id="manual_react")
    engine._reactions.append(manual)

    engine._rebuild_configured_reactions()

    ids = {r.reaction_id for r in engine._reactions}
    assert "manual_react" in ids
    assert "p1" in ids


def test_multiple_weekday_proposals_all_registered():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                f"p{d}": _presence_cfg(weekday=d, median_arrival_min=480 + d * 10)
                for d in range(3)
            }
        }
    })
    engine._rebuild_configured_reactions()
    assert len(engine._reactions) == 3
    assert len(engine._configured_reaction_ids) == 3


def test_heating_preference_reaction_built_and_registered():
    engine = _make_engine(options=_heating_options({
        "hp1": {
            "reaction_class": "HeatingPreferenceReaction",
            "house_state": "home",
            "target_temperature": 21.5,
        }
    }))
    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    reaction = engine._reactions[0]
    assert isinstance(reaction, HeatingPreferenceReaction)
    assert reaction.reaction_id == "hp1"


def test_heating_eco_reaction_built_and_registered():
    engine = _make_engine(options=_heating_options({
        "he1": {
            "reaction_class": "HeatingEcoReaction",
            "eco_target_temperature": 16.0,
        }
    }))
    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    reaction = engine._reactions[0]
    assert isinstance(reaction, HeatingEcoReaction)
    assert reaction.reaction_id == "he1"


def test_room_signal_assist_reaction_built_and_registered():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "sa1": {
                    "reaction_class": "RoomSignalAssistReaction",
                    "room_id": "bathroom",
                    "trigger_signal_entities": ["sensor.bathroom_humidity"],
                    "temperature_signal_entities": ["sensor.bathroom_temperature"],
                    "humidity_rise_threshold": 8.0,
                    "temperature_rise_threshold": 0.8,
                    "correlation_window_s": 600,
                    "followup_window_s": 900,
                    "steps": [{"domain": "script", "target": "script.fan_on", "action": "script.turn_on"}],
                }
            }
        }
    })
    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    reaction = engine._reactions[0]
    assert isinstance(reaction, RoomSignalAssistReaction)
    assert reaction.reaction_id == "sa1"


def test_room_signal_assist_reaction_builds_generic_signal_config():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "sa2": {
                    "reaction_class": "RoomSignalAssistReaction",
                    "room_id": "studio",
                    "primary_signal_entities": ["sensor.studio_temperature"],
                    "primary_rise_threshold": 1.5,
                    "primary_signal_name": "temperature",
                    "corroboration_signal_entities": ["sensor.studio_humidity"],
                    "corroboration_rise_threshold": 5.0,
                    "corroboration_signal_name": "humidity",
                    "steps": [{"domain": "script", "target": "script.cool_room", "action": "script.turn_on"}],
                }
            }
        }
    })

    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    reaction = engine._reactions[0]
    assert isinstance(reaction, RoomSignalAssistReaction)
    assert reaction.reaction_id == "sa2"


def test_room_signal_assist_reaction_normalizer_prefers_generic_fields_over_legacy_aliases():
    normalized = HeimaEngine._normalize_room_signal_assist_config(
        {
            "trigger_signal_entities": ["sensor.legacy_humidity"],
            "primary_signal_entities": ["sensor.generic_temperature"],
            "humidity_rise_threshold": 8.0,
            "primary_rise_threshold": 1.5,
            "temperature_signal_entities": ["sensor.legacy_temperature"],
            "corroboration_signal_entities": ["sensor.generic_humidity"],
            "temperature_rise_threshold": 0.8,
            "corroboration_rise_threshold": 5.0,
            "primary_signal_name": "temperature",
            "corroboration_signal_name": "humidity",
        }
    )

    assert normalized["primary_signal_entities"] == ["sensor.generic_temperature"]
    assert normalized["primary_rise_threshold"] == 1.5
    assert normalized["corroboration_signal_entities"] == ["sensor.generic_humidity"]
    assert normalized["corroboration_rise_threshold"] == 5.0


def test_rebuild_clears_removed_proposals():
    """If a proposal is removed from options, its reaction should be removed."""
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "p1": _presence_cfg(weekday=0, median_arrival_min=480),
                "p2": _presence_cfg(weekday=1, median_arrival_min=500),
            }
        }
    })
    engine._rebuild_configured_reactions()
    assert len(engine._reactions) == 2

    # Remove p2 from options
    engine._entry.options = {
        "reactions": {
            "configured": {
                "p1": _presence_cfg(weekday=0, median_arrival_min=480),
            }
        }
    }
    engine._rebuild_configured_reactions()
    assert len(engine._reactions) == 1
    assert engine._reactions[0].reaction_id == "p1"
