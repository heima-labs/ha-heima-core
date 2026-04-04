"""Tests for HeimaEngine._rebuild_configured_reactions()."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.reactions import (
    builtin_reaction_plugin_descriptors,
    create_builtin_reaction_plugin_registry,
)
from custom_components.heima.runtime.reactions.heating import HeatingEcoReaction, HeatingPreferenceReaction
from custom_components.heima.runtime.reactions.lighting_assist import RoomLightingAssistReaction
from custom_components.heima.runtime.reactions.presence import PresencePatternReaction
from custom_components.heima.runtime.reactions.security_presence_simulation import (
    VacationPresenceSimulationReaction,
)
from custom_components.heima.runtime.reactions.signal_assist import (
    RoomSignalAssistReaction,
    normalize_room_signal_assist_config,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


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
    engine._reaction_plugin_registry = create_builtin_reaction_plugin_registry()
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


class _FakeState:
    def __init__(self, state: str, attributes: dict | None = None) -> None:
        self.state = state
        self.attributes = dict(attributes or {})


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
    registry = create_builtin_reaction_plugin_registry()

    assert {
        descriptor.reaction_class
        for descriptor in registry.descriptors()
    } == {
        "PresencePatternReaction",
        "LightingScheduleReaction",
        "HeatingPreferenceReaction",
        "HeatingEcoReaction",
        "RoomSignalAssistReaction",
        "RoomLightingAssistReaction",
        "VacationPresenceSimulationReaction",
    }
    assert registry.builder_for("RoomSignalAssistReaction") is not None
    assert registry.builder_for("MissingReaction") is None


def test_builtin_reaction_plugin_descriptors_expose_minimal_metadata():
    descriptors = builtin_reaction_plugin_descriptors()

    assert [d.reaction_class for d in descriptors] == [
        "PresencePatternReaction",
        "LightingScheduleReaction",
        "HeatingPreferenceReaction",
        "HeatingEcoReaction",
        "RoomSignalAssistReaction",
        "RoomLightingAssistReaction",
        "VacationPresenceSimulationReaction",
    ]
    assert descriptors[-1].supported_config_contracts == (
        "vacation_presence_simulation",
    )
    assert descriptors[-1].supports_normalizer is False
    assert descriptors[-2].supported_config_contracts == (
        "room_darkness_lighting_assist",
    )
    assert descriptors[-2].supports_normalizer is False
    assert descriptors[-3].supported_config_contracts == (
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
    )
    assert descriptors[-3].supports_normalizer is True


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


def test_vacation_presence_simulation_reaction_bootstraps_source_profile_from_recent_lighting_reactions():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "security-presence": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "enabled": True,
                    "allowed_rooms": ["living"],
                    "allowed_entities": ["light.living_main"],
                },
                "light-old": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 0,
                    "scheduled_min": 1140,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-03-30T09:00:00+00:00",
                },
                "light-new": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 1,
                    "scheduled_min": 1200,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-03-30T11:00:00+00:00",
                },
                "light-other-room": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "kitchen",
                    "weekday": 1,
                    "scheduled_min": 1210,
                    "entity_steps": [{"entity_id": "light.kitchen_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-03-30T12:00:00+00:00",
                },
            }
        }
    })

    engine._rebuild_configured_reactions()

    reaction = next(r for r in engine._reactions if r.reaction_id == "security-presence")
    assert isinstance(reaction, VacationPresenceSimulationReaction)
    diagnostics = reaction.diagnostics()
    assert diagnostics["source_profile_ready"] is True
    assert diagnostics["source_reaction_ids"] == ["light-new", "light-old"]
    assert diagnostics["source_rooms"] == ["living"]
    assert diagnostics["blocked_reason"] == "waiting_for_snapshot"


def test_vacation_presence_simulation_reaction_reports_runtime_block_reason_until_plan_exists():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "security-presence": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "enabled": True,
                    "requires_dark_outside": True,
                    "skip_if_presence_detected": True,
                },
                "light-src": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 1,
                    "scheduled_min": 1200,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                },
            }
        }
    })
    engine._rebuild_configured_reactions()

    reaction = next(r for r in engine._reactions if r.reaction_id == "security-presence")
    current = DecisionSnapshot(
        snapshot_id="s1",
        ts="2026-04-04T19:00:00+00:00",
        house_state="vacation",
        anyone_home=False,
        people_count=0,
        occupied_rooms=[],
        lighting_intents={},
        security_state="armed_away",
    )

    assert reaction.evaluate([current]) == []
    assert reaction.diagnostics()["blocked_reason"] == "sun_unavailable"


def test_vacation_presence_simulation_reaction_schedules_next_darkness_relative_job():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "security-presence": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "enabled": True,
                    "simulation_aggressiveness": "medium",
                    "skip_if_presence_detected": True,
                },
                "light-src": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 5,
                    "scheduled_min": 1210,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 120}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-04-04T10:00:00+00:00",
                },
            }
        }
    })
    engine._hass.states.get.side_effect = lambda entity_id: (
        _FakeState(
            "below_horizon",
            {
                "last_setting": "2026-04-04T18:50:00+00:00",
                "next_setting": "2026-04-05T18:51:00+00:00",
            },
        )
        if entity_id == "sun.sun"
        else None
    )
    engine._rebuild_configured_reactions()
    reaction = next(r for r in engine._reactions if r.reaction_id == "security-presence")

    with patch(
        "custom_components.heima.runtime.reactions.security_presence_simulation.dt_util.now",
        return_value=datetime(2026, 4, 4, 19, 0, 0, tzinfo=timezone.utc),
    ):
        jobs = reaction.scheduled_jobs("entry-1")

    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    assert job.owner == "VacationPresenceSimulationReaction"
    assert "security_presence_simulation:security-presence:" in job.job_id


def test_vacation_presence_simulation_reaction_fires_derived_plan_step_when_due():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "security-presence": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "enabled": True,
                    "simulation_aggressiveness": "medium",
                    "skip_if_presence_detected": True,
                },
                "light-src": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 5,
                    "scheduled_min": 1210,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 120}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-04-04T10:00:00+00:00",
                },
            }
        }
    })
    engine._hass.states.get.side_effect = lambda entity_id: (
        _FakeState(
            "below_horizon",
            {
                "last_setting": "2026-04-04T18:50:00+00:00",
                "next_setting": "2026-04-05T18:51:00+00:00",
            },
        )
        if entity_id == "sun.sun"
        else None
    )
    engine._rebuild_configured_reactions()
    reaction = next(r for r in engine._reactions if r.reaction_id == "security-presence")
    current = DecisionSnapshot(
        snapshot_id="s1",
        ts="2026-04-04T19:10:10+00:00",
        house_state="vacation",
        anyone_home=False,
        people_count=0,
        occupied_rooms=[],
        lighting_intents={},
        security_state="armed_away",
    )

    with patch(
        "custom_components.heima.runtime.reactions.security_presence_simulation.dt_util.now",
        return_value=datetime(2026, 4, 4, 19, 10, 10, tzinfo=timezone.utc),
    ):
        steps = reaction.evaluate([current])

    assert len(steps) == 1
    step = steps[0]
    assert step.action == "light.turn_on"
    assert step.params["entity_id"] == "light.living_main"
    assert step.reason == "security_presence_simulation:security-presence:light-src"
    diagnostics = reaction.diagnostics()
    assert diagnostics["last_simulated_activation"] is not None
    assert diagnostics["fire_count"] == 1


def test_vacation_presence_simulation_reaction_excludes_stale_sources_from_tonight_plan():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "security-presence": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "enabled": True,
                    "simulation_aggressiveness": "medium",
                    "skip_if_presence_detected": True,
                },
                "light-stale": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 5,
                    "scheduled_min": 1210,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2025-11-01T10:00:00+00:00",
                },
            }
        }
    })
    engine._hass.states.get.side_effect = lambda entity_id: (
        _FakeState(
            "below_horizon",
            {
                "last_setting": "2026-04-04T18:50:00+00:00",
                "next_setting": "2026-04-05T18:51:00+00:00",
            },
        )
        if entity_id == "sun.sun"
        else None
    )
    engine._rebuild_configured_reactions()
    reaction = next(r for r in engine._reactions if r.reaction_id == "security-presence")
    current = DecisionSnapshot(
        snapshot_id="s1",
        ts="2026-04-04T19:10:10+00:00",
        house_state="vacation",
        anyone_home=False,
        people_count=0,
        occupied_rooms=[],
        lighting_intents={},
        security_state="armed_away",
    )

    with patch(
        "custom_components.heima.runtime.reactions.security_presence_simulation.dt_util.now",
        return_value=datetime(2026, 4, 4, 19, 10, 10, tzinfo=timezone.utc),
    ):
        steps = reaction.evaluate([current])

    assert steps == []
    diagnostics = reaction.diagnostics()
    assert diagnostics["recent_source_reaction_count"] == 0
    assert diagnostics["tonight_plan_count"] == 0
    assert diagnostics["blocked_reason"] == "no_suitable_recent_sources"


def test_vacation_presence_simulation_reaction_exposes_tonight_plan_preview():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "security-presence": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "enabled": True,
                    "simulation_aggressiveness": "high",
                    "skip_if_presence_detected": True,
                },
                "light-src-1": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "living",
                    "weekday": 5,
                    "scheduled_min": 1210,
                    "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-04-04T10:00:00+00:00",
                },
                "light-src-2": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "room_id": "kitchen",
                    "weekday": 5,
                    "scheduled_min": 1250,
                    "entity_steps": [{"entity_id": "light.kitchen_main", "action": "on"}],
                    "source_template_id": "lighting.scene_schedule.basic",
                    "updated_at": "2026-04-04T09:00:00+00:00",
                },
            }
        }
    })
    engine._hass.states.get.side_effect = lambda entity_id: (
        _FakeState(
            "below_horizon",
            {
                "last_setting": "2026-04-04T18:50:00+00:00",
                "next_setting": "2026-04-05T18:51:00+00:00",
            },
        )
        if entity_id == "sun.sun"
        else None
    )
    engine._rebuild_configured_reactions()
    reaction = next(r for r in engine._reactions if r.reaction_id == "security-presence")

    with patch(
        "custom_components.heima.runtime.reactions.security_presence_simulation.dt_util.now",
        return_value=datetime(2026, 4, 4, 19, 0, 0, tzinfo=timezone.utc),
    ):
        diagnostics = reaction.diagnostics()

    assert diagnostics["recent_source_reaction_count"] == 2
    assert diagnostics["tonight_plan_count"] == 2
    assert len(diagnostics["tonight_plan_preview"]) == 2
    assert diagnostics["tonight_plan_preview"][0]["source_reaction_id"] == "light-src-1"


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
    normalized = normalize_room_signal_assist_config(
        {
            "trigger_signal_entities": ["sensor.legacy_humidity"],
            "primary_signal_entities": ["sensor.generic_temperature"],
            "humidity_rise_threshold": 8.0,
            "primary_rise_threshold": 1.5,
            "primary_threshold": 2.0,
            "primary_threshold_mode": "above",
            "temperature_signal_entities": ["sensor.legacy_temperature"],
            "corroboration_signal_entities": ["sensor.generic_humidity"],
            "temperature_rise_threshold": 0.8,
            "corroboration_rise_threshold": 5.0,
            "corroboration_threshold": 6.0,
            "corroboration_threshold_mode": "drop",
            "primary_signal_name": "temperature",
            "corroboration_signal_name": "humidity",
        }
    )

    assert normalized["primary_signal_entities"] == ["sensor.generic_temperature"]
    assert normalized["primary_rise_threshold"] == 1.5
    assert normalized["primary_threshold"] == 2.0
    assert normalized["primary_threshold_mode"] == "above"
    assert normalized["corroboration_signal_entities"] == ["sensor.generic_humidity"]
    assert normalized["corroboration_rise_threshold"] == 5.0
    assert normalized["corroboration_threshold"] == 6.0
    assert normalized["corroboration_threshold_mode"] == "drop"


def test_room_lighting_assist_reaction_built_and_registered():
    engine = _make_engine(options={
        "reactions": {
            "configured": {
                "la1": {
                    "reaction_class": "RoomLightingAssistReaction",
                    "room_id": "living",
                    "primary_signal_entities": ["sensor.living_room_lux"],
                    "primary_threshold": 120.0,
                    "primary_signal_name": "room_lux",
                    "primary_threshold_mode": "below",
                    "entity_steps": [
                        {
                            "entity_id": "light.living_main",
                            "action": "on",
                            "brightness": 144,
                            "color_temp_kelvin": 2900,
                            "rgb_color": None,
                        }
                    ],
                }
            }
        }
    })

    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    reaction = engine._reactions[0]
    assert isinstance(reaction, RoomLightingAssistReaction)
    assert reaction.reaction_id == "la1"


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
