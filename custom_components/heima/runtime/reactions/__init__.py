from dataclasses import dataclass
from typing import Any, Callable

from .base import HeimaReaction
from .builtin import ConsecutiveStateReaction
from .heating import HeatingEcoReaction, HeatingPreferenceReaction
from .learning import ILearningBackend, NaiveLearningBackend
from .lighting_schedule import LightingScheduleReaction
from .patterns import ConsecutiveMatchDetector, IPatternDetector
from .presence import PresencePatternReaction
from .signal_assist import RoomSignalAssistReaction

ReactionPluginBuilder = Callable[[Any, str, dict[str, Any]], HeimaReaction | None]


@dataclass(frozen=True)
class ReactionPluginDescriptor:
    """Minimal built-in metadata for one Reaction Plugin."""

    reaction_class: str
    reaction_id_strategy: str
    supported_config_contracts: tuple[str, ...]
    supports_normalizer: bool


def builtin_reaction_plugin_builders() -> dict[str, ReactionPluginBuilder]:
    """Return built-in Reaction Plugin builders keyed by reaction_class."""
    return {
        "PresencePatternReaction": lambda engine, proposal_id, cfg: engine._build_presence_reaction(  # noqa: SLF001
            proposal_id, cfg
        ),
        "LightingScheduleReaction": lambda engine, proposal_id, cfg: engine._build_lighting_schedule_reaction(  # noqa: SLF001
            proposal_id, cfg
        ),
        "HeatingPreferenceReaction": lambda engine, proposal_id, cfg: engine._build_heating_preference_reaction(  # noqa: SLF001
            proposal_id, cfg
        ),
        "HeatingEcoReaction": lambda engine, proposal_id, cfg: engine._build_heating_eco_reaction(  # noqa: SLF001
            proposal_id, cfg
        ),
        "RoomSignalAssistReaction": lambda engine, proposal_id, cfg: engine._build_room_signal_assist_reaction(  # noqa: SLF001
            proposal_id, cfg
        ),
    }


def builtin_reaction_plugin_descriptors() -> tuple[ReactionPluginDescriptor, ...]:
    """Return minimal metadata for built-in Reaction Plugins."""
    return (
        ReactionPluginDescriptor(
            reaction_class="PresencePatternReaction",
            reaction_id_strategy="proposal_id",
            supported_config_contracts=("presence_preheat",),
            supports_normalizer=False,
        ),
        ReactionPluginDescriptor(
            reaction_class="LightingScheduleReaction",
            reaction_id_strategy="proposal_id",
            supported_config_contracts=("lighting_scene_schedule",),
            supports_normalizer=False,
        ),
        ReactionPluginDescriptor(
            reaction_class="HeatingPreferenceReaction",
            reaction_id_strategy="proposal_id",
            supported_config_contracts=("heating_preference",),
            supports_normalizer=False,
        ),
        ReactionPluginDescriptor(
            reaction_class="HeatingEcoReaction",
            reaction_id_strategy="proposal_id",
            supported_config_contracts=("heating_eco",),
            supports_normalizer=False,
        ),
        ReactionPluginDescriptor(
            reaction_class="RoomSignalAssistReaction",
            reaction_id_strategy="proposal_id",
            supported_config_contracts=("room_signal_assist", "room_cooling_assist"),
            supports_normalizer=True,
        ),
    )

__all__ = [
    "HeimaReaction",
    "ReactionPluginDescriptor",
    "ReactionPluginBuilder",
    "builtin_reaction_plugin_builders",
    "builtin_reaction_plugin_descriptors",
    "ConsecutiveStateReaction",
    "ConsecutiveMatchDetector",
    "HeatingEcoReaction",
    "HeatingPreferenceReaction",
    "IPatternDetector",
    "ILearningBackend",
    "LightingScheduleReaction",
    "NaiveLearningBackend",
    "PresencePatternReaction",
    "RoomSignalAssistReaction",
]
