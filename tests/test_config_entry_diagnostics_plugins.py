"""Tests for config entry diagnostics plugin metadata."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.const import DOMAIN
from custom_components.heima.diagnostics import async_get_config_entry_diagnostics
from custom_components.heima.runtime.analyzers import create_builtin_learning_plugin_registry


class _CoordinatorStub:
    def __init__(self) -> None:
        self.data = {"health": "ok"}
        self.engine = SimpleNamespace(diagnostics=lambda: {"engine": "ok"})
        self.scheduler = SimpleNamespace(diagnostics=lambda: {"scheduler": "ok"})
        self._event_store = SimpleNamespace(diagnostics=lambda: {"total_events": 1})
        self._proposal_engine = SimpleNamespace(diagnostics=lambda: {"total": 0})
        self.learning_plugin_registry = create_builtin_learning_plugin_registry()


async def test_config_entry_diagnostics_includes_learning_and_reaction_plugins():
    coordinator = _CoordinatorStub()
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    plugins = diagnostics["runtime"]["plugins"]

    learning = plugins["learning_pattern_plugins"]
    reactions = plugins["reaction_plugins"]

    assert any(item["plugin_id"] == "builtin.lighting_routines" for item in learning)
    assert any(item["plugin_id"] == "builtin.composite_room_assist" for item in learning)
    assert any(item["reaction_class"] == "RoomSignalAssistReaction" for item in reactions)
    assert any(item["reaction_class"] == "RoomLightingAssistReaction" for item in reactions)


async def test_config_entry_diagnostics_exposes_heating_observed_provenance():
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "heating": {
                "observed_source": "heima",
                "observed_provenance": {
                    "source": "reaction:heat_pref_test",
                    "origin_reaction_id": "heat_pref_test",
                    "origin_reaction_class": "HeatingPreferenceReaction",
                    "expected_domains": ["climate"],
                    "expected_subject_ids": ["climate.test_thermostat"],
                },
            }
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]

    assert diagnostics["runtime"]["engine"]["heating"]["observed_source"] == "heima"
    assert diagnostics["runtime"]["engine"]["heating"]["observed_provenance"] == {
        "source": "reaction:heat_pref_test",
        "origin_reaction_id": "heat_pref_test",
        "origin_reaction_class": "HeatingPreferenceReaction",
        "expected_domains": ["climate"],
        "expected_subject_ids": ["climate.test_thermostat"],
    }


async def test_config_entry_diagnostics_exposes_learning_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator._proposal_engine = SimpleNamespace(
        diagnostics=lambda: {
            "total": 3,
            "pending": 2,
            "pending_stale": 1,
            "proposals": [
                {
                    "id": "p1",
                    "type": "lighting_scene_schedule",
                    "status": "pending",
                    "confidence": 0.95,
                    "description": "Living lights",
                    "is_stale": False,
                    "updated_at": "2026-03-26T10:00:00+00:00",
                },
                {
                    "id": "p2",
                    "type": "room_signal_assist",
                    "status": "pending",
                    "confidence": 0.85,
                    "description": "Bathroom assist",
                    "is_stale": True,
                    "updated_at": "2026-03-26T09:00:00+00:00",
                },
                {
                    "id": "p3",
                    "type": "heating_preference",
                    "status": "accepted",
                    "confidence": 0.75,
                    "description": "Heating home",
                    "is_stale": False,
                    "updated_at": "2026-03-26T08:00:00+00:00",
                },
            ],
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["learning_summary"]

    assert summary["plugin_count"] >= 4
    assert summary["family_count"] >= 4
    assert summary["proposal_total"] == 3
    assert summary["pending_total"] == 2
    assert summary["pending_stale_total"] == 1

    lighting = summary["families"]["lighting"]
    assert lighting["pending"] == 1
    assert "lighting_scene_schedule" in lighting["proposal_types"]

    composite = summary["plugins"]["builtin.composite_room_assist"]
    assert composite["pending"] == 1
    assert composite["stale_pending"] == 1

    heating = summary["plugins"]["builtin.heating_preferences"]
    assert heating["accepted"] == 1
