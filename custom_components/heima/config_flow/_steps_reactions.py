"""Options flow: Reactions step (persisted mute management + proposal review)."""

# mypy: ignore-errors

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ..const import DOMAIN, OPT_REACTIONS
from ..runtime.analyzers import create_builtin_learning_plugin_registry
from ..runtime.analyzers.base import ReactionProposal
from ..runtime.analyzers.reaction_identity import composite_configured_reaction_slot_key
from ..runtime.reactions import (
    resolve_reaction_type,
)
from ._reaction_builders import _ReactionBuildersMixin
from ._reaction_forms import _ReactionFormHelpersMixin
from ._reaction_helpers import (
    safe_mapping as _safe_mapping,
)
from ._reaction_labels import _ReactionLabelsMixin
from ._steps_reaction_admin_authored import _ReactionAdminAuthoredStepsMixin
from ._steps_reaction_editing import _ReactionEditingStepsMixin
from ._steps_reaction_proposals import _ReactionProposalStepsMixin

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)
_REDACTED_SENTINEL = "**REDACTED**"


class _ReactionsStepsMixin(
    _ReactionAdminAuthoredStepsMixin,
    _ReactionBuildersMixin,
    _ReactionEditingStepsMixin,
    _ReactionFormHelpersMixin,
    _ReactionLabelsMixin,
    _ReactionProposalStepsMixin,
):
    """Mixin for reactions step."""

    @staticmethod
    def _reaction_type_from_cfg(cfg: dict[str, Any]) -> str:
        return resolve_reaction_type(cfg)

    @staticmethod
    def _has_redacted_payload(value: Any) -> bool:
        if isinstance(value, str):
            return _REDACTED_SENTINEL in value
        if isinstance(value, dict):
            return any(_ReactionsStepsMixin._has_redacted_payload(item) for item in value.values())
        if isinstance(value, list):
            return any(_ReactionsStepsMixin._has_redacted_payload(item) for item in value)
        return False

    def _admin_authored_identity_conflicts(self, proposal: ReactionProposal) -> bool:
        """Return True if a configured reaction already covers this identity key."""
        identity_key = str(proposal.identity_key or "").strip()
        if not identity_key:
            return False
        configured = dict(self._reactions_options().get("configured", {}))
        for raw in configured.values():
            reaction_cfg = _safe_mapping(raw)
            if str(reaction_cfg.get("source_proposal_identity_key") or "").strip() == identity_key:
                return True
        return False

    @staticmethod
    def _configured_reaction_slot_key(cfg: dict[str, Any]) -> str:
        """Return a coarse slot key used to avoid duplicate configured reactions."""
        reaction_type = resolve_reaction_type(cfg)
        return composite_configured_reaction_slot_key(reaction_type=reaction_type, cfg=cfg)

    def _configured_slot_matches_for_proposal(
        self,
        proposal: ReactionProposal,
        configured: dict[str, Any],
        *,
        exclude_ids: set[str] | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return configured reactions that occupy the same canonical slot."""
        exclude = exclude_ids or set()
        slot_key = self._configured_reaction_slot_key(
            _safe_mapping(proposal.suggested_reaction_config)
        )
        if not slot_key:
            return []

        matches: list[tuple[str, dict[str, Any]]] = []
        for reaction_id, raw in configured.items():
            if reaction_id in exclude:
                continue
            reaction_cfg = _safe_mapping(raw)
            if self._configured_reaction_slot_key(reaction_cfg) != slot_key:
                continue
            matches.append((str(reaction_id), reaction_cfg))
        matches.sort(key=lambda item: item[0])
        return matches

    def _resolve_configured_target_for_proposal(
        self,
        proposal: ReactionProposal,
        configured: dict[str, Any],
    ) -> tuple[ReactionProposal, str, dict[str, Any] | None, list[str]]:
        """Resolve the configured reaction target for a proposal accept/update."""
        accepted_proposal = proposal
        target_id = proposal.proposal_id
        existing_cfg: dict[str, Any] | None = None
        duplicate_ids: list[str] = []

        followup = self._proposal_followup_target(proposal)
        if followup is not None:
            target_id = str(followup["reaction_id"])
            existing_cfg = dict(followup["reaction_cfg"])
            if proposal.followup_kind == "discovery":
                accepted_proposal = replace(
                    proposal,
                    followup_kind="tuning_suggestion",
                    target_reaction_id=target_id,
                    target_reaction_type=self._reaction_type_from_cfg(existing_cfg),
                    target_reaction_origin=str(followup.get("target_reaction_origin") or ""),
                    target_template_id=str(followup.get("target_template_id") or ""),
                )
            return accepted_proposal, target_id, existing_cfg, duplicate_ids

        slot_matches = self._configured_slot_matches_for_proposal(
            proposal,
            configured,
            exclude_ids={proposal.proposal_id},
        )
        if not slot_matches:
            return accepted_proposal, target_id, existing_cfg, duplicate_ids

        target_id, existing_cfg = slot_matches[0]
        duplicate_ids = [reaction_id for reaction_id, _cfg in slot_matches[1:]]
        accepted_proposal = replace(
            proposal,
            followup_kind="tuning_suggestion",
            target_reaction_id=target_id,
            target_reaction_type=self._reaction_type_from_cfg(existing_cfg),
            target_reaction_origin=str(existing_cfg.get("origin") or ""),
            target_template_id=str(existing_cfg.get("source_template_id") or ""),
        )
        return accepted_proposal, target_id, existing_cfg, duplicate_ids

    def _store_reactions_options(self, updates: dict[str, Any]) -> None:
        """Persist reaction options without dropping sibling reaction state."""
        reactions_cfg = dict(self._reactions_options())
        reactions_cfg.update(updates)
        self._update_options({OPT_REACTIONS: reactions_cfg})

    # ---- Helpers ----

    def _reactions_options(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_REACTIONS, {}))

    def _configured_reaction_from_proposal(
        self,
        proposal: ReactionProposal,
        *,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        configured = dict(_safe_mapping(existing_config))
        configured.update(cfg)
        configured.pop("reaction_class", None)

        is_followup = proposal.followup_kind == "tuning_suggestion" and bool(
            _safe_mapping(existing_config)
        )
        if is_followup:
            if proposal.updated_at:
                configured["last_tuned_at"] = proposal.updated_at
            configured["last_tuning_proposal_id"] = proposal.proposal_id
            configured["last_tuning_origin"] = proposal.origin
            configured["last_tuning_followup_kind"] = proposal.followup_kind
            return configured

        is_improvement = proposal.followup_kind == "improvement" and bool(
            _safe_mapping(existing_config)
        )
        if is_improvement:
            previous = _safe_mapping(existing_config)
            registry = self._learning_plugin_registry()
            if registry is not None:
                return registry.build_improvement_config(
                    proposal,
                    existing_config=previous,
                )

        origin = proposal.origin
        configured["reaction_type"] = str(proposal.reaction_type or "").strip()
        configured["origin"] = origin
        configured["author_kind"] = "admin" if origin == "admin_authored" else "heima"
        configured["source_proposal_id"] = proposal.proposal_id
        if proposal.identity_key:
            configured["source_proposal_identity_key"] = proposal.identity_key
        if proposal.created_at:
            configured["created_at"] = proposal.created_at
        template_id = str(cfg.get("admin_authored_template_id") or "").strip()
        if template_id:
            configured["source_template_id"] = template_id
            configured["source_request"] = f"template:{template_id}"
            configured.setdefault("last_tuned_at", None)
        else:
            configured["source_request"] = "learned_pattern"
        return configured

    def _admin_authored_template_options(self) -> dict[str, str]:
        registry = self._learning_plugin_registry()
        if registry is None:
            return {}
        options: dict[str, str] = {}
        for template in registry.admin_authored_templates(implemented_only=True):
            available, _reason = self._admin_authored_template_availability(template.template_id)
            title = template.title
            if not available:
                title = f"{title} ({'non disponibile' if self._flow_language().startswith('it') else 'unavailable'})"
            options[template.template_id] = title
        return options

    def _admin_authored_template(self, template_id: str) -> Any | None:
        registry = self._learning_plugin_registry()
        if registry is None:
            return None
        return registry.get_admin_authored_template(
            template_id,
            implemented_only=True,
        )

    def _admin_authored_template_availability(self, template_id: str) -> tuple[bool, str]:
        template_id = str(template_id or "").strip()
        if not template_id:
            return False, ""
        if template_id == "security.vacation_presence_simulation.basic":
            configured = self._reactions_options().get("configured", {})
            has_lighting = any(
                resolve_reaction_type(cfg) == "context_conditioned_lighting_scene"
                for cfg in configured.values()
                if isinstance(cfg, dict)
            )
            if not has_lighting:
                is_it = self._flow_language().startswith("it")
                reason = (
                    "Servono routine luci già accettate per costruire un profilo credibile."
                    if is_it
                    else "Accepted lighting routines are required to build a credible presence profile."
                )
                return False, reason
        return True, ""

    def _admin_authored_template_availability_notes(self) -> str:
        registry = self._learning_plugin_registry()
        if registry is None:
            return ""
        lines: list[str] = []
        for template in registry.admin_authored_templates(implemented_only=True):
            available, reason = self._admin_authored_template_availability(template.template_id)
            if not available and reason:
                lines.append(f"- {template.title}: {reason}")
        return "\n".join(lines)

    def _learning_plugin_registry(self) -> Any | None:
        coordinator = self._get_coordinator()
        registry = getattr(coordinator, "learning_plugin_registry", None) if coordinator else None
        if registry is not None:
            return registry
        learning_cfg = dict(self.options.get("learning", {}))
        enabled_families = {
            str(item).strip()
            for item in learning_cfg.get("enabled_plugin_families") or []
            if str(item).strip()
        }
        return create_builtin_learning_plugin_registry(enabled_families=enabled_families or None)

    def _proposals_step_summary(
        self,
        proposals: list[ReactionProposal],
        *,
        current: ReactionProposal | None = None,
        remaining: int | None = None,
    ) -> str:
        language = self._flow_language()
        is_it = language.startswith("it")
        pending = [proposal for proposal in proposals if proposal.status == "pending"]
        if not pending:
            return "—"
        total = len(pending)
        if current is None:
            if is_it:
                return "1 proposta pendente" if total == 1 else f"{total} proposte pendenti"
            return f"{total} pending proposal{'s' if total != 1 else ''}"
        return ""

    def _flow_language(self) -> str:
        return str(getattr(getattr(self.hass, "config", None), "language", "en") or "en").lower()

    def _get_coordinator(self) -> Any | None:
        """Return the running coordinator for this entry, or None."""
        try:
            entry_id = self._config_entry.entry_id
            coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id, {}).get("coordinator")
            return coordinator
        except Exception:
            _LOGGER.debug("Could not retrieve coordinator", exc_info=True)
            return None
