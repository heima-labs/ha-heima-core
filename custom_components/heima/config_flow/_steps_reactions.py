"""Options flow: Reactions step (persisted mute management + proposal review)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN, OPT_REACTIONS
from ..runtime.analyzers.base import ReactionProposal
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class _ReactionsStepsMixin:
    """Mixin for reactions step."""

    async def async_step_reactions(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Show registered reactions and allow toggling persisted mute state."""
        reaction_labels = self._get_registered_reaction_labels()
        current_muted = list(self._reactions_options().get("muted", []))

        if not reaction_labels:
            # No reactions registered — skip silently back to menu
            return await self.async_step_init()

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("muted_reactions"): cv.multi_select(reaction_labels),
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
        muted = [rid for rid in muted if rid in reaction_labels]
        self._update_options({OPT_REACTIONS: {"muted": muted}})
        return await self.async_step_init()

    # ---- Edit configured reaction ----

    async def async_step_reactions_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Select a configured reaction to edit."""
        configured: dict[str, Any] = self._reactions_options().get("configured", {})
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})
        if not configured:
            return await self.async_step_init()

        reaction_labels = {
            pid: self._reaction_label_from_config(pid, cfg, labels_map)
            for pid, cfg in configured.items()
        }

        if user_input is None:
            schema = vol.Schema(
                {vol.Required("reaction"): vol.In(reaction_labels)}
            )
            return self.async_show_form(step_id="reactions_edit", data_schema=schema)

        self._editing_reaction_id = user_input.get("reaction")
        return await self.async_step_reactions_edit_form()

    async def async_step_reactions_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Edit action_entities and pre_condition_min for the selected reaction."""
        pid = getattr(self, "_editing_reaction_id", None)
        if not pid:
            return await self.async_step_init()

        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        labels_map: dict[str, str] = reactions_cfg.get("labels", {})
        cfg = dict(configured.get(pid, {}))

        if user_input is None:
            current_steps = cfg.get("steps", [])
            current_entities = [s["target"] for s in current_steps if isinstance(s, dict) and "target" in s]
            current_pre = cfg.get("pre_condition_min", 20)
            schema = vol.Schema(
                {
                    vol.Optional("action_entities"): _entity_selector(
                        ["scene", "script"], multiple=True
                    ),
                    vol.Optional("pre_condition_min", default=current_pre): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=120)
                    ),
                }
            )
            label = self._reaction_label_from_config(pid, cfg, labels_map)
            return self.async_show_form(
                step_id="reactions_edit_form",
                data_schema=self.add_suggested_values_to_schema(
                    schema, {"action_entities": current_entities, "pre_condition_min": current_pre}
                ),
                description_placeholders={"reaction_description": label},
            )

        entities = self._normalize_multi_value(user_input.get("action_entities"))
        steps = self._action_entities_to_steps(entities)
        cfg["steps"] = steps
        cfg["pre_condition_min"] = int(user_input.get("pre_condition_min") or 20)
        configured[pid] = cfg
        reactions_cfg["configured"] = configured
        self._update_options({OPT_REACTIONS: reactions_cfg})
        self._editing_reaction_id = None
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

            labels: dict[str, str] = dict(reactions_cfg.get("labels", {}))

            for pid in accepted_ids:
                proposal = next((p for p in pending if p.proposal_id == pid), None)
                if proposal is None:
                    continue
                await coordinator.proposal_engine.async_accept_proposal(pid)
                configured[pid] = dict(proposal.suggested_reaction_config)
                labels[pid] = proposal.description

            for pid in rejected_ids:
                await coordinator.proposal_engine.async_reject_proposal(pid)
                configured.pop(pid, None)
                labels.pop(pid, None)

            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._update_options({OPT_REACTIONS: reactions_cfg})

        # Self-contained reactions (e.g. LightingScheduleReaction) carry all their
        # config in suggested_reaction_config — skip the action configuration step.
        proposal_map = {p.proposal_id: p for p in pending}
        needs_action_config = [
            pid for pid in accepted_ids
            if proposal_map.get(pid) is not None
            and proposal_map[pid].suggested_reaction_config.get("reaction_class")
            != "LightingScheduleReaction"
        ]
        if needs_action_config:
            self._pending_action_configs = needs_action_config
            return await self.async_step_proposal_configure_action()

        return await self.async_step_init()

    # ---- Proposal action configuration ----

    async def async_step_proposal_configure_action(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Configure the action(s) to trigger for each accepted proposal, one at a time."""
        pending: list[str] = getattr(self, "_pending_action_configs", [])
        if not pending:
            return await self.async_step_init()

        current_pid = pending[0]
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})
        proposal_description = labels_map.get(current_pid, current_pid)

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional("action_entities"): _entity_selector(
                        ["scene", "script"], multiple=True
                    ),
                    vol.Optional("pre_condition_min", default=20): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=120)
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

        reactions_cfg = dict(self._reactions_options())
        configured = dict(reactions_cfg.get("configured", {}))
        if current_pid in configured:
            cfg = dict(configured[current_pid])
            cfg["steps"] = steps
            cfg["pre_condition_min"] = pre_condition_min
            configured[current_pid] = cfg
            reactions_cfg["configured"] = configured
            self._update_options({OPT_REACTIONS: reactions_cfg})

        # Advance queue
        self._pending_action_configs = pending[1:]
        if self._pending_action_configs:
            return await self.async_step_proposal_configure_action()
        return await self.async_step_init()

    # ---- Helpers ----

    def _reactions_options(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_REACTIONS, {}))

    @staticmethod
    def _action_entities_to_steps(entities: list[str]) -> list[dict[str, Any]]:
        """Normalize selected action entities into executable ApplyStep-like dicts."""
        steps: list[dict[str, Any]] = []
        for entity_id in entities:
            domain = str(entity_id).split(".", 1)[0]
            if domain == "scene":
                steps.append(
                    {
                        "domain": "lighting",
                        "target": entity_id,
                        "action": "scene.turn_on",
                        "params": {"entity_id": entity_id},
                    }
                )
            elif domain == "script":
                steps.append(
                    {
                        "domain": "script",
                        "target": entity_id,
                        "action": "script.turn_on",
                        "params": {"entity_id": entity_id},
                    }
                )
        return steps

    def _get_coordinator(self) -> Any | None:
        """Return the running coordinator for this entry, or None."""
        try:
            entry_id = self._config_entry.entry_id
            coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id, {}).get("coordinator")
            return coordinator
        except Exception:
            _LOGGER.debug("Could not retrieve coordinator", exc_info=True)
            return None

    def _get_registered_reaction_labels(self) -> dict[str, str]:
        """Return {reaction_id: human_readable_label} for all reactions available for muting.

        Label is derived from the stored reaction config (always up-to-date), with the
        saved ``labels`` entry as fallback for unknown reaction classes.
        """
        result: dict[str, str] = {}
        configured: dict[str, Any] = self._reactions_options().get("configured", {})
        labels_map: dict[str, str] = self._reactions_options().get("labels", {})

        # 1. Running engine reactions (already persisted and loaded)
        try:
            coordinator = self._get_coordinator()
            engine = getattr(coordinator, "engine", None) if coordinator else None
            for r in getattr(engine, "_reactions", []):
                rid = r.reaction_id
                if rid not in result:
                    cfg = configured.get(rid, {})
                    result[rid] = self._reaction_label_from_config(rid, cfg, labels_map)
        except Exception:
            _LOGGER.debug("Could not query registered reactions", exc_info=True)

        # 2. Configured reactions from in-session accepted proposals (not yet saved)
        for pid, cfg in configured.items():
            if pid not in result:
                result[pid] = self._reaction_label_from_config(pid, cfg, labels_map)

        return result

    @staticmethod
    def _reaction_label_from_config(
        reaction_id: str, cfg: dict[str, Any], labels_map: dict[str, str]
    ) -> str:
        """Derive a human-readable label from a stored reaction config dict.

        For PresencePatternReaction: generates "Weekday: arrival at HH:MM (± N min)"
        from weekday + median_arrival_min + window_half_min stored in the config.
        Falls back to labels_map, then to reaction_id.
        """
        _WEEKDAY_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

        if cfg.get("reaction_class") == "PresencePatternReaction":
            try:
                weekday = int(cfg["weekday"])
                median_min = int(cfg["median_arrival_min"])
                window_half = int(cfg.get("window_half_min", 0))
                hhmm = f"{median_min // 60:02d}:{median_min % 60:02d}"
                spread = f" (± {window_half} min)" if window_half > 0 else ""
                day = _WEEKDAY_IT[weekday] if 0 <= weekday <= 6 else str(weekday)
                return f"{day}: arrivo alle {hhmm}{spread}"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        if cfg.get("reaction_class") == "LightingScheduleReaction":
            try:
                weekday = int(cfg["weekday"])
                scheduled_min = int(cfg["scheduled_min"])
                room_id = str(cfg.get("room_id", ""))
                hhmm = f"{scheduled_min // 60:02d}:{scheduled_min % 60:02d}"
                day = _WEEKDAY_IT[weekday] if 0 <= weekday <= 6 else str(weekday)
                n_steps = len(cfg.get("entity_steps", []))
                return f"Luci {room_id} — {day} ~{hhmm} ({n_steps} entità)"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        return labels_map.get(reaction_id, reaction_id)
