"""Registry for built-in learning pattern plugins."""

# mypy: disable-error-code=dict-item

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .base import IPatternAnalyzer, ReactionProposal
from .cross_domain import (
    DEFAULT_COMPOSITE_PATTERN_CATALOG,
    CompositePatternCatalogAnalyzer,
    composite_quality_policy_from_learning_config,
)
from .heating import HeatingPatternAnalyzer
from .lifecycle import (
    ProposalLifecycleHooks,
    composite_lifecycle_policy_from_learning_config,
    composite_room_assist_lifecycle_hooks,
    heating_lifecycle_hooks,
    lighting_lifecycle_hooks,
    presence_lifecycle_hooks,
    security_presence_simulation_lifecycle_hooks,
)
from .lighting import LightingPatternAnalyzer
from .policy import composite_catalog_with_policy, learning_policy_from_config
from .presence import PresencePatternAnalyzer
from .security_presence_simulation import SecurityPresenceSimulationAnalyzer


@dataclass(frozen=True)
class AdminAuthoredTemplateDescriptor:
    """A bounded admin-authored proposal template exposed by a plugin."""

    template_id: str
    reaction_type: str
    title: str
    description: str
    config_schema_id: str
    implemented: bool = False
    flow_step_id: str = ""


@dataclass(frozen=True)
class ImprovementProposalDescriptor:
    """Metadata for one supported improvement proposal family."""

    source_reaction_type: str
    target_reaction_type: str
    improvement_reason: str
    acceptance_strategy: str = "convert_replace"
    review_reason_en: str = ""
    review_reason_it: str = ""
    conversion_builder: (
        Callable[
            ["ImprovementProposalDescriptor", ReactionProposal, dict[str, Any]], dict[str, Any]
        ]
        | None
    ) = None


@dataclass(frozen=True)
class LearningPatternPluginDescriptor:
    """Minimal built-in metadata for one Learning Pattern Plugin."""

    plugin_id: str
    analyzer_id: str
    plugin_family: str
    proposal_types: tuple[str, ...]
    reaction_targets: tuple[str, ...]
    lifecycle_hooks: ProposalLifecycleHooks | None = None
    supports_admin_authored: bool = False
    admin_authored_templates: tuple[AdminAuthoredTemplateDescriptor, ...] = ()
    improvement_proposals: tuple[ImprovementProposalDescriptor, ...] = ()


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
        return tuple(item.analyzer for item in self._plugins if item.enabled or not enabled_only)

    def descriptors(
        self, *, enabled_only: bool = False
    ) -> tuple[LearningPatternPluginDescriptor, ...]:
        return tuple(item.descriptor for item in self._plugins if item.enabled or not enabled_only)

    def admin_authored_descriptors(
        self, *, enabled_only: bool = True
    ) -> tuple[LearningPatternPluginDescriptor, ...]:
        return tuple(
            item.descriptor
            for item in self._plugins
            if item.descriptor.supports_admin_authored and (item.enabled or not enabled_only)
        )

    def admin_authored_templates(
        self, *, enabled_only: bool = True, implemented_only: bool = False
    ) -> tuple[AdminAuthoredTemplateDescriptor, ...]:
        templates: list[AdminAuthoredTemplateDescriptor] = []
        for item in self._plugins:
            if not item.descriptor.supports_admin_authored:
                continue
            if enabled_only and not item.enabled:
                continue
            for template in item.descriptor.admin_authored_templates:
                if implemented_only and not template.implemented:
                    continue
                templates.append(template)
        return tuple(templates)

    def get_admin_authored_template(
        self,
        template_id: str,
        *,
        enabled_only: bool = True,
        implemented_only: bool = False,
    ) -> AdminAuthoredTemplateDescriptor | None:
        target = template_id.strip()
        if not target:
            return None
        for template in self.admin_authored_templates(
            enabled_only=enabled_only,
            implemented_only=implemented_only,
        ):
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
                "has_lifecycle_hooks": item.descriptor.lifecycle_hooks is not None,
                "supports_admin_authored": item.descriptor.supports_admin_authored,
                "admin_authored_templates": list(
                    _template_diagnostics(item.descriptor.admin_authored_templates)
                ),
                "improvement_proposals": list(
                    _improvement_diagnostics(item.descriptor.improvement_proposals)
                ),
                "enabled": item.enabled,
            }
            for item in self._plugins
        ]

    def lifecycle_hooks_for(
        self,
        reaction_type: str,
        *,
        enabled_only: bool = False,
    ) -> ProposalLifecycleHooks | None:
        target = reaction_type.strip()
        if not target:
            return None
        for item in self._plugins:
            if enabled_only and not item.enabled:
                continue
            if target in item.descriptor.proposal_types:
                return item.descriptor.lifecycle_hooks
        return None

    def improvement_descriptor_for(
        self,
        *,
        target_reaction_type: str,
        source_reaction_type: str,
        improvement_reason: str = "",
        enabled_only: bool = False,
    ) -> ImprovementProposalDescriptor | None:
        target = str(target_reaction_type or "").strip()
        source = str(source_reaction_type or "").strip()
        reason = str(improvement_reason or "").strip()
        if not target or not source:
            return None
        for item in self._plugins:
            if enabled_only and not item.enabled:
                continue
            for descriptor in item.descriptor.improvement_proposals:
                if descriptor.target_reaction_type != target:
                    continue
                if descriptor.source_reaction_type != source:
                    continue
                if reason and descriptor.improvement_reason != reason:
                    continue
                return descriptor
        return None

    def improvement_descriptors(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[ImprovementProposalDescriptor, ...]:
        items: list[ImprovementProposalDescriptor] = []
        for plugin in self._plugins:
            if enabled_only and not plugin.enabled:
                continue
            items.extend(plugin.descriptor.improvement_proposals)
        return tuple(items)

    def build_improvement_config(
        self,
        proposal: ReactionProposal,
        *,
        existing_config: dict[str, Any],
    ) -> dict[str, Any]:
        descriptor = self.improvement_descriptor_for(
            target_reaction_type=str(proposal.reaction_type or "").strip(),
            source_reaction_type=str(
                proposal.improves_reaction_type or proposal.target_reaction_type or ""
            ).strip(),
            improvement_reason=str(proposal.improvement_reason or "").strip(),
            enabled_only=False,
        )
        return _build_improvement_config(
            descriptor=descriptor,
            proposal=proposal,
            existing_config=existing_config,
        )

    def __len__(self) -> int:
        return len(self._plugins)

    def __iter__(self) -> Iterable[RegisteredLearningPlugin]:
        return iter(self._plugins)


def create_builtin_learning_plugin_registry(
    *,
    enabled_families: set[str] | None = None,
    learning_config: dict[str, object] | None = None,
) -> LearningPluginRegistry:
    """Create the built-in learning plugin registry used by Heima v1."""
    registry = LearningPluginRegistry()
    policies = learning_policy_from_config(learning_config)
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.presence_preheat",
            analyzer_id="PresencePatternAnalyzer",
            plugin_family="presence",
            proposal_types=("presence_preheat",),
            reaction_targets=("PresencePatternReaction",),
            lifecycle_hooks=presence_lifecycle_hooks(),
            supports_admin_authored=False,
            admin_authored_templates=(),
        ),
        analyzer=PresencePatternAnalyzer(policy=policies.presence),
        enabled=_is_enabled("presence", enabled_families),
    )
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.heating_preferences",
            analyzer_id="HeatingPatternAnalyzer",
            plugin_family="heating",
            proposal_types=("heating_preference", "heating_eco"),
            reaction_targets=("HeatingPreferenceReaction", "HeatingEcoReaction"),
            lifecycle_hooks=heating_lifecycle_hooks(),
            supports_admin_authored=False,
            admin_authored_templates=(),
        ),
        analyzer=HeatingPatternAnalyzer(policy=policies.heating),
        enabled=_is_enabled("heating", enabled_families),
    )
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.lighting_routines",
            analyzer_id="LightingPatternAnalyzer",
            plugin_family="lighting",
            proposal_types=("context_conditioned_lighting_scene",),
            reaction_targets=("ContextConditionedLightingReaction",),
            lifecycle_hooks=lighting_lifecycle_hooks(),
            supports_admin_authored=False,
            admin_authored_templates=(),
        ),
        analyzer=LightingPatternAnalyzer(policy=policies.lighting),
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
                "room_contextual_lighting_assist",
                "room_vacancy_lighting_off",
            ),
            reaction_targets=(
                "RoomSignalAssistReaction",
                "RoomLightingAssistReaction",
                "RoomContextualLightingAssistReaction",
                "RoomLightingVacancyOffReaction",
            ),
            lifecycle_hooks=composite_room_assist_lifecycle_hooks(
                policy=composite_lifecycle_policy_from_learning_config(learning_config)
            ),
            supports_admin_authored=True,
            admin_authored_templates=(
                AdminAuthoredTemplateDescriptor(
                    template_id="room.signal_assist.basic",
                    reaction_type="room_signal_assist",
                    title="Room Signal Assist",
                    description="Create a room assist automation driven by a primary room signal.",
                    config_schema_id="room_signal_assist.basic.v1",
                    implemented=True,
                    flow_step_id="admin_authored_room_signal_assist",
                ),
                AdminAuthoredTemplateDescriptor(
                    template_id="room.darkness_lighting_assist.basic",
                    reaction_type="room_darkness_lighting_assist",
                    title="Darkness Lighting Assist",
                    description="Create a room lighting assist that reacts to darkness conditions.",
                    config_schema_id="room_darkness_lighting_assist.basic.v1",
                    implemented=True,
                    flow_step_id="admin_authored_room_darkness_lighting_assist",
                ),
                AdminAuthoredTemplateDescriptor(
                    template_id="room.contextual_lighting_assist.basic",
                    reaction_type="room_contextual_lighting_assist",
                    title="Contextual Room Lighting",
                    description="Create a room lighting assist that selects profiles by time and context.",
                    config_schema_id="room_contextual_lighting_assist.basic.v1",
                    implemented=True,
                    flow_step_id="admin_authored_room_contextual_lighting_assist",
                ),
                AdminAuthoredTemplateDescriptor(
                    template_id="room.vacancy_lighting_off.basic",
                    reaction_type="room_vacancy_lighting_off",
                    title="Vacancy Lights Off",
                    description="Create a room lighting assist that turns lights off after vacancy persists.",
                    config_schema_id="room_vacancy_lighting_off.basic.v1",
                    implemented=True,
                    flow_step_id="admin_authored_room_vacancy_lighting_off",
                ),
            ),
            improvement_proposals=(
                ImprovementProposalDescriptor(
                    source_reaction_type="room_darkness_lighting_assist",
                    target_reaction_type="room_contextual_lighting_assist",
                    improvement_reason="contextual_variation",
                    acceptance_strategy="convert_replace",
                    review_reason_en=(
                        "Reason: darkness-triggered lighting varies consistently by time "
                        "window or context."
                    ),
                    review_reason_it=(
                        "Motivo: l'uso delle luci al buio varia in modo stabile per fascia "
                        "oraria o contesto."
                    ),
                ),
                ImprovementProposalDescriptor(
                    source_reaction_type="room_signal_assist",
                    target_reaction_type="room_cooling_assist",
                    improvement_reason="cooling_specialization",
                    acceptance_strategy="convert_replace",
                    review_reason_en=(
                        "Reason: the learned signal-followup pattern is consistently cooling-"
                        "specific and is better represented as a cooling assist."
                    ),
                    review_reason_it=(
                        "Motivo: il pattern segnale-followup osservato e' stabilmente specifico "
                        "del raffrescamento ed e' espresso meglio come cooling assist."
                    ),
                ),
            ),
        ),
        analyzer=CompositePatternCatalogAnalyzer(
            catalog=composite_catalog_with_policy(
                DEFAULT_COMPOSITE_PATTERN_CATALOG,
                policies.composite_room_assist,
            ),
            quality_policy=composite_quality_policy_from_learning_config(learning_config),
        ),
        enabled=_is_enabled("composite_room_assist", enabled_families),
    )
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="builtin.security_presence_simulation",
            analyzer_id="SecurityPresenceSimulationAnalyzer",
            plugin_family="security_presence_simulation",
            proposal_types=("vacation_presence_simulation",),
            reaction_targets=("VacationPresenceSimulationReaction",),
            lifecycle_hooks=security_presence_simulation_lifecycle_hooks(),
            supports_admin_authored=True,
            admin_authored_templates=(
                AdminAuthoredTemplateDescriptor(
                    template_id="security.vacation_presence_simulation.basic",
                    reaction_type="vacation_presence_simulation",
                    title="Vacation Presence Simulation",
                    description="Create a security-owned vacation presence simulation driven by learned lighting behavior.",
                    config_schema_id="vacation_presence_simulation.basic.v1",
                    implemented=True,
                    flow_step_id="admin_authored_security_presence_simulation",
                ),
            ),
        ),
        analyzer=SecurityPresenceSimulationAnalyzer(policy=policies.security_presence_simulation),
        enabled=_is_enabled("security_presence_simulation", enabled_families),
    )
    return registry


def _is_enabled(plugin_family: str, enabled_families: set[str] | None) -> bool:
    if enabled_families is None:
        return True
    return plugin_family in enabled_families


def _template_diagnostics(
    templates: tuple[AdminAuthoredTemplateDescriptor, ...],
) -> list[dict[str, str]]:
    return [
        {
            "template_id": item.template_id,
            "reaction_type": item.reaction_type,
            "title": item.title,
            "description": item.description,
            "config_schema_id": item.config_schema_id,
            "implemented": item.implemented,
            "flow_step_id": item.flow_step_id,
        }
        for item in templates
    ]


def _improvement_diagnostics(
    improvements: tuple[ImprovementProposalDescriptor, ...],
) -> list[dict[str, str]]:
    return [
        {
            "source_reaction_type": item.source_reaction_type,
            "target_reaction_type": item.target_reaction_type,
            "improvement_reason": item.improvement_reason,
            "acceptance_strategy": item.acceptance_strategy,
            "review_reason_en": item.review_reason_en,
            "review_reason_it": item.review_reason_it,
        }
        for item in improvements
    ]


def _build_improvement_config(
    *,
    descriptor: ImprovementProposalDescriptor | None,
    proposal: ReactionProposal,
    existing_config: dict[str, Any],
) -> dict[str, Any]:
    previous = _safe_dict(existing_config)
    if descriptor is not None and descriptor.conversion_builder is not None:
        return descriptor.conversion_builder(descriptor, proposal, previous)
    return _default_improvement_conversion_builder(descriptor, proposal, previous)


def _default_improvement_conversion_builder(
    descriptor: ImprovementProposalDescriptor | None,
    proposal: ReactionProposal,
    existing_config: dict[str, Any],
) -> dict[str, Any]:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    converted = dict(cfg)
    converted.pop("reaction_class", None)
    converted["reaction_type"] = str(proposal.reaction_type or "").strip()
    converted["origin"] = proposal.origin
    converted["author_kind"] = "admin" if proposal.origin == "admin_authored" else "heima"
    converted["source_proposal_id"] = proposal.proposal_id
    if proposal.identity_key:
        converted["source_proposal_identity_key"] = proposal.identity_key
    converted["source_request"] = "learned_pattern"
    converted["created_at"] = str(
        existing_config.get("created_at") or proposal.created_at or ""
    ).strip()
    converted["last_improved_at"] = str(proposal.updated_at or proposal.created_at or "").strip()
    converted["improved_from_reaction_type"] = str(
        existing_config.get("reaction_type") or proposal.improves_reaction_type or ""
    ).strip()
    converted["improvement_reason"] = str(proposal.improvement_reason or "").strip()
    converted["improvement_acceptance_strategy"] = str(
        (descriptor.acceptance_strategy if descriptor is not None else "convert_replace")
        or "convert_replace"
    )
    if "enabled" in existing_config:
        converted["enabled"] = existing_config.get("enabled")
    return converted


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
