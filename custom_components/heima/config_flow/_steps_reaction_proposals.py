"""Options flow: reaction proposal review steps."""

# mypy: ignore-errors

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from ..const import OPT_REACTIONS, SIGNAL_DISCOVERY_REACTION_TYPE
from ..runtime.analyzers.base import ReactionProposal
from ..runtime.analyzers.registry import ImprovementProposalDescriptor
from ..runtime.inference.approval_store import ACTIVITY_PROPOSAL_TYPE, HOUSE_STATE_PROPOSAL_TYPE
from ..runtime.proposal_engine import ActivityProposal
from ..runtime.reactions import create_builtin_reaction_plugin_registry, resolve_reaction_type
from ._common import _entity_selector, _number_box_selector
from ._reaction_helpers import (
    activity_proposal_review_details as _activity_proposal_review_details,
)
from ._reaction_helpers import (
    format_last_seen as _format_last_seen,
)
from ._reaction_helpers import (
    house_state_proposal_review_details as _house_state_proposal_review_details,
)
from ._reaction_helpers import (
    proposal_review_type as _proposal_review_type,
)
from ._reaction_helpers import (
    safe_mapping as _safe_mapping,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _ReactionProposalStepsMixin:
    """Mixin for proposal review and accepted-proposal action completion."""

    # ---- Proposals step (P5) ----

    async def async_step_proposals(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Review pending learning proposals one at a time. Skip silently if none are pending."""
        coordinator = self._get_coordinator()
        pending = coordinator.proposal_engine.pending_proposals() if coordinator else []

        if not pending:
            self._proposal_review_queue = []
            return await self.async_step_init()

        pending_map = {proposal.proposal_id: proposal for proposal in pending}
        queue = list(getattr(self, "_proposal_review_queue", []))
        if not queue:
            queue = [proposal.proposal_id for proposal in pending]

        queue = [proposal_id for proposal_id in queue if proposal_id in pending_map]
        if not queue:
            self._proposal_review_queue = []
            return await self.async_step_init()

        current_id = queue[0]
        current = pending_map[current_id]

        if user_input is None:
            self._proposal_review_queue = queue
            schema = vol.Schema(
                {
                    vol.Required(
                        "review_action",
                        default="accept",
                    ): vol.In(self._proposal_review_action_options()),
                }
            )
            return self.async_show_form(
                step_id="proposals",
                data_schema=schema,
                description_placeholders=self._proposal_review_placeholders(
                    pending, current, len(queue)
                ),
            )

        action = str(user_input.get("review_action") or "skip").strip().lower()
        queue = queue[1:]
        self._proposal_review_queue = queue

        if not coordinator:
            return await self.async_step_proposals() if queue else await self.async_step_init()

        current_type = _proposal_review_type(current)
        if current_type == HOUSE_STATE_PROPOSAL_TYPE:
            if action == "accept":
                await coordinator.async_review_house_state_proposal(
                    current_id,
                    decision="approved",
                    approved_by="installer",
                )
            elif action == "reject":
                await coordinator.async_review_house_state_proposal(
                    current_id,
                    decision="rejected",
                    approved_by="installer",
                )
            return await self.async_step_proposals() if queue else await self.async_step_init()

        if current_type == ACTIVITY_PROPOSAL_TYPE:
            if action == "accept":
                await coordinator.async_review_activity_proposal(
                    current_id,
                    decision="approved",
                    approved_by="installer",
                )
            elif action == "reject":
                await coordinator.async_review_activity_proposal(
                    current_id,
                    decision="rejected",
                    approved_by="installer",
                )
            return await self.async_step_proposals() if queue else await self.async_step_init()

        if current_type == SIGNAL_DISCOVERY_REACTION_TYPE:
            if action == "accept":
                await coordinator.async_review_signal_discovery_proposal(
                    current_id,
                    decision="approved",
                )
            elif action == "reject":
                await coordinator.async_review_signal_discovery_proposal(
                    current_id,
                    decision="rejected",
                )
            return await self.async_step_proposals() if queue else await self.async_step_init()

        reactions_cfg = dict(self.options.get(OPT_REACTIONS, {}))
        configured = dict(reactions_cfg.get("configured", {}))
        labels: dict[str, str] = dict(reactions_cfg.get("labels", {}))
        if action == "accept":
            accepted_proposal, target_id, existing_cfg, duplicate_ids = (
                self._resolve_configured_target_for_proposal(current, configured)
            )
            if current.followup_kind == "improvement":
                strategy = self._improvement_acceptance_strategy(current)
                if strategy != "convert_replace":
                    self._proposal_review_queue = [current_id, *queue]
                    return self.async_show_form(
                        step_id="proposals",
                        data_schema=vol.Schema(
                            {
                                vol.Required(
                                    "review_action",
                                    default="accept",
                                ): vol.In(self._proposal_review_action_options()),
                            }
                        ),
                        errors={"base": "unsupported_improvement_strategy"},
                        description_placeholders=self._proposal_review_placeholders(
                            pending, current, len(self._proposal_review_queue)
                        ),
                    )
            if self._proposal_requires_action_completion(current):
                pending_drafts = list(getattr(self, "_pending_action_drafts", []))
                pending_drafts.append(
                    {
                        "proposal": accepted_proposal,
                        "proposal_id": current_id,
                        "target_id": target_id,
                        "existing_config": existing_cfg,
                        "label": current.description,
                    }
                )
                self._pending_action_drafts = pending_drafts
                self._resume_proposal_review = True
                return await self.async_step_proposal_configure_action()

            if self._has_redacted_payload(accepted_proposal.suggested_reaction_config):
                self._proposal_review_queue = [current_id, *queue]
                return self.async_show_form(
                    step_id="proposals",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "review_action",
                                default="accept",
                            ): vol.In(self._proposal_review_action_options()),
                        }
                    ),
                    errors={"base": "redacted_payload"},
                    description_placeholders=self._proposal_review_placeholders(
                        pending, current, len(self._proposal_review_queue)
                    ),
                )

            await coordinator.proposal_engine.async_accept_proposal(current_id)
            configured[target_id] = self._configured_reaction_from_proposal(
                accepted_proposal,
                existing_config=existing_cfg,
            )
            if target_id != current_id:
                configured.pop(current_id, None)
                labels.pop(current_id, None)
            for duplicate_id in duplicate_ids:
                configured.pop(duplicate_id, None)
                labels.pop(duplicate_id, None)
            labels[target_id] = current.description
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._store_reactions_options(reactions_cfg)

        elif action == "reject":
            await coordinator.proposal_engine.async_reject_proposal(current_id)
            configured.pop(current_id, None)
            labels.pop(current_id, None)
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._store_reactions_options(reactions_cfg)

        return await self.async_step_proposals() if queue else await self.async_step_init()

    # ---- Proposal action configuration ----

    async def async_step_proposal_configure_action(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Configure the action(s) to trigger for each accepted proposal, one at a time."""
        pending_drafts: list[dict[str, Any]] = list(getattr(self, "_pending_action_drafts", []))
        if pending_drafts:
            current_draft = pending_drafts[0]
            current_pid = str(
                current_draft.get("target_id") or current_draft.get("proposal_id") or ""
            )
            proposal_description = str(current_draft.get("label") or current_pid)
        else:
            pending: list[str] = getattr(self, "_pending_action_configs", [])
            if not pending:
                return await self.async_step_init()
            current_pid = pending[0]
            labels_map: dict[str, str] = self._reactions_options().get("labels", {})
            proposal_description = labels_map.get(current_pid, current_pid)
            current_draft = None

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("action_entities"): _entity_selector(
                        ["scene", "script"], multiple=True
                    ),
                    vol.Optional("pre_condition_min", default=20): _number_box_selector(
                        min_value=1, max_value=120, step=1
                    ),
                }
            )
            return self.async_show_form(
                step_id="proposal_configure_action",
                data_schema=schema,
                description_placeholders={"proposal_description": proposal_description},
            )

        # Build steps from selected entities
        entities = self._normalize_multi_value(user_input.get("action_entities"))
        steps = self._action_entities_to_steps(entities)
        pre_condition_min = int(user_input.get("pre_condition_min") or 20)

        if current_draft is not None:
            proposal = current_draft["proposal"]
            proposal_id = str(current_draft.get("proposal_id") or "")
            if _proposal_review_type(proposal) == SIGNAL_DISCOVERY_REACTION_TYPE:
                coordinator = self._get_coordinator()
                if coordinator is not None:
                    await coordinator.async_review_signal_discovery_proposal(
                        proposal_id,
                        decision="approved",
                    )
                self._pending_action_drafts = pending_drafts[1:]
                return await self.async_step_proposal_configure_action()
            target_id = str(current_draft.get("target_id") or proposal_id)
            existing_cfg = _safe_mapping(current_draft.get("existing_config"))
            reactions_cfg = dict(self._reactions_options())
            configured = dict(reactions_cfg.get("configured", {}))
            labels = dict(reactions_cfg.get("labels", {}))
            accepted_proposal, resolved_target_id, resolved_existing_cfg, duplicate_ids = (
                self._resolve_configured_target_for_proposal(proposal, configured)
            )
            target_id = resolved_target_id
            if resolved_existing_cfg is not None:
                existing_cfg = resolved_existing_cfg
            cfg = self._configured_reaction_from_proposal(
                accepted_proposal,
                existing_config=existing_cfg,
            )
            cfg["steps"] = steps
            cfg["pre_condition_min"] = pre_condition_min
            if self._has_redacted_payload(cfg):
                return self.async_show_form(
                    step_id="proposal_configure_action",
                    data_schema=vol.Schema(
                        {
                            vol.Optional("action_entities"): _entity_selector(
                                ["scene", "script"], multiple=True
                            ),
                            vol.Optional(
                                "pre_condition_min", default=pre_condition_min
                            ): _number_box_selector(min_value=1, max_value=120, step=1),
                        }
                    ),
                    errors={"base": "redacted_payload"},
                    description_placeholders={
                        "proposal_description": str(
                            current_draft.get("label") or current_draft.get("target_id") or ""
                        )
                    },
                )
            coordinator = self._get_coordinator()
            if coordinator is not None:
                await coordinator.proposal_engine.async_accept_proposal(proposal_id)
            configured[target_id] = cfg
            if target_id != proposal_id:
                configured.pop(proposal_id, None)
                labels.pop(proposal_id, None)
            for duplicate_id in duplicate_ids:
                configured.pop(duplicate_id, None)
                labels.pop(duplicate_id, None)
            labels[target_id] = str(current_draft.get("label") or target_id)
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._store_reactions_options(reactions_cfg)
        else:
            reactions_cfg = dict(self._reactions_options())
            configured = dict(reactions_cfg.get("configured", {}))
            if current_pid in configured:
                cfg = dict(configured[current_pid])
                cfg["steps"] = steps
                cfg["pre_condition_min"] = pre_condition_min
                if self._has_redacted_payload(cfg):
                    return self.async_show_form(
                        step_id="proposal_configure_action",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("action_entities"): _entity_selector(
                                    ["scene", "script"], multiple=True
                                ),
                                vol.Optional(
                                    "pre_condition_min", default=pre_condition_min
                                ): _number_box_selector(min_value=1, max_value=120, step=1),
                            }
                        ),
                        errors={"base": "redacted_payload"},
                        description_placeholders={"proposal_description": proposal_description},
                    )
                configured[current_pid] = cfg
                reactions_cfg["configured"] = configured
                self._store_reactions_options(reactions_cfg)

        # Advance queue
        if pending_drafts:
            self._pending_action_drafts = pending_drafts[1:]
        else:
            self._pending_action_configs = pending[1:]
        if getattr(self, "_pending_action_drafts", []):
            return await self.async_step_proposal_configure_action()
        if getattr(self, "_pending_action_configs", []):
            return await self.async_step_proposal_configure_action()
        if getattr(self, "_resume_proposal_review", False):
            self._resume_proposal_review = False
            if getattr(self, "_proposal_review_queue", []):
                return await self.async_step_proposals()
        return await self.async_step_init()

    @staticmethod
    def _proposal_requires_action_completion(proposal: ReactionProposal) -> bool:
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        reaction_type = resolve_reaction_type(cfg) or str(proposal.reaction_type or "").strip()
        if reaction_type in {
            HOUSE_STATE_PROPOSAL_TYPE,
            "room_smart_lighting_assist",
            "vacation_presence_simulation",
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
        }:
            return False
        steps = cfg.get("steps")
        if isinstance(steps, list) and steps:
            return False
        entity_steps = cfg.get("entity_steps")
        if isinstance(entity_steps, list) and entity_steps:
            return False
        return True

    @staticmethod
    def _proposal_review_label(proposal: ReactionProposal) -> str:
        """Build a compact proposal review label with context and freshness."""
        description = str(proposal.description or "").strip()
        if len(description) > 72:
            description = description[:69].rstrip() + "..."

        cfg = dict(proposal.suggested_reaction_config or {})
        context_parts: list[str] = []
        room_id = str(cfg.get("room_id") or "").strip()
        house_state = str(cfg.get("house_state") or "").strip()
        weekday = cfg.get("weekday")

        if room_id:
            context_parts.append(f"room:{room_id}")
        elif house_state:
            context_parts.append(f"state:{house_state}")
        elif weekday not in (None, ""):
            context_parts.append(f"weekday:{weekday}")
        else:
            context_parts.append(f"type:{proposal.reaction_type}")

        badges = [f"{proposal.confidence:.0%}"]
        if proposal.origin == "admin_authored":
            badges.insert(0, "admin")
        last_seen = _format_last_seen(proposal.last_observed_at)
        if last_seen:
            badges.append(f"seen {last_seen}")

        return f"{description} ({', '.join(context_parts)}) [{' | '.join(badges)}]"

    def _proposal_review_placeholders(
        self,
        proposals: list[ReactionProposal],
        current: ReactionProposal,
        queue_len: int,
    ) -> dict[str, str]:
        """Build placeholders for guided proposal review."""
        pending = [proposal for proposal in proposals if proposal.status == "pending"]
        total = len(pending)
        position = total - queue_len + 1
        remaining = max(total - position, 0)
        return {
            "summary": self._proposals_step_summary(
                proposals, current=current, remaining=remaining
            ),
            "current_position": f"{position}/{total}",
            "proposal_label": self._proposal_review_title(current),
            "proposal_details": self._proposal_review_details(current),
        }

    def _proposal_review_action_options(self) -> dict[str, str]:
        """Return localized review actions for the proposal step."""
        language = self._flow_language()
        if language.startswith("it"):
            return {
                "accept": "Accetta questa proposta",
                "reject": "Rifiuta questa proposta",
                "skip": "Salta per ora",
            }
        return {
            "accept": "Accept this proposal",
            "reject": "Reject this proposal",
            "skip": "Skip for now",
        }

    def _proposal_review_title(self, proposal: ReactionProposal) -> str:
        """Build a concise, user-facing title for the current proposal."""
        if isinstance(proposal, ActivityProposal):
            activity_name = str(proposal.activity_name or "unknown").replace("_", " ")
            if self._flow_language().startswith("it"):
                return f"Attivita appresa: {activity_name}"
            return f"Learned activity: {activity_name}"
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        followup = self._proposal_followup_target(proposal)
        presenter = self._reaction_presenter_for_cfg(cfg)
        language = self._flow_language()
        if proposal.reaction_type == HOUSE_STATE_PROPOSAL_TYPE:
            snapshot = _safe_mapping(cfg.get("context_snapshot"))
            predicted_state = str(
                snapshot.get("predicted_state") or cfg.get("predicted_state") or ""
            )
            if language.startswith("it"):
                return f"Stato casa appreso: {predicted_state or 'sconosciuto'}"
            return f"Learned house state: {predicted_state or 'unknown'}"
        if presenter is not None and presenter.proposal_review_title is not None:
            title = presenter.proposal_review_title(
                self,
                proposal,
                cfg,
                language,
                followup is not None,
            )
            if title:
                return title
        title = self._proposal_human_label(proposal, cfg)
        if proposal.followup_kind == "improvement" and followup is not None:
            if language.startswith("it"):
                return f"Miglioramento: {title}"
            return f"Upgrade: {title}"
        if followup is not None:
            if language.startswith("it"):
                return f"Affinamento: {title}"
            return f"Tuning: {title}"
        if proposal.origin != "admin_authored":
            return title
        if language.startswith("it"):
            return f"Bozza admin: {title}"
        return f"Admin draft: {title}"

    def _proposal_review_details(self, proposal: ReactionProposal) -> str:
        """Build a human-readable review body for one proposal."""
        if isinstance(proposal, ActivityProposal):
            return _activity_proposal_review_details(
                proposal,
                is_it=self._flow_language().startswith("it"),
            )
        cfg = _safe_mapping(proposal.suggested_reaction_config)
        learning = _safe_mapping(cfg.get("learning_diagnostics"))
        language = self._flow_language()
        is_it = language.startswith("it")
        if proposal.reaction_type == HOUSE_STATE_PROPOSAL_TYPE:
            return _house_state_proposal_review_details(proposal, cfg, is_it=is_it)

        details: list[str] = []
        if proposal.origin == "admin_authored":
            details.extend(self._admin_authored_review_details(proposal, cfg, language))
            return "\n".join(details)

        followup = self._proposal_followup_target(proposal)
        if followup is not None:
            if proposal.followup_kind == "improvement":
                details.extend(
                    self._proposal_improvement_review_details(proposal, followup, language)
                )
            else:
                details.extend(self._proposal_tuning_review_details(proposal, followup, language))

        pattern_description = str(proposal.description or "").strip()
        title = self._proposal_human_label(proposal, cfg)
        if pattern_description and pattern_description != title:
            details.append(
                f"Pattern osservato: {pattern_description}"
                if is_it
                else f"Observed pattern: {pattern_description}"
            )

        evidence_parts: list[str] = []
        observations = learning.get("observations_count")
        episodes = learning.get("episodes_observed")
        weeks = learning.get("weeks_observed")
        if observations not in (None, ""):
            evidence_parts.append(
                f"{observations} osservazioni" if is_it else f"{observations} observations"
            )
        if episodes not in (None, ""):
            evidence_parts.append(f"{episodes} episodi" if is_it else f"{episodes} episodes")
        if weeks not in (None, ""):
            evidence_parts.append(f"{weeks} settimane" if is_it else f"{weeks} weeks")
        if evidence_parts:
            details.append(
                f"Evidenza: {', '.join(evidence_parts)}"
                if is_it
                else f"Evidence: {', '.join(evidence_parts)}"
            )

        details.append(
            f"Affidabilità: {proposal.confidence:.0%}"
            if is_it
            else f"Confidence: {proposal.confidence:.0%}"
        )
        last_seen = _format_last_seen(proposal.last_observed_at)
        if last_seen:
            details.append(
                f"Osservata l'ultima volta: {last_seen}" if is_it else f"Last seen: {last_seen}"
            )

        room_id = str(cfg.get("room_id") or "").strip()
        if room_id:
            details.append(f"Stanza: {room_id}" if is_it else f"Applies to room: {room_id}")
        house_state = str(cfg.get("house_state") or "").strip()
        if house_state:
            details.append(
                f"Si applica quando lo stato casa è: {house_state}"
                if is_it
                else f"Applies when house state is: {house_state}"
            )

        weekday = cfg.get("weekday")
        if weekday not in (None, ""):
            weekday_label = self._weekday_label(weekday, language)
            details.append(
                f"Giorno ricorrente: {weekday_label}"
                if is_it
                else f"Recurring day: {weekday_label}"
            )

        presenter = self._reaction_presenter_for_cfg(cfg)
        if presenter is not None and presenter.learned_review_details is not None:
            details.extend(presenter.learned_review_details(self, proposal, cfg, language))

        return "\n".join(details)

    def _proposal_improvement_review_details(
        self,
        proposal: ReactionProposal,
        followup: dict[str, Any],
        language: str,
    ) -> list[str]:
        is_it = language.startswith("it")
        reaction_label = str(followup.get("reaction_label") or followup.get("reaction_id") or "")
        lines = [
            (
                f"Questa proposta sostituisce la reaction esistente: {reaction_label}"
                if is_it
                else f"This proposal replaces the existing reaction: {reaction_label}"
            )
        ]
        descriptor = self._improvement_descriptor(proposal)
        if descriptor is not None:
            localized_reason = descriptor.review_reason_it if is_it else descriptor.review_reason_en
            if localized_reason:
                lines.append(localized_reason)
        return lines

    def _improvement_descriptor(
        self, proposal: ReactionProposal
    ) -> ImprovementProposalDescriptor | None:
        registry = self._learning_plugin_registry()
        if registry is None:
            return None
        return registry.improvement_descriptor_for(
            target_reaction_type=str(proposal.reaction_type or "").strip(),
            source_reaction_type=str(
                proposal.improves_reaction_type or proposal.target_reaction_type or ""
            ).strip(),
            improvement_reason=str(proposal.improvement_reason or "").strip(),
            enabled_only=False,
        )

    def _improvement_acceptance_strategy(self, proposal: ReactionProposal) -> str:
        descriptor = self._improvement_descriptor(proposal)
        if descriptor is None:
            return "convert_replace"
        return str(descriptor.acceptance_strategy or "convert_replace")

    def _proposal_tuning_review_details(
        self,
        proposal: ReactionProposal,
        followup: dict[str, Any],
        language: str,
    ) -> list[str]:
        is_it = language.startswith("it")
        details: list[str] = [
            (
                "Tipo proposta: affinamento di una automazione esistente"
                if is_it
                else "Proposal type: tuning of an existing automation"
            )
        ]

        reaction_label = str(followup.get("reaction_label") or "").strip()
        if reaction_label:
            details.append(
                f"Automazione target: {reaction_label}"
                if is_it
                else f"Target automation: {reaction_label}"
            )

        target_origin = str(followup.get("target_reaction_origin") or "").strip()
        if target_origin:
            origin_label = self._proposal_origin_label(target_origin, language)
            details.append(
                f"Origine automazione attiva: {origin_label}"
                if is_it
                else f"Active automation origin: {origin_label}"
            )

        target_template_id = str(followup.get("target_template_id") or "").strip()
        if target_template_id:
            details.append(f"Template target: {target_template_id}")

        reaction_cfg = _safe_mapping(followup.get("reaction_cfg"))
        presenter = self._reaction_presenter_for_cfg(reaction_cfg)
        if presenter is not None and presenter.tuning_review_details is not None:
            details.extend(
                presenter.tuning_review_details(
                    self,
                    proposal,
                    _safe_mapping(proposal.suggested_reaction_config),
                    reaction_cfg,
                    language,
                )
            )
        return details

    def _admin_authored_review_details(
        self,
        proposal: ReactionProposal,
        cfg: dict[str, Any],
        language: str,
    ) -> list[str]:
        is_it = language.startswith("it")
        details: list[str] = []

        template_id = str(cfg.get("admin_authored_template_id") or "").strip()
        if is_it:
            details.append("Origine: bozza richiesta dall'amministratore")
        else:
            details.append("Origin: draft requested by the administrator")

        if template_id:
            details.append(f"Template: {template_id}")

        details.append("Stato UX: bozza" if is_it else "UX state: draft")
        details.append(
            f"Affidabilità: {proposal.confidence:.0%}"
            if is_it
            else f"Confidence: {proposal.confidence:.0%}"
        )

        room_id = str(cfg.get("room_id") or "").strip()
        if room_id:
            details.append(f"Stanza: {room_id}" if is_it else f"Room: {room_id}")
        presenter = self._reaction_presenter_for_cfg(cfg)
        if presenter is not None and presenter.admin_authored_review_details is not None:
            details.extend(presenter.admin_authored_review_details(self, proposal, cfg, language))

        return details

    def _proposal_human_label(
        self,
        proposal: ReactionProposal,
        cfg: dict[str, Any] | None = None,
    ) -> str:
        """Build the most readable label available for a proposal."""
        cfg = _safe_mapping(cfg if cfg is not None else proposal.suggested_reaction_config)
        language = self._flow_language()
        presenter = self._reaction_presenter_for_cfg(cfg)
        if presenter is not None and presenter.proposal_human_label is not None:
            presented = presenter.proposal_human_label(self, proposal, cfg, language)
            if presented:
                return presented

        derived = self._reaction_label_from_config(
            proposal.proposal_id,
            cfg,
            {},
        )
        if derived != proposal.proposal_id:
            return derived

        room_id = str(cfg.get("room_id") or "").strip()
        house_state = str(cfg.get("house_state") or "").strip()
        weekday = cfg.get("weekday")

        if proposal.reaction_type == "room_cooling_assist" and room_id:
            return (
                f"Raffrescamento {room_id}" if language.startswith("it") else f"Cooling {room_id}"
            )
        if proposal.reaction_type == "room_air_quality_assist" and room_id:
            return f"Aria {room_id}" if language.startswith("it") else f"Air quality {room_id}"
        if proposal.reaction_type == "heating_preference" and house_state:
            return (
                f"Riscaldamento {house_state}"
                if language.startswith("it")
                else f"Heating {house_state}"
            )
        if proposal.reaction_type == "presence_preheat" and weekday not in (None, ""):
            day = self._weekday_label(weekday, language)
            if language.startswith("it"):
                return f"{day}: arrivo tipico"
            return f"{day}: typical arrival"

        return str(proposal.description or proposal.proposal_id)

    def _proposal_followup_target(self, proposal: ReactionProposal) -> dict[str, Any] | None:
        explicit_target_id = str(proposal.target_reaction_id or "").strip()
        if explicit_target_id:
            cfg = self._configured_reaction_cfg(explicit_target_id)
            reaction_cfg = dict(cfg or {})
            labels_map: dict[str, str] = self._reactions_options().get("labels", {})
            return {
                "reaction_id": explicit_target_id,
                "reaction_cfg": reaction_cfg,
                "reaction_label": self._reaction_label_from_config(
                    explicit_target_id, reaction_cfg, labels_map
                ),
                "target_reaction_origin": str(
                    proposal.target_reaction_origin or reaction_cfg.get("origin") or ""
                ),
                "target_template_id": str(
                    proposal.target_template_id or reaction_cfg.get("source_template_id") or ""
                ),
            }

        identity_key = str(proposal.identity_key or "").strip()
        if not identity_key:
            return None
        configured = dict(self._reactions_options().get("configured", {}))
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})
        for reaction_id, raw in configured.items():
            reaction_cfg = _safe_mapping(raw)
            if str(reaction_cfg.get("source_proposal_identity_key") or "").strip() != identity_key:
                continue
            return {
                "reaction_id": str(reaction_id),
                "reaction_cfg": reaction_cfg,
                "reaction_label": self._reaction_label_from_config(
                    str(reaction_id), reaction_cfg, labels_map
                ),
                "target_reaction_origin": str(reaction_cfg.get("origin") or ""),
                "target_template_id": str(reaction_cfg.get("source_template_id") or ""),
            }

        return None

    def _configured_reaction_cfg(self, reaction_id: str) -> dict[str, Any] | None:
        configured = dict(self._reactions_options().get("configured", {}))
        raw = configured.get(reaction_id)
        if isinstance(raw, dict):
            return dict(raw)
        return None

    @staticmethod
    def _reaction_presenter_for_cfg(cfg: dict[str, Any]) -> Any | None:
        reaction_type = resolve_reaction_type(cfg)
        if not reaction_type:
            return None
        registry = create_builtin_reaction_plugin_registry()
        return registry.presenter_for(reaction_type)

    @staticmethod
    def _proposal_origin_label(origin: str, language: str) -> str:
        if language.startswith("it"):
            if origin == "admin_authored":
                return "bozza amministratore"
            if origin == "learned":
                return "appresa da Heima"
        else:
            if origin == "admin_authored":
                return "admin-authored"
            if origin == "learned":
                return "learned"
        return origin
