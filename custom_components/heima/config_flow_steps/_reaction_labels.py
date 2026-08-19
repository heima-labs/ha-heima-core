"""Options flow helpers: reaction labels for persisted reaction management."""

# mypy: ignore-errors

from __future__ import annotations

import logging
from typing import Any

from ..runtime.reactions import (
    create_builtin_reaction_plugin_registry,
    resolve_reaction_type,
)
from ._reaction_builders import _ReactionBuildersMixin

_LOGGER = logging.getLogger(__name__)


class _ReactionLabelsMixin:
    """Mixin for deriving human-readable reaction labels."""

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
            for reaction in getattr(engine, "_reactions", []):
                reaction_id = reaction.reaction_id
                if reaction_id not in result:
                    cfg = configured.get(reaction_id, {})
                    result[reaction_id] = self._reaction_label_from_config(
                        reaction_id, cfg, labels_map
                    )
        except Exception:
            _LOGGER.debug("Could not query registered reactions", exc_info=True)

        # 2. Configured reactions from in-session accepted proposals (not yet saved)
        for proposal_id, cfg in configured.items():
            if proposal_id not in result:
                result[proposal_id] = self._reaction_label_from_config(proposal_id, cfg, labels_map)

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
        registry = create_builtin_reaction_plugin_registry()
        reaction_type = resolve_reaction_type(cfg)
        presenter = registry.presenter_for(reaction_type)
        if presenter is not None and presenter.reaction_label_from_config is not None:
            presented = presenter.reaction_label_from_config(reaction_id, cfg, labels_map)
            if presented:
                return presented

        if reaction_type == "presence_preheat":
            try:
                weekday = int(cfg["weekday"])
                median_min = int(cfg["median_arrival_min"])
                window_half = int(cfg.get("window_half_min", 0))
                hhmm = f"{median_min // 60:02d}:{median_min % 60:02d}"
                spread = f" (± {window_half} min)" if window_half > 0 else ""
                day = _ReactionBuildersMixin._weekday_label(weekday, "it")
                return f"{day}: arrivo alle {hhmm}{spread}"
            except (KeyError, TypeError, ValueError, IndexError):
                pass

        if reaction_type in {
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
        }:
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                primary_signal_name = str(cfg.get("primary_signal_name") or "").strip().lower()
                corroboration_signal_name = (
                    str(cfg.get("corroboration_signal_name") or "").strip().lower()
                )
                primary_entities = list(cfg.get("primary_signal_entities") or [])
                corroboration_entities = list(cfg.get("corroboration_signal_entities") or [])
                legacy_trigger_entities = list(cfg.get("trigger_signal_entities") or [])
                legacy_temperature_entities = list(cfg.get("temperature_signal_entities") or [])
                primary_trigger_mode = str(cfg.get("primary_trigger_mode") or "").strip().lower()
                house_state_filter = str(cfg.get("house_state_filter") or "").strip().lower()
                observed = int(cfg.get("episodes_observed", 0))
                if reaction_type == "room_cooling_assist":
                    parts = [f"Raffrescamento {room_id}"]
                elif reaction_type == "room_air_quality_assist":
                    parts = [f"Aria {room_id}"]
                else:
                    parts = [f"Assist {room_id}"]
                if primary_signal_name:
                    signal_bits = [primary_signal_name]
                    if corroboration_signal_name:
                        signal_bits.append(corroboration_signal_name)
                    parts.append(" + ".join(signal_bits))
                elif legacy_trigger_entities or legacy_temperature_entities:
                    if legacy_trigger_entities:
                        parts.append(f"hum:{len(legacy_trigger_entities)}")
                    if legacy_temperature_entities:
                        parts.append(f"temp:{len(legacy_temperature_entities)}")
                elif primary_entities:
                    parts.append(f"sig:{len(primary_entities)}")
                    if corroboration_entities:
                        parts.append(f"corr:{len(corroboration_entities)}")
                if primary_trigger_mode:
                    parts.append(primary_trigger_mode)
                if house_state_filter:
                    parts.append(f"stato:{house_state_filter}")
                if observed > 0:
                    parts.append(f"{observed} episodi")
                return " — ".join(parts)
            except (TypeError, ValueError):
                pass

        if reaction_type == "room_smart_lighting_assist":
            try:
                room_id = str(cfg.get("room_id", "")).strip() or reaction_id
                primary_signal = str(
                    cfg.get("indoor_lux_signal") or cfg.get("primary_signal_name") or "room_lux"
                ).strip()
                entity_steps = list(cfg.get("entity_steps", []))
                parts = [f"Luce smart {room_id}"]
                if primary_signal:
                    parts.append(primary_signal)
                if entity_steps:
                    parts.append(f"{len(entity_steps)} entità")
                return " — ".join(parts)
            except (TypeError, ValueError):
                pass

        return labels_map.get(reaction_id, reaction_id)
