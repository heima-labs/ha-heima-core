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
    assert descriptors[0].supports_admin_authored is False
    assert descriptors[0].admin_authored_templates == ()
    assert descriptors[2].supports_admin_authored is True
    assert tuple(item.template_id for item in descriptors[2].admin_authored_templates) == (
        "lighting.scene_schedule.basic",
    )
    assert descriptors[3].supports_admin_authored is True
    assert tuple(item.template_id for item in descriptors[3].admin_authored_templates) == (
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
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
        "supports_admin_authored": True,
        "admin_authored_templates": [
            {
                "template_id": "room.signal_assist.basic",
                "reaction_type": "room_signal_assist",
                "title": "Room Signal Assist",
                "description": "Create a room assist automation driven by a primary room signal.",
                "config_schema_id": "room_signal_assist.basic.v1",
                "implemented": True,
            },
            {
                "template_id": "room.darkness_lighting_assist.basic",
                "reaction_type": "room_darkness_lighting_assist",
                "title": "Darkness Lighting Assist",
                "description": "Create a room lighting assist that reacts to darkness conditions.",
                "config_schema_id": "room_darkness_lighting_assist.basic.v1",
                "implemented": True,
            },
        ],
        "enabled": True,
    }


def test_builtin_learning_plugin_registry_can_disable_families():
    registry = create_builtin_learning_plugin_registry(
        enabled_families={"presence", "lighting"}
    )

    assert [analyzer.analyzer_id for analyzer in registry.analyzers()] == [
        "PresencePatternAnalyzer",
        "LightingPatternAnalyzer",
    ]
    diagnostics = registry.diagnostics()
    enabled = {item["plugin_family"] for item in diagnostics if item["enabled"] is True}
    disabled = {item["plugin_family"] for item in diagnostics if item["enabled"] is False}
    assert enabled == {"presence", "lighting"}
    assert disabled == {"heating", "composite_room_assist"}


def test_builtin_learning_plugin_registry_exposes_admin_authored_templates():
    registry = create_builtin_learning_plugin_registry()

    assert [d.plugin_family for d in registry.admin_authored_descriptors()] == [
        "lighting",
        "composite_room_assist",
    ]
    assert [t.template_id for t in registry.admin_authored_templates()] == [
        "lighting.scene_schedule.basic",
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
    ]
    assert [t.template_id for t in registry.admin_authored_templates(implemented_only=True)] == [
        "lighting.scene_schedule.basic",
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
    ]
    assert (
        registry.get_admin_authored_template("room.signal_assist.basic").reaction_type
        == "room_signal_assist"
    )
    assert (
        registry.get_admin_authored_template(
            "room.signal_assist.basic", implemented_only=True
        ).reaction_type
        == "room_signal_assist"
    )
    assert registry.get_admin_authored_template("missing.template") is None


def test_builtin_learning_plugin_registry_filters_disabled_admin_authored_templates():
    registry = create_builtin_learning_plugin_registry(enabled_families={"lighting"})

    assert [t.template_id for t in registry.admin_authored_templates()] == [
        "lighting.scene_schedule.basic"
    ]
    assert registry.get_admin_authored_template("room.signal_assist.basic") is None
    assert (
        registry.get_admin_authored_template(
            "room.signal_assist.basic", enabled_only=False
        ).reaction_type
        == "room_signal_assist"
    )
