"""Tests for built-in Learning Pattern Plugin registry."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers import (
    builtin_learning_pattern_plugin_descriptors,
    builtin_learning_pattern_plugins,
    create_builtin_learning_plugin_registry,
)


def test_builtin_learning_pattern_plugins_exposes_default_learning_plugins():
    plugins = tuple(builtin_learning_pattern_plugins())

    assert [plugin.analyzer_id for plugin in plugins] == [
        "PresencePatternAnalyzer",
        "HeatingPatternAnalyzer",
        "LightingPatternAnalyzer",
        "CompositePatternCatalogAnalyzer",
    ]


def test_builtin_learning_pattern_plugin_descriptors_expose_minimal_metadata():
    descriptors = builtin_learning_pattern_plugin_descriptors()

    assert [d.plugin_id for d in descriptors] == [
        "builtin.presence_preheat",
        "builtin.heating_preferences",
        "builtin.lighting_routines",
        "builtin.composite_room_assist",
    ]
    assert [d.plugin_family for d in descriptors] == [
        "presence",
        "heating",
        "lighting",
        "composite_room_assist",
    ]
    assert descriptors[-1].proposal_types == (
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
        "room_darkness_lighting_assist",
    )
    assert descriptors[-1].reaction_targets == (
        "RoomSignalAssistReaction",
        "RoomLightingAssistReaction",
    )


def test_builtin_learning_plugin_registry_exposes_default_plugins_and_metadata():
    registry = create_builtin_learning_plugin_registry()

    assert len(registry) == 4
    assert [item.descriptor.plugin_id for item in registry] == [
        "builtin.presence_preheat",
        "builtin.heating_preferences",
        "builtin.lighting_routines",
        "builtin.composite_room_assist",
    ]
    assert [analyzer.analyzer_id for analyzer in registry.analyzers()] == [
        "PresencePatternAnalyzer",
        "HeatingPatternAnalyzer",
        "LightingPatternAnalyzer",
        "CompositePatternCatalogAnalyzer",
    ]
    assert registry.diagnostics()[-1] == {
        "plugin_id": "builtin.composite_room_assist",
        "analyzer_id": "CompositePatternCatalogAnalyzer",
        "plugin_family": "composite_room_assist",
        "proposal_types": [
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
            "room_darkness_lighting_assist",
        ],
        "reaction_targets": [
            "RoomSignalAssistReaction",
            "RoomLightingAssistReaction",
        ],
        "enabled": True,
    }
