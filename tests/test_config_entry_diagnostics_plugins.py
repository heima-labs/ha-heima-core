"""Tests for config entry diagnostics plugin metadata."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.const import DOMAIN
from custom_components.heima.diagnostics import async_get_config_entry_diagnostics


class _CoordinatorStub:
    def __init__(self) -> None:
        self.data = {"health": "ok"}
        self.engine = SimpleNamespace(diagnostics=lambda: {"engine": "ok"})
        self.scheduler = SimpleNamespace(diagnostics=lambda: {"scheduler": "ok"})
        self._event_store = SimpleNamespace(diagnostics=lambda: {"total_events": 1})
        self._proposal_engine = SimpleNamespace(diagnostics=lambda: {"total": 0})


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
