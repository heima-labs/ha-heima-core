"""Options flow: Reactions step (persisted mute management + proposal review)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN, OPT_REACTIONS
from ..runtime.analyzers.base import ReactionProposal

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class _ReactionsStepsMixin:
    """Mixin for reactions step."""

    async def async_step_reactions(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Show registered reactions and allow toggling persisted mute state."""
        reaction_ids = self._get_registered_reaction_ids()
        current_muted = list(self._reactions_options().get("muted", []))

        if not reaction_ids:
            # No reactions registered — skip silently back to menu
            return await self.async_step_init()

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("muted_reactions"): cv.multi_select(reaction_ids),
                }
            )
            return self.async_show_form(
                step_id="reactions",
                data_schema=self.add_suggested_values_to_schema(
                    schema, {"muted_reactions": current_muted}
                ),
            )

        muted = self._normalize_multi_value(user_input.get("muted_reactions"))
        # Only persist IDs that are actually registered
        muted = [rid for rid in muted if rid in reaction_ids]
        self.options[OPT_REACTIONS] = {"muted": muted}
        return await self.async_step_init()

    # ---- Proposals step (P5) ----

    async def async_step_proposals(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Review pending learning proposals. Skip silently if none are pending."""
        coordinator = self._get_coordinator()
        pending = coordinator.proposal_engine.pending_proposals() if coordinator else []

        if not pending:
            return await self.async_step_init()

        proposal_options = {
            p.proposal_id: f"{p.description[:80]} [{p.confidence:.0%}]"
            for p in pending
        }

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("proposals_accept"): cv.multi_select(proposal_options),
                    vol.Optional("proposals_reject"): cv.multi_select(proposal_options),
                }
            )
            return self.async_show_form(step_id="proposals", data_schema=schema)

        accepted_ids = self._normalize_multi_value(user_input.get("proposals_accept"))
        rejected_ids = [
            pid
            for pid in self._normalize_multi_value(user_input.get("proposals_reject"))
            if pid not in accepted_ids  # accept takes precedence
        ]

        if coordinator:
            reactions_cfg = dict(self.options.get(OPT_REACTIONS, {}))
            configured = dict(reactions_cfg.get("configured", {}))

            for pid in accepted_ids:
                proposal = next((p for p in pending if p.proposal_id == pid), None)
                if proposal is None:
                    continue
                await coordinator.proposal_engine.async_accept_proposal(pid)
                configured[pid] = dict(proposal.suggested_reaction_config)

            for pid in rejected_ids:
                await coordinator.proposal_engine.async_reject_proposal(pid)

            reactions_cfg["configured"] = configured
            self.options[OPT_REACTIONS] = reactions_cfg

        return await self.async_step_init()

    # ---- Helpers ----

    def _reactions_options(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_REACTIONS, {}))

    def _get_coordinator(self) -> Any | None:
        """Return the running coordinator for this entry, or None."""
        try:
            entry_id = self._config_entry.entry_id
            coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id, {}).get("coordinator")
            return coordinator
        except Exception:
            _LOGGER.debug("Could not retrieve coordinator", exc_info=True)
            return None

    def _get_registered_reaction_ids(self) -> list[str]:
        """Return IDs of reactions registered in the running engine for this entry."""
        try:
            coordinator = self._get_coordinator()
            if coordinator is None:
                return []
            engine = getattr(coordinator, "engine", None)
            if engine is None:
                return []
            reactions = getattr(engine, "_reactions", [])
            return [r.reaction_id for r in reactions]
        except Exception:
            _LOGGER.debug("Could not query registered reactions", exc_info=True)
            return []
