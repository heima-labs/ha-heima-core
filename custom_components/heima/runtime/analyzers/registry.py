"""Registry for built-in learning pattern plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .base import IPatternAnalyzer
from .cross_domain import CompositePatternCatalogAnalyzer
from .heating import HeatingPatternAnalyzer
from .lighting import LightingPatternAnalyzer
from .presence import PresencePatternAnalyzer


@dataclass(frozen=True)
class AdminAuthoredTemplateDescriptor:
    """A bounded admin-authored proposal template exposed by a plugin."""

    template_id: str
    reaction_type: str
    title: str
    description: str
    config_schema_id: str
    implemented: bool = False


@dataclass(frozen=True)
class LearningPatternPluginDescriptor:
    """Minimal built-in metadata for one Learning Pattern Plugin."""

    plugin_id: str
    analyzer_id: str
    plugin_family: str
    proposal_types: tuple[str, ...]
    reaction_targets: tuple[str, ...]
    supports_admin_authored: bool = False
    admin_authored_templates: tuple[AdminAuthoredTemplateDescriptor, ...] = ()


@dataclass(frozen=True)
class RegisteredLearningPlugin:
    """One registered learning plugin entry."""

    descriptor: LearningPatternPluginDescriptor
    analyzer: IPatternAnalyzer
    enabled: bool = True


class LearningPluginRegistry:
    """Small built-in registry for learning pattern plugins in v1."""

    def __init__(self) -> None:
        self._plugins: list[RegisteredLearningPlugin] = []

    def register(
        self,
        *,
        descriptor: LearningPatternPluginDescriptor,
        analyzer: IPatternAnalyzer,
        enabled: bool = True,
    ) -> None:
        plugin_id = descriptor.plugin_id
        if any(item.descriptor.plugin_id == plugin_id for item in self._plugins):
            raise ValueError(f"Duplicate learning plugin_id: {plugin_id}")
        self._plugins.append(
            RegisteredLearningPlugin(
                descriptor=descriptor,
                analyzer=analyzer,
                enabled=enabled,
            )
        )

    def analyzers(self, *, enabled_only: bool = True) -> tuple[IPatternAnalyzer, ...]:
        return tuple(
            item.analyzer
            for item in self._plugins
            if item.enabled or not enabled_only
        )

    def descriptors(
        self, *, enabled_only: bool = False
    ) -> tuple[LearningPatternPluginDescriptor, ...]:
        return tuple(
            item.descriptor
            for item in self._plugins
            if item.enabled or not enabled_only
        )

    def admin_authored_descriptors(
        self, *, enabled_only: bool = True
    ) -> tuple[LearningPatternPluginDescriptor, ...]:
        return tuple(
            item.descriptor
            for item in self._plugins
            if item.descriptor.supports_admin_authored
            and (item.enabled or not enabled_only)
        )

    def admin_authored_templates(
        self, *, enabled_only: bool = True
    ) -> tuple[AdminAuthoredTemplateDescriptor, ...]:
        templates: list[AdminAuthoredTemplateDescriptor] = []
        for item in self._plugins:
            if not item.descriptor.supports_admin_authored:
                continue
            if enabled_only and not item.enabled:
                continue
            templates.extend(item.descriptor.admin_authored_templates)
        return tuple(templates)

    def get_admin_authored_template(
        self, template_id: str, *, enabled_only: bool = True
    ) -> AdminAuthoredTemplateDescriptor | None:
        target = template_id.strip()
        if not target:
            return None
        for template in self.admin_authored_templates(enabled_only=enabled_only):
            if template.template_id == target:
                return template
        return None

    def diagnostics(self) -> list[dict[str, object]]:
        return [
            {
                "plugin_id": item.descriptor.plugin_id,
                "analyzer_id": item.descriptor.analyzer_id,
                "plugin_family": item.descriptor.plugin_family,
                "proposal_types": list(item.descriptor.proposal_types),
                "reaction_targets": list(item.descriptor.reaction_targets),
                "supports_admin_authored": item.descriptor.supports_admin_authored,
                "admin_authored_templates": list(
                    _template_diagnostics(item.descriptor.admin_authored_templates)
                ),
                "enabled": item.enabled,
            }
            for item in self._plugins
        ]

    def __len__(self) -> int:
        return len(self._plugins)

    def __iter__(self) -> Iterable[RegisteredLearningPlugin]:
        return iter(self._plugins)


def create_builtin_learning_plugin_registry(
    *, enabled_families: set[str] | None = None
) -> LearningPluginRegistry:
    """Create the built-in learning plugin registry used by Heima v1."""
    registry = LearningPluginRegistry()
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.presence_preheat",
            analyzer_id="PresencePatternAnalyzer",
            plugin_family="presence",
            proposal_types=("presence_preheat",),
            reaction_targets=("PresencePatternReaction",),
            supports_admin_authored=False,
            admin_authored_templates=(),
        ),
        analyzer=PresencePatternAnalyzer(),
        enabled=_is_enabled("presence", enabled_families),
    )
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.heating_preferences",
            analyzer_id="HeatingPatternAnalyzer",
            plugin_family="heating",
            proposal_types=("heating_preference", "heating_eco"),
            reaction_targets=("HeatingPreferenceReaction", "HeatingEcoReaction"),
            supports_admin_authored=False,
            admin_authored_templates=(),
        ),
        analyzer=HeatingPatternAnalyzer(),
        enabled=_is_enabled("heating", enabled_families),
    )
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.lighting_routines",
            analyzer_id="LightingPatternAnalyzer",
            plugin_family="lighting",
            proposal_types=("lighting_scene_schedule",),
            reaction_targets=("LightingScheduleReaction",),
            supports_admin_authored=True,
            admin_authored_templates=(
                AdminAuthoredTemplateDescriptor(
                    template_id="lighting.scene_schedule.basic",
                    reaction_type="lighting_scene_schedule",
                    title="Lighting Schedule",
                    description="Create a room-based recurring lighting schedule.",
                    config_schema_id="lighting_scene_schedule.basic.v1",
                    implemented=True,
                ),
            ),
        ),
        analyzer=LightingPatternAnalyzer(),
        enabled=_is_enabled("lighting", enabled_families),
    )
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.composite_room_assist",
            analyzer_id="CompositePatternCatalogAnalyzer",
            plugin_family="composite_room_assist",
            proposal_types=(
                "room_signal_assist",
                "room_cooling_assist",
                "room_air_quality_assist",
                "room_darkness_lighting_assist",
            ),
            reaction_targets=("RoomSignalAssistReaction", "RoomLightingAssistReaction"),
            supports_admin_authored=True,
            admin_authored_templates=(
                AdminAuthoredTemplateDescriptor(
                    template_id="room.signal_assist.basic",
                    reaction_type="room_signal_assist",
                    title="Room Signal Assist",
                    description="Create a room assist automation driven by a primary room signal.",
                    config_schema_id="room_signal_assist.basic.v1",
                    implemented=True,
                ),
                AdminAuthoredTemplateDescriptor(
                    template_id="room.darkness_lighting_assist.basic",
                    reaction_type="room_darkness_lighting_assist",
                    title="Darkness Lighting Assist",
                    description="Create a room lighting assist that reacts to darkness conditions.",
                    config_schema_id="room_darkness_lighting_assist.basic.v1",
                    implemented=True,
                ),
            ),
        ),
        analyzer=CompositePatternCatalogAnalyzer(),
        enabled=_is_enabled("composite_room_assist", enabled_families),
    )
    return registry


def _is_enabled(plugin_family: str, enabled_families: set[str] | None) -> bool:
    if enabled_families is None:
        return True
    return plugin_family in enabled_families


def _template_diagnostics(
    templates: tuple[AdminAuthoredTemplateDescriptor, ...]
) -> list[dict[str, str]]:
    return [
        {
            "template_id": item.template_id,
            "reaction_type": item.reaction_type,
            "title": item.title,
            "description": item.description,
            "config_schema_id": item.config_schema_id,
            "implemented": item.implemented,
        }
        for item in templates
    ]
