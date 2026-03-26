"""Options flow: Reactions step (persisted mute management + proposal review)."""

from __future__ import annotations

from datetime import datetime
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
                description_placeholders=self._proposal_review_placeholders(pending, current, len(queue)),
            )

        action = str(user_input.get("review_action") or "skip").strip().lower()
        queue = queue[1:]
        self._proposal_review_queue = queue

        if not coordinator:
            return await self.async_step_proposals() if queue else await self.async_step_init()

        reactions_cfg = dict(self.options.get(OPT_REACTIONS, {}))
        configured = dict(reactions_cfg.get("configured", {}))
        labels: dict[str, str] = dict(reactions_cfg.get("labels", {}))

        if action == "accept":
            await coordinator.proposal_engine.async_accept_proposal(current_id)
            configured[current_id] = dict(current.suggested_reaction_config)
            labels[current_id] = current.description
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._update_options({OPT_REACTIONS: reactions_cfg})

            if current.suggested_reaction_config.get("reaction_class") not in {
                "LightingScheduleReaction",
                "RoomLightingAssistReaction",
            }:
                self._pending_action_configs = [current_id]
                self._resume_proposal_review = True
                return await self.async_step_proposal_configure_action()

        elif action == "reject":
            await coordinator.proposal_engine.async_reject_proposal(current_id)
            configured.pop(current_id, None)
            labels.pop(current_id, None)
            reactions_cfg["configured"] = configured
            reactions_cfg["labels"] = labels
            self._update_options({OPT_REACTIONS: reactions_cfg})

        return await self.async_step_proposals() if queue else await self.async_step_init()

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
        if getattr(self, "_resume_proposal_review", False):
            self._resume_proposal_review = False
            if getattr(self, "_proposal_review_queue", []):
                return await self.async_step_proposals()
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
            "summary": self._proposals_step_summary(proposals, current=current, remaining=remaining),
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
        cfg = dict(proposal.suggested_reaction_config or {})
        return self._proposal_human_label(proposal, cfg)

    def _proposal_review_details(self, proposal: ReactionProposal) -> str:
        """Build a human-readable review body for one proposal."""
        cfg = dict(proposal.suggested_reaction_config or {})
        learning = dict(cfg.get("learning_diagnostics") or {})
        language = self._flow_language()
        is_it = language.startswith("it")

        details: list[str] = []

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
                f"Osservata l'ultima volta: {last_seen}"
                if is_it
                else f"Last seen: {last_seen}"
            )

        room_id = str(cfg.get("room_id") or "").strip()
        if room_id:
            details.append(
                f"Stanza: {room_id}" if is_it else f"Applies to room: {room_id}"
            )
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

        return "\n".join(details)

    def _proposal_human_label(
        self,
        proposal: ReactionProposal,
        cfg: dict[str, Any] | None = None,
    ) -> str:
        """Build the most readable label available for a proposal."""
        cfg = dict(cfg or proposal.suggested_reaction_config or {})
        derived = self._reaction_label_from_config(
            proposal.proposal_id,
            cfg,
            {},
        )
        if derived != proposal.proposal_id:
            return derived

        language = self._flow_language()
        room_id = str(cfg.get("room_id") or "").strip()
        house_state = str(cfg.get("house_state") or "").strip()
        weekday = cfg.get("weekday")

        if proposal.reaction_type == "lighting_scene_schedule" and room_id:
            return f"Luci {room_id}" if language.startswith("it") else f"Lighting {room_id}"
        if proposal.reaction_type == "room_signal_assist" and room_id:
            return f"Assist {room_id}"
        if proposal.reaction_type == "room_cooling_assist" and room_id:
            return f"Raffrescamento {room_id}" if language.startswith("it") else f"Cooling {room_id}"
        if proposal.reaction_type == "room_air_quality_assist" and room_id:
            return f"Aria {room_id}" if language.startswith("it") else f"Air quality {room_id}"
        if proposal.reaction_type == "room_darkness_lighting_assist" and room_id:
            return f"Luce {room_id}" if language.startswith("it") else f"Lighting {room_id}"
        if proposal.reaction_type == "heating_preference" and house_state:
            return (
                f"Riscaldamento {house_state}" if language.startswith("it") else f"Heating {house_state}"
            )
        if proposal.reaction_type == "presence_preheat" and weekday not in (None, ""):
            day = self._weekday_label(weekday, language)
            if language.startswith("it"):
                return f"{day}: arrivo tipico"
            return f"{day}: typical arrival"

        return str(proposal.description or proposal.proposal_id)

    @staticmethod
    def _weekday_label(weekday: Any, language: str) -> str:
        it_days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        en_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        try:
            index = int(weekday)
            if 0 <= index <= 6:
                return it_days[index] if language.startswith("it") else en_days[index]
        except (TypeError, ValueError):
            pass
        return str(weekday)

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

        if cfg.get("reaction_class") == "RoomSignalAssistReaction":
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                humidity_entities = list(cfg.get("trigger_signal_entities", []))
                temperature_entities = list(cfg.get("temperature_signal_entities", []))
                observed = int(cfg.get("episodes_observed", 0))
                parts = [f"Assist {room_id}"]
                if humidity_entities:
                    parts.append(f"hum:{len(humidity_entities)}")
                if temperature_entities:
                    parts.append(f"temp:{len(temperature_entities)}")
                if observed > 0:
                    parts.append(f"{observed} episodi")
                return " — ".join(parts)
            except (TypeError, ValueError):
                pass

        if cfg.get("reaction_class") == "RoomLightingAssistReaction":
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                primary_entities = list(cfg.get("primary_signal_entities", []))
                entity_steps = list(cfg.get("entity_steps", []))
                parts = [f"Luce {room_id}"]
                if primary_entities:
                    parts.append(f"lux:{len(primary_entities)}")
                if entity_steps:
                    parts.append(f"{len(entity_steps)} entità")
                return " — ".join(parts)
            except (TypeError, ValueError):
                pass

        return labels_map.get(reaction_id, reaction_id)


def _format_last_seen(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (TypeError, ValueError):
        return ""
