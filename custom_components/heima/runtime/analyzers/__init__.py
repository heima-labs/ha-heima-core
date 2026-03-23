"""Learning analyzers package."""

from dataclasses import dataclass
from typing import Iterable

from .base import IPatternAnalyzer, ReactionProposal
from .cross_domain import (
    CompositePatternCatalogAnalyzer,
    CrossDomainPatternAnalyzer,
    RoomCoolingPatternAnalyzer,
)
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


def builtin_learning_pattern_plugins() -> Iterable[IPatternAnalyzer]:
    """Return the built-in Learning Pattern Plugins enabled by default."""
    return (
        PresencePatternAnalyzer(),
        HeatingPatternAnalyzer(),
        LightingPatternAnalyzer(),
        CompositePatternCatalogAnalyzer(),
    )


def builtin_learning_pattern_plugin_descriptors() -> tuple[LearningPatternPluginDescriptor, ...]:
    """Return minimal metadata for built-in Learning Pattern Plugins."""
    return (
        LearningPatternPluginDescriptor(
            plugin_id="builtin.presence_preheat",
            analyzer_id="PresencePatternAnalyzer",
            plugin_family="presence",
            proposal_types=("presence_preheat",),
            reaction_targets=("PresencePatternReaction",),
        ),
        LearningPatternPluginDescriptor(
            plugin_id="builtin.heating_preferences",
            analyzer_id="HeatingPatternAnalyzer",
            plugin_family="heating",
            proposal_types=("heating_preference", "heating_eco"),
            reaction_targets=("HeatingPreferenceReaction", "HeatingEcoReaction"),
        ),
        LearningPatternPluginDescriptor(
            plugin_id="builtin.lighting_routines",
            analyzer_id="LightingPatternAnalyzer",
            plugin_family="lighting",
            proposal_types=("lighting_scene_schedule",),
            reaction_targets=("LightingScheduleReaction",),
        ),
        LearningPatternPluginDescriptor(
            plugin_id="builtin.composite_room_assist",
            analyzer_id="CompositePatternCatalogAnalyzer",
            plugin_family="composite_room_assist",
            proposal_types=(
                "room_signal_assist",
                "room_cooling_assist",
                "room_air_quality_assist",
            ),
            reaction_targets=("RoomSignalAssistReaction",),
        ),
    )

__all__ = [
    "IPatternAnalyzer",
    "ReactionProposal",
    "LearningPatternPluginDescriptor",
    "builtin_learning_pattern_plugins",
    "builtin_learning_pattern_plugin_descriptors",
    "CompositePatternCatalogAnalyzer",
    "CrossDomainPatternAnalyzer",
    "RoomCoolingPatternAnalyzer",
    "HeatingPatternAnalyzer",
    "LightingPatternAnalyzer",
    "PresencePatternAnalyzer",
]
