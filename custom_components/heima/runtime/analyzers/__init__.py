"""Learning analyzers package."""

from ..plugin_contracts import IBehaviorAnalyzer
from .activity import ActivityAnalyzer
from .anomaly import ANOMALY_RULE_CATALOG, AnomalyAnalyzer, AnomalyRule
from .base import IPatternAnalyzer, ReactionProposal
from .cross_domain import (
    CompositePatternCatalogAnalyzer,
    CrossDomainPatternAnalyzer,
    RoomCoolingPatternAnalyzer,
)
from .heating import HeatingPatternAnalyzer
from .lifecycle import ProposalLifecycleHooks, ProposalReviewGrouping
from .lighting import LightingPatternAnalyzer
from .presence import PresencePatternAnalyzer
from .registry import (
    AdminAuthoredTemplateDescriptor,
    LearningPatternPluginDescriptor,
    LearningPluginRegistry,
    create_builtin_learning_plugin_registry,
)
from .security_presence_simulation import SecurityPresenceSimulationAnalyzer


def builtin_learning_pattern_plugins() -> tuple[IBehaviorAnalyzer, ...]:
    """Return the built-in Learning Pattern Plugins enabled by default."""
    return create_builtin_learning_plugin_registry().analyzers()


def builtin_learning_pattern_plugin_descriptors() -> tuple[LearningPatternPluginDescriptor, ...]:
    """Return minimal metadata for built-in Learning Pattern Plugins."""
    return create_builtin_learning_plugin_registry().descriptors()


__all__ = [
    "IPatternAnalyzer",
    "ActivityAnalyzer",
    "AnomalyAnalyzer",
    "AnomalyRule",
    "ANOMALY_RULE_CATALOG",
    "ReactionProposal",
    "AdminAuthoredTemplateDescriptor",
    "LearningPatternPluginDescriptor",
    "LearningPluginRegistry",
    "ProposalLifecycleHooks",
    "ProposalReviewGrouping",
    "create_builtin_learning_plugin_registry",
    "builtin_learning_pattern_plugins",
    "builtin_learning_pattern_plugin_descriptors",
    "CompositePatternCatalogAnalyzer",
    "CrossDomainPatternAnalyzer",
    "RoomCoolingPatternAnalyzer",
    "HeatingPatternAnalyzer",
    "LightingPatternAnalyzer",
    "PresencePatternAnalyzer",
    "SecurityPresenceSimulationAnalyzer",
]
