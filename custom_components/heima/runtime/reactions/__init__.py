"""Built-in reaction registry."""

# mypy: disable-error-code=misc

from dataclasses import dataclass
from typing import Any, Callable

from ._compat import (
    LEGACY_REACTION_CLASS_TO_TYPE,
    normalize_reaction_options_payload,
    resolve_reaction_type,
)
from .base import HeimaReaction
from .builtin import ConsecutiveStateReaction
from .context_conditioned_lighting import (
    ContextConditionedLightingReaction,
    build_context_conditioned_lighting_reaction,
    present_context_conditioned_lighting_label,
    present_context_conditioned_lighting_proposal_label,
    present_context_conditioned_lighting_review_title,
    present_learned_context_conditioned_lighting_details,
    present_tuning_context_conditioned_lighting_details,
)
from .contextual_lighting_assist import (
    RoomContextualLightingAssistReaction,
    build_room_contextual_lighting_assist_reaction,
    present_admin_authored_room_contextual_lighting_assist_details,
    present_learned_room_contextual_lighting_assist_details,
    present_room_contextual_lighting_assist_label,
    present_room_contextual_lighting_assist_proposal_label,
    present_room_contextual_lighting_assist_review_title,
    present_tuning_room_contextual_lighting_assist_details,
    validate_contextual_lighting_contract,
)
from .heating import (
    HeatingEcoReaction,
    HeatingPreferenceReaction,
    build_heating_eco_reaction,
    build_heating_preference_reaction,
)
from .learning import ILearningBackend, NaiveLearningBackend
from .lighting_assist import (
    RoomLightingAssistReaction,
    build_room_lighting_assist_reaction,
    present_admin_authored_room_lighting_assist_details,
    present_learned_room_lighting_assist_details,
    present_room_lighting_assist_label,
    present_room_lighting_assist_proposal_label,
    present_room_lighting_assist_review_title,
    present_tuning_room_lighting_assist_details,
)
from .lighting_schedule import (
    LightingScheduleReaction,
    build_lighting_schedule_reaction,
    present_admin_authored_lighting_schedule_details,
    present_learned_lighting_schedule_details,
    present_lighting_schedule_label,
    present_lighting_schedule_proposal_label,
    present_lighting_schedule_review_title,
    present_tuning_lighting_schedule_details,
)
from .lighting_vacancy_off import (
    RoomLightingVacancyOffReaction,
    build_room_lighting_vacancy_off_reaction,
    present_admin_authored_room_lighting_vacancy_off_details,
    present_learned_room_lighting_vacancy_off_details,
    present_room_lighting_vacancy_off_label,
    present_room_lighting_vacancy_off_proposal_label,
    present_room_lighting_vacancy_off_review_title,
    present_tuning_room_lighting_vacancy_off_details,
)
from .patterns import ConsecutiveMatchDetector, IPatternDetector
from .presence import (
    PresencePatternReaction,
    build_presence_pattern_reaction,
    present_presence_pattern_label,
)
from .security_presence_simulation import (
    VacationPresenceSimulationReaction,
    build_vacation_presence_simulation_reaction,
    present_admin_authored_vacation_presence_simulation_details,
    present_learned_vacation_presence_simulation_details,
    present_vacation_presence_simulation_label,
    present_vacation_presence_simulation_proposal_label,
    present_vacation_presence_simulation_review_title,
)
from .signal_assist import (
    RoomSignalAssistReaction,
    build_room_cooling_assist_reaction,
    build_room_signal_assist_reaction,
    normalize_room_signal_assist_config,
    present_admin_authored_room_signal_assist_details,
    present_learned_room_signal_assist_details,
    present_room_signal_assist_label,
    present_room_signal_assist_proposal_label,
    present_room_signal_assist_review_title,
    present_tuning_room_signal_assist_details,
)

ReactionPluginBuilder = Callable[[Any, str, dict[str, Any]], HeimaReaction | None]
ReactionLabelPresenter = Callable[[str, dict[str, Any], dict[str, str]], str | None]
AdminAuthoredReviewDetailsPresenter = Callable[[Any, Any, dict[str, Any], str], list[str]]
LearnedReviewDetailsPresenter = Callable[[Any, Any, dict[str, Any], str], list[str]]
TuningReviewDetailsPresenter = Callable[[Any, Any, dict[str, Any], dict[str, Any], str], list[str]]
ProposalHumanLabelPresenter = Callable[[Any, Any, dict[str, Any], str], str | None]
ProposalReviewTitlePresenter = Callable[[Any, Any, dict[str, Any], str, bool], str | None]


@dataclass(frozen=True)
class ReactionPluginDescriptor:
    """Minimal built-in metadata for one Reaction Plugin."""

    reaction_type: str
    reaction_id_strategy: str
    supported_config_contracts: tuple[str, ...]
    supports_normalizer: bool


@dataclass(frozen=True)
class ReactionPresenterHooks:
    """Optional presentation hooks for one reaction plugin."""

    reaction_label_from_config: ReactionLabelPresenter | None = None
    proposal_human_label: ProposalHumanLabelPresenter | None = None
    proposal_review_title: ProposalReviewTitlePresenter | None = None
    admin_authored_review_details: AdminAuthoredReviewDetailsPresenter | None = None
    learned_review_details: LearnedReviewDetailsPresenter | None = None
    tuning_review_details: TuningReviewDetailsPresenter | None = None


@dataclass(frozen=True)
class RegisteredReactionPlugin:
    """Built-in reaction plugin metadata plus runtime hooks."""

    descriptor: ReactionPluginDescriptor
    builder: ReactionPluginBuilder
    presenter_hooks: ReactionPresenterHooks | None = None


class ReactionPluginRegistry:
    """Registry for reaction plugins used by diagnostics and runtime rebuild."""

    def __init__(self, plugins: tuple[RegisteredReactionPlugin, ...]) -> None:
        self._plugins = plugins
        self._plugins_by_type = {plugin.descriptor.reaction_type: plugin for plugin in plugins}

    def plugin_for(self, reaction_type: str) -> RegisteredReactionPlugin | None:
        return self._plugins_by_type.get(str(reaction_type or ""))

    def builder_for(self, reaction_type: str) -> ReactionPluginBuilder | None:
        plugin = self.plugin_for(reaction_type)
        return plugin.builder if plugin is not None else None

    def descriptors(self) -> tuple[ReactionPluginDescriptor, ...]:
        return tuple(plugin.descriptor for plugin in self._plugins)

    def presenter_for(self, reaction_type: str) -> ReactionPresenterHooks | None:
        plugin = self.plugin_for(reaction_type)
        return plugin.presenter_hooks if plugin is not None else None

    def diagnostics(self) -> list[dict[str, Any]]:
        return [
            {
                "reaction_type": plugin.descriptor.reaction_type,
                "reaction_id_strategy": plugin.descriptor.reaction_id_strategy,
                "supported_config_contracts": list(plugin.descriptor.supported_config_contracts),
                "supports_normalizer": plugin.descriptor.supports_normalizer,
                "supports_presenter": plugin.presenter_hooks is not None,
            }
            for plugin in self._plugins
        ]


def create_builtin_reaction_plugin_registry() -> ReactionPluginRegistry:
    """Return the built-in reaction plugin registry."""
    plugins = (
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="presence_preheat",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("presence_preheat",),
                supports_normalizer=False,
            ),
            builder=build_presence_pattern_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_presence_pattern_label,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="context_conditioned_lighting_scene",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("context_conditioned_lighting_scene",),
                supports_normalizer=False,
            ),
            builder=build_context_conditioned_lighting_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_context_conditioned_lighting_label,
                proposal_human_label=present_context_conditioned_lighting_proposal_label,
                proposal_review_title=present_context_conditioned_lighting_review_title,
                learned_review_details=present_learned_context_conditioned_lighting_details,
                tuning_review_details=present_tuning_context_conditioned_lighting_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="lighting_scene_schedule",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("lighting_scene_schedule",),
                supports_normalizer=False,
            ),
            builder=build_lighting_schedule_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_lighting_schedule_label,
                proposal_human_label=present_lighting_schedule_proposal_label,
                proposal_review_title=present_lighting_schedule_review_title,
                admin_authored_review_details=present_admin_authored_lighting_schedule_details,
                learned_review_details=present_learned_lighting_schedule_details,
                tuning_review_details=present_tuning_lighting_schedule_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="heating_preference",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("heating_preference",),
                supports_normalizer=False,
            ),
            builder=build_heating_preference_reaction,
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="heating_eco",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("heating_eco",),
                supports_normalizer=False,
            ),
            builder=build_heating_eco_reaction,
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="room_signal_assist",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("room_signal_assist",),
                supports_normalizer=True,
            ),
            builder=build_room_signal_assist_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_room_signal_assist_label,
                proposal_human_label=present_room_signal_assist_proposal_label,
                proposal_review_title=present_room_signal_assist_review_title,
                admin_authored_review_details=present_admin_authored_room_signal_assist_details,
                learned_review_details=present_learned_room_signal_assist_details,
                tuning_review_details=present_tuning_room_signal_assist_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="room_cooling_assist",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("room_cooling_assist",),
                supports_normalizer=True,
            ),
            builder=build_room_cooling_assist_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_room_signal_assist_label,
                proposal_human_label=present_room_signal_assist_proposal_label,
                proposal_review_title=present_room_signal_assist_review_title,
                admin_authored_review_details=present_admin_authored_room_signal_assist_details,
                learned_review_details=present_learned_room_signal_assist_details,
                tuning_review_details=present_tuning_room_signal_assist_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="room_air_quality_assist",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("room_air_quality_assist",),
                supports_normalizer=True,
            ),
            builder=build_room_signal_assist_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_room_signal_assist_label,
                proposal_human_label=present_room_signal_assist_proposal_label,
                proposal_review_title=present_room_signal_assist_review_title,
                admin_authored_review_details=present_admin_authored_room_signal_assist_details,
                learned_review_details=present_learned_room_signal_assist_details,
                tuning_review_details=present_tuning_room_signal_assist_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="room_contextual_lighting_assist",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("room_contextual_lighting_assist",),
                supports_normalizer=False,
            ),
            builder=build_room_contextual_lighting_assist_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_room_contextual_lighting_assist_label,
                proposal_human_label=present_room_contextual_lighting_assist_proposal_label,
                proposal_review_title=present_room_contextual_lighting_assist_review_title,
                admin_authored_review_details=present_admin_authored_room_contextual_lighting_assist_details,
                learned_review_details=present_learned_room_contextual_lighting_assist_details,
                tuning_review_details=present_tuning_room_contextual_lighting_assist_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="room_darkness_lighting_assist",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("room_darkness_lighting_assist",),
                supports_normalizer=False,
            ),
            builder=build_room_lighting_assist_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_room_lighting_assist_label,
                proposal_human_label=present_room_lighting_assist_proposal_label,
                proposal_review_title=present_room_lighting_assist_review_title,
                admin_authored_review_details=present_admin_authored_room_lighting_assist_details,
                learned_review_details=present_learned_room_lighting_assist_details,
                tuning_review_details=present_tuning_room_lighting_assist_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="room_vacancy_lighting_off",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("room_vacancy_lighting_off",),
                supports_normalizer=False,
            ),
            builder=build_room_lighting_vacancy_off_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_room_lighting_vacancy_off_label,
                proposal_human_label=present_room_lighting_vacancy_off_proposal_label,
                proposal_review_title=present_room_lighting_vacancy_off_review_title,
                admin_authored_review_details=present_admin_authored_room_lighting_vacancy_off_details,
                learned_review_details=present_learned_room_lighting_vacancy_off_details,
                tuning_review_details=present_tuning_room_lighting_vacancy_off_details,
            ),
        ),
        RegisteredReactionPlugin(
            descriptor=ReactionPluginDescriptor(
                reaction_type="vacation_presence_simulation",
                reaction_id_strategy="proposal_id",
                supported_config_contracts=("vacation_presence_simulation",),
                supports_normalizer=False,
            ),
            builder=build_vacation_presence_simulation_reaction,
            presenter_hooks=ReactionPresenterHooks(
                reaction_label_from_config=present_vacation_presence_simulation_label,
                proposal_human_label=present_vacation_presence_simulation_proposal_label,
                proposal_review_title=present_vacation_presence_simulation_review_title,
                admin_authored_review_details=present_admin_authored_vacation_presence_simulation_details,
                learned_review_details=present_learned_vacation_presence_simulation_details,
            ),
        ),
    )
    return ReactionPluginRegistry(plugins)


def builtin_reaction_plugin_builders() -> dict[str, ReactionPluginBuilder]:
    """Legacy helper: return built-in builders keyed by reaction_type."""
    registry = create_builtin_reaction_plugin_registry()
    return {
        descriptor.reaction_type: registry.builder_for(descriptor.reaction_type)
        for descriptor in registry.descriptors()
        if registry.builder_for(descriptor.reaction_type) is not None
    }


def builtin_reaction_plugin_descriptors() -> tuple[ReactionPluginDescriptor, ...]:
    """Legacy helper: return minimal metadata for built-in Reaction Plugins."""
    return create_builtin_reaction_plugin_registry().descriptors()


__all__ = [
    "HeimaReaction",
    "ReactionPluginRegistry",
    "ReactionPluginDescriptor",
    "ReactionPluginBuilder",
    "ReactionLabelPresenter",
    "AdminAuthoredReviewDetailsPresenter",
    "LearnedReviewDetailsPresenter",
    "TuningReviewDetailsPresenter",
    "ProposalHumanLabelPresenter",
    "ProposalReviewTitlePresenter",
    "ReactionPresenterHooks",
    "RegisteredReactionPlugin",
    "create_builtin_reaction_plugin_registry",
    "builtin_reaction_plugin_builders",
    "builtin_reaction_plugin_descriptors",
    "resolve_reaction_type",
    "LEGACY_REACTION_CLASS_TO_TYPE",
    "ConsecutiveStateReaction",
    "ConsecutiveMatchDetector",
    "HeatingEcoReaction",
    "HeatingPreferenceReaction",
    "IPatternDetector",
    "ILearningBackend",
    "RoomContextualLightingAssistReaction",
    "RoomLightingAssistReaction",
    "LightingScheduleReaction",
    "NaiveLearningBackend",
    "PresencePatternReaction",
    "RoomSignalAssistReaction",
    "VacationPresenceSimulationReaction",
    "validate_contextual_lighting_contract",
]
