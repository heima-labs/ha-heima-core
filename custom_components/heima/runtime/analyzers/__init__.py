"""Learning analyzers package."""

from .base import IPatternAnalyzer, ReactionProposal
from .cross_domain import (
    CompositePatternCatalogAnalyzer,
    CrossDomainPatternAnalyzer,
    RoomCoolingPatternAnalyzer,
)
from .heating import HeatingPatternAnalyzer
from .lighting import LightingPatternAnalyzer
from .presence import PresencePatternAnalyzer
from .registry import (
    AdminAuthoredTemplateDescriptor,
    LearningPatternPluginDescriptor,
    LearningPluginRegistry,
    create_builtin_learning_plugin_registry,
)


def builtin_learning_pattern_plugins() -> tuple[IPatternAnalyzer, ...]:
    """Return the built-in Learning Pattern Plugins enabled by default."""
    return create_builtin_learning_plugin_registry().analyzers()


def builtin_learning_pattern_plugin_descriptors() -> tuple[LearningPatternPluginDescriptor, ...]:
    """Return minimal metadata for built-in Learning Pattern Plugins."""
    return create_builtin_learning_plugin_registry().descriptors()

__all__ = [
    "IPatternAnalyzer",
    "ReactionProposal",
    "AdminAuthoredTemplateDescriptor",
    "LearningPatternPluginDescriptor",
    "LearningPluginRegistry",
    "create_builtin_learning_plugin_registry",
    "builtin_learning_pattern_plugins",
    "builtin_learning_pattern_plugin_descriptors",
    "CompositePatternCatalogAnalyzer",
    "CrossDomainPatternAnalyzer",
    "RoomCoolingPatternAnalyzer",
    "HeatingPatternAnalyzer",
    "LightingPatternAnalyzer",
    "PresencePatternAnalyzer",
]
