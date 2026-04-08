"""Tests for built-in Learning Pattern Plugin registry."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers import (
    builtin_learning_pattern_plugin_descriptors,
    builtin_learning_pattern_plugins,
    create_builtin_learning_plugin_registry,
)
from custom_components.heima.runtime.analyzers.policy import learning_policy_from_config


def test_builtin_learning_pattern_plugins_exposes_default_learning_plugins():
    plugins = tuple(builtin_learning_pattern_plugins())

    assert [plugin.analyzer_id for plugin in plugins] == [
        "PresencePatternAnalyzer",
        "HeatingPatternAnalyzer",
        "LightingPatternAnalyzer",
        "CompositePatternCatalogAnalyzer",
        "SecurityPresenceSimulationAnalyzer",
    ]


def test_builtin_learning_pattern_plugin_descriptors_expose_minimal_metadata():
    descriptors = builtin_learning_pattern_plugin_descriptors()

    assert [d.plugin_id for d in descriptors] == [
        "builtin.presence_preheat",
        "builtin.heating_preferences",
        "builtin.lighting_routines",
        "builtin.composite_room_assist",
        "builtin.security_presence_simulation",
    ]
    assert [d.plugin_family for d in descriptors] == [
        "presence",
        "heating",
        "lighting",
        "composite_room_assist",
        "security_presence_simulation",
    ]
    assert descriptors[-2].proposal_types == (
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
        "room_darkness_lighting_assist",
        "room_vacancy_lighting_off",
    )
    assert descriptors[-2].reaction_targets == (
        "RoomSignalAssistReaction",
        "RoomLightingAssistReaction",
        "RoomLightingVacancyOffReaction",
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
        "room.vacancy_lighting_off.basic",
    )
    assert descriptors[4].supports_admin_authored is True
    assert tuple(item.template_id for item in descriptors[4].admin_authored_templates) == (
        "security.vacation_presence_simulation.basic",
    )


def test_builtin_learning_plugin_registry_exposes_default_plugins_and_metadata():
    registry = create_builtin_learning_plugin_registry()

    assert len(registry) == 5
    assert [item.descriptor.plugin_id for item in registry] == [
        "builtin.presence_preheat",
        "builtin.heating_preferences",
        "builtin.lighting_routines",
        "builtin.composite_room_assist",
        "builtin.security_presence_simulation",
    ]
    assert [analyzer.analyzer_id for analyzer in registry.analyzers()] == [
        "PresencePatternAnalyzer",
        "HeatingPatternAnalyzer",
        "LightingPatternAnalyzer",
        "CompositePatternCatalogAnalyzer",
        "SecurityPresenceSimulationAnalyzer",
    ]
    assert registry.diagnostics()[-1] == {
        "plugin_id": "builtin.security_presence_simulation",
        "analyzer_id": "SecurityPresenceSimulationAnalyzer",
        "plugin_family": "security_presence_simulation",
        "proposal_types": ["vacation_presence_simulation"],
        "reaction_targets": ["VacationPresenceSimulationReaction"],
        "has_lifecycle_hooks": True,
        "supports_admin_authored": True,
        "admin_authored_templates": [
            {
                "template_id": "security.vacation_presence_simulation.basic",
                "reaction_type": "vacation_presence_simulation",
                "title": "Vacation Presence Simulation",
                "description": "Create a security-owned vacation presence simulation driven by learned lighting behavior.",
                "config_schema_id": "vacation_presence_simulation.basic.v1",
                "implemented": True,
                "flow_step_id": "admin_authored_security_presence_simulation",
            },
        ],
        "enabled": True,
    }
    assert registry.diagnostics()[-2] == {
        "plugin_id": "builtin.composite_room_assist",
        "analyzer_id": "CompositePatternCatalogAnalyzer",
        "plugin_family": "composite_room_assist",
        "proposal_types": [
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
            "room_darkness_lighting_assist",
            "room_vacancy_lighting_off",
        ],
        "reaction_targets": [
            "RoomSignalAssistReaction",
            "RoomLightingAssistReaction",
            "RoomLightingVacancyOffReaction",
        ],
        "has_lifecycle_hooks": True,
        "supports_admin_authored": True,
        "admin_authored_templates": [
            {
                "template_id": "room.signal_assist.basic",
                "reaction_type": "room_signal_assist",
                "title": "Room Signal Assist",
                "description": "Create a room assist automation driven by a primary room signal.",
                "config_schema_id": "room_signal_assist.basic.v1",
                "implemented": True,
                "flow_step_id": "admin_authored_room_signal_assist",
            },
            {
                "template_id": "room.darkness_lighting_assist.basic",
                "reaction_type": "room_darkness_lighting_assist",
                "title": "Darkness Lighting Assist",
                "description": "Create a room lighting assist that reacts to darkness conditions.",
                "config_schema_id": "room_darkness_lighting_assist.basic.v1",
                "implemented": True,
                "flow_step_id": "admin_authored_room_darkness_lighting_assist",
            },
            {
                "template_id": "room.vacancy_lighting_off.basic",
                "reaction_type": "room_vacancy_lighting_off",
                "title": "Vacancy Lights Off",
                "description": "Create a room lighting assist that turns lights off after vacancy persists.",
                "config_schema_id": "room_vacancy_lighting_off.basic.v1",
                "implemented": True,
                "flow_step_id": "admin_authored_room_vacancy_lighting_off",
            },
        ],
        "enabled": True,
    }


def test_builtin_learning_plugin_registry_can_disable_families():
    registry = create_builtin_learning_plugin_registry(enabled_families={"presence", "lighting"})

    assert [analyzer.analyzer_id for analyzer in registry.analyzers()] == [
        "PresencePatternAnalyzer",
        "LightingPatternAnalyzer",
    ]
    diagnostics = registry.diagnostics()
    enabled = {item["plugin_family"] for item in diagnostics if item["enabled"] is True}
    disabled = {item["plugin_family"] for item in diagnostics if item["enabled"] is False}
    assert enabled == {"presence", "lighting"}
    assert disabled == {"heating", "composite_room_assist", "security_presence_simulation"}


def test_builtin_learning_plugin_registry_exposes_admin_authored_templates():
    registry = create_builtin_learning_plugin_registry()

    assert [d.plugin_family for d in registry.admin_authored_descriptors()] == [
        "lighting",
        "composite_room_assist",
        "security_presence_simulation",
    ]
    assert [t.template_id for t in registry.admin_authored_templates()] == [
        "lighting.scene_schedule.basic",
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
        "room.vacancy_lighting_off.basic",
        "security.vacation_presence_simulation.basic",
    ]
    assert [t.template_id for t in registry.admin_authored_templates(implemented_only=True)] == [
        "lighting.scene_schedule.basic",
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
        "room.vacancy_lighting_off.basic",
        "security.vacation_presence_simulation.basic",
    ]
    assert (
        registry.get_admin_authored_template("room.signal_assist.basic").reaction_type
        == "room_signal_assist"
    )
    assert (
        registry.get_admin_authored_template("room.signal_assist.basic").flow_step_id
        == "admin_authored_room_signal_assist"
    )
    assert (
        registry.get_admin_authored_template(
            "room.signal_assist.basic", implemented_only=True
        ).reaction_type
        == "room_signal_assist"
    )
    assert registry.get_admin_authored_template("missing.template") is None


def test_builtin_learning_plugin_registry_exposes_lifecycle_hooks_by_reaction_type():
    registry = create_builtin_learning_plugin_registry()

    assert registry.lifecycle_hooks_for("presence_preheat") is not None
    assert registry.lifecycle_hooks_for("heating_preference") is not None
    assert registry.lifecycle_hooks_for("heating_eco") is not None
    assert registry.lifecycle_hooks_for("lighting_scene_schedule") is not None
    assert registry.lifecycle_hooks_for("room_signal_assist") is not None
    assert registry.lifecycle_hooks_for("vacation_presence_simulation") is not None
    assert registry.lifecycle_hooks_for("missing.reaction") is None


def test_builtin_learning_plugin_registry_passes_composite_quality_policy():
    registry = create_builtin_learning_plugin_registry(
        learning_config={
            "composite_quality_policy": {
                "followup_entity_min_ratio": 0.75,
                "followup_entity_min_episodes": 4,
                "corroboration_promote_min_ratio": 0.8,
                "corroboration_promote_min_episodes": 4,
                "minimal_evidence_confidence_cap": 0.82,
            }
        }
    )

    composite = next(
        analyzer
        for analyzer in registry.analyzers()
        if analyzer.analyzer_id == "CompositePatternCatalogAnalyzer"
    )
    assert composite._quality_policy.followup_entity_min_ratio == 0.75  # noqa: SLF001
    assert composite._quality_policy.followup_entity_min_episodes == 4  # noqa: SLF001
    assert composite._quality_policy.minimal_evidence_confidence_cap == 0.82  # noqa: SLF001


def test_builtin_learning_plugin_registry_passes_composite_lifecycle_policy():
    registry = create_builtin_learning_plugin_registry(
        learning_config={
            "composite_lifecycle_policy": {
                "room_signal_primary_threshold_max_gap": 2.0,
                "room_signal_corroboration_threshold_max_gap": 0.5,
                "room_darkness_primary_threshold_max_gap": 15.0,
                "room_darkness_brightness_max_gap": 24,
                "room_darkness_color_temp_max_gap": 180,
            }
        }
    )

    hooks = registry.lifecycle_hooks_for("room_signal_assist")
    assert hooks is not None
    closure_cells = hooks.should_suppress_followup.__closure__  # type: ignore[union-attr]
    assert closure_cells is not None
    policy = closure_cells[0].cell_contents
    assert policy.room_signal_primary_threshold_max_gap == 2.0
    assert policy.room_signal_corroboration_threshold_max_gap == 0.5
    assert policy.room_darkness_primary_threshold_max_gap == 15.0
    assert policy.room_darkness_brightness_max_gap == 24
    assert policy.room_darkness_color_temp_max_gap == 180


def test_learning_policy_from_config_uses_defaults_and_family_aliases():
    policies = learning_policy_from_config(
        {
            "presence": {"min_occurrences": 7, "min_weeks": 3},
            "lighting": {"min_occurrences": 6},
            "composite": {"min_weeks": 4},
            "security_presence_simulation": {"min_occurrences": 5, "min_weeks": 3},
            "heating": {"min_events": 12, "min_eco_sessions": 4, "min_weeks": 5},
        }
    )

    assert policies.presence.min_occurrences == 7
    assert policies.presence.min_weeks == 3
    assert policies.lighting.min_occurrences == 6
    assert policies.lighting.min_weeks == 2
    assert policies.composite_room_assist.min_occurrences == 5
    assert policies.composite_room_assist.min_weeks == 4
    assert policies.security_presence_simulation.min_occurrences == 5
    assert policies.security_presence_simulation.min_weeks == 3
    assert policies.heating.preference_min_events == 12
    assert policies.heating.preference_min_weeks == 5
    assert policies.heating.eco_min_sessions == 4
    assert policies.heating.eco_min_weeks == 5


def test_builtin_learning_plugin_registry_passes_family_learning_policies():
    registry = create_builtin_learning_plugin_registry(
        learning_config={
            "presence": {"min_occurrences": 7, "min_weeks": 3},
            "lighting": {"min_occurrences": 6, "min_weeks": 4},
            "security_presence_simulation": {"min_occurrences": 5, "min_weeks": 3},
        }
    )

    analyzers = {analyzer.analyzer_id: analyzer for analyzer in registry.analyzers()}

    presence = analyzers["PresencePatternAnalyzer"]
    assert presence.min_arrivals == 7  # noqa: SLF001
    assert presence.min_weeks == 3  # noqa: SLF001

    lighting = analyzers["LightingPatternAnalyzer"]
    assert lighting.min_occurrences == 6  # noqa: SLF001
    assert lighting.min_weeks == 4  # noqa: SLF001

    security_presence = analyzers["SecurityPresenceSimulationAnalyzer"]
    assert security_presence.min_occurrences == 5  # noqa: SLF001
    assert security_presence.min_weeks == 3  # noqa: SLF001


def test_builtin_learning_plugin_registry_passes_composite_family_learning_policy():
    registry = create_builtin_learning_plugin_registry(
        learning_config={
            "composite": {"min_occurrences": 7, "min_weeks": 4},
        }
    )

    composite = next(
        analyzer
        for analyzer in registry.analyzers()
        if analyzer.analyzer_id == "CompositePatternCatalogAnalyzer"
    )
    assert composite._catalog  # noqa: SLF001
    assert all(item.min_occurrences == 7 for item in composite._catalog)  # noqa: SLF001
    assert all(item.min_weeks == 4 for item in composite._catalog)  # noqa: SLF001


def test_builtin_learning_plugin_registry_passes_heating_family_learning_policy():
    registry = create_builtin_learning_plugin_registry(
        learning_config={
            "heating": {
                "preference_min_events": 12,
                "preference_min_weeks": 4,
                "eco_min_sessions": 5,
                "eco_min_weeks": 3,
            }
        }
    )

    heating = next(
        analyzer
        for analyzer in registry.analyzers()
        if analyzer.analyzer_id == "HeatingPatternAnalyzer"
    )
    assert heating.preference_min_events == 12  # noqa: SLF001
    assert heating.preference_min_weeks == 4  # noqa: SLF001
    assert heating.eco_min_sessions == 5  # noqa: SLF001
    assert heating.eco_min_weeks == 3  # noqa: SLF001


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
