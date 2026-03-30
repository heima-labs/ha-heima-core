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
class LearningPatternPluginDescriptor:
    """Minimal built-in metadata for one Learning Pattern Plugin."""

    plugin_id: str
    analyzer_id: str
    plugin_family: str
    proposal_types: tuple[str, ...]
    reaction_targets: tuple[str, ...]


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

    def diagnostics(self) -> list[dict[str, object]]:
        return [
            {
                "plugin_id": item.descriptor.plugin_id,
                "analyzer_id": item.descriptor.analyzer_id,
                "plugin_family": item.descriptor.plugin_family,
                "proposal_types": list(item.descriptor.proposal_types),
                "reaction_targets": list(item.descriptor.reaction_targets),
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
        ),
        analyzer=CompositePatternCatalogAnalyzer(),
        enabled=_is_enabled("composite_room_assist", enabled_families),
    )
    return registry


def _is_enabled(plugin_family: str, enabled_families: set[str] | None) -> bool:
    if enabled_families is None:
        return True
    return plugin_family in enabled_families
