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
    assert any(
        item["plugin_id"] == "builtin.lighting_routines"
        and item["supports_admin_authored"] is True
        and item["admin_authored_templates"][0]["template_id"]
        == "lighting.scene_schedule.basic"
        for item in learning
    )
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
    assert summary["config_source"] == "learning.enabled_plugin_families"
    assert "lighting" in summary["enabled_plugin_families"]
    assert summary["disabled_plugin_families"] == []

    lighting = summary["families"]["lighting"]
    assert lighting["pending"] == 1
    assert "lighting_scene_schedule" in lighting["proposal_types"]
    assert lighting["admin_authorable"] is True
    assert lighting["admin_authored_templates"] == ["lighting.scene_schedule.basic"]

    composite = summary["plugins"]["builtin.composite_room_assist"]
    assert composite["pending"] == 1
    assert composite["stale_pending"] == 1
    assert composite["supports_admin_authored"] is True
    assert composite["admin_authored_templates"] == [
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
    ]

    heating = summary["plugins"]["builtin.heating_preferences"]
    assert heating["accepted"] == 1
    assert heating["supports_admin_authored"] is False


async def test_config_entry_diagnostics_exposes_disabled_learning_families() -> None:
    coordinator = _CoordinatorStub()
    coordinator.learning_plugin_registry = create_builtin_learning_plugin_registry(
        enabled_families={"presence", "lighting"}
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

    assert summary["enabled_plugin_families"] == ["lighting", "presence"]
    assert summary["disabled_plugin_families"] == ["composite_room_assist", "heating"]


async def test_config_entry_diagnostics_exposes_configured_reaction_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"r1":{"origin":"learned","author_kind":"heima"},'
                '"r2":{"origin":"admin_authored","author_kind":"admin",'
                '"source_template_id":"room.signal_assist.basic"}}'
                if key == "heima_reactions_active"
                else None
            )
        ),
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
    summary = diagnostics["runtime"]["plugins"]["configured_reaction_summary"]

    assert summary["total"] == 2
    assert summary["by_origin"] == {"admin_authored": 1, "learned": 1}
    assert summary["by_author_kind"] == {"admin": 1, "heima": 1}
    assert summary["by_template_id"] == {
        "room.signal_assist.basic": 1,
        "unspecified": 1,
    }
    assert summary["reaction_ids"] == ["r1", "r2"]
