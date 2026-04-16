"""Room-scoped vacancy-driven lights-off reaction."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.core import HomeAssistant

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from ._lighting_review import (
    render_entity_steps_discovery_details,
    render_entity_steps_tuning_details,
)
from .base import HeimaReaction


class RoomLightingVacancyOffReaction(HeimaReaction):
    """Turn room lights off after the room stays vacant for the learned delay."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        room_id: str,
        entity_steps: list[dict[str, Any]],
        vacancy_delay_s: int,
        reaction_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._room_id = room_id
        self._entity_steps = [
            dict(step)
            for step in entity_steps
            if str(step.get("entity_id") or "").strip()
            and str(step.get("action") or "").strip() == "off"
        ]
        self._vacancy_delay_s = max(0, int(vacancy_delay_s))
        self._reaction_id = reaction_id or self.__class__.__name__
        self._vacant_since_ts: str | None = None
        self._last_fired_ts: float | None = None
        self._fire_count = 0
        self._suppressed_count = 0
        self._vacancy_episode_active = False

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        snapshot = history[-1]
        if self._room_id in snapshot.occupied_rooms:
            self._vacant_since_ts = None
            self._vacancy_episode_active = False
            return []

        if self._vacant_since_ts is None:
            self._vacant_since_ts = snapshot.ts
            self._vacancy_episode_active = True
            return []

        if not self._vacancy_delay_elapsed(history):
            return []
        if not self._entity_steps_need_apply():
            self._vacancy_episode_active = False
            return []
        if not self._is_cooled_down():
            self._suppressed_count += 1
            return []

        self._last_fired_ts = time.monotonic()
        self._fire_count += 1
        self._vacancy_episode_active = False
        return self._build_steps()

    def reset_learning_state(self) -> None:
        self._vacant_since_ts = None
        self._last_fired_ts = None
        self._fire_count = 0
        self._suppressed_count = 0
        self._vacancy_episode_active = False

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_id": self._room_id,
            "entity_steps": len(self._entity_steps),
            "vacancy_delay_s": self._vacancy_delay_s,
            "vacant_since_ts": self._vacant_since_ts,
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "vacancy_episode_active": self._vacancy_episode_active,
        }

    def _vacancy_delay_elapsed(self, history: list[DecisionSnapshot]) -> bool:
        if self._vacancy_delay_s <= 0:
            return True
        if len(history) < 2:
            return False
        start = _parse_snapshot_epoch(self._vacant_since_ts)
        current = _parse_snapshot_epoch(history[-1].ts)
        if start is None or current is None:
            return False
        return (current - start) >= self._vacancy_delay_s

    def _entity_steps_need_apply(self) -> bool:
        for cfg in self._entity_steps:
            entity_id = str(cfg.get("entity_id") or "").strip()
            if not entity_id:
                continue
            state = self._hass.states.get(entity_id)
            current = str(state.state).strip().lower() if state is not None else ""
            if current != "off":
                return True
        return False

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= max(self._vacancy_delay_s, 1)

    def _build_steps(self) -> list[ApplyStep]:
        steps: list[ApplyStep] = []
        for cfg in self._entity_steps:
            entity_id = str(cfg.get("entity_id") or "").strip()
            if not entity_id:
                continue
            steps.append(
                ApplyStep(
                    domain="lighting",
                    target=self._room_id,
                    action="light.turn_off",
                    params={"entity_id": entity_id},
                    reason=f"room_vacancy_lighting_off:{self._reaction_id}",
                )
            )
        return steps


def build_room_lighting_vacancy_off_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomLightingVacancyOffReaction | None:
    try:
        room_id = str(cfg["room_id"]).strip()
        vacancy_delay_s = int(cfg.get("vacancy_delay_s", 0))
        entity_steps = list(cfg.get("entity_steps", []))
        if not room_id or not entity_steps:
            raise ValueError("room_id or entity_steps missing")
    except (KeyError, TypeError, ValueError):
        return None
    return RoomLightingVacancyOffReaction(
        hass=engine._hass,  # noqa: SLF001
        room_id=room_id,
        entity_steps=entity_steps,
        vacancy_delay_s=vacancy_delay_s,
        reaction_id=proposal_id,
    )


def present_room_lighting_vacancy_off_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    try:
        room_id = str(cfg.get("room_id", "")).strip() or reaction_id
        if "vacancy_delay_s" in cfg:
            delay_min = max(1, int(cfg.get("vacancy_delay_s", 0)) // 60)
            return f"Spegni {room_id} dopo {delay_min}m"
        return f"Spegni {room_id} per assenza"
    except (TypeError, ValueError):
        return labels_map.get(reaction_id)


def present_learned_room_lighting_vacancy_off_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    del flow, proposal
    is_it = language.startswith("it")
    details: list[str] = []
    delay_s = cfg.get("vacancy_delay_s")
    if isinstance(delay_s, (int, float)):
        delay_min = max(1, int(delay_s) // 60)
        details.append(
            f"Ritardo spegnimento: {delay_min} minuti"
            if is_it
            else f"Lights-off delay: {delay_min} minutes"
        )
    entity_steps = cfg.get("entity_steps")
    if isinstance(entity_steps, list) and entity_steps:
        details.extend(
            render_entity_steps_discovery_details(
                entity_steps,
                language=language,
            )
        )
    return details


def present_admin_authored_room_lighting_vacancy_off_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    return present_learned_room_lighting_vacancy_off_details(flow, proposal, cfg, language)


def present_tuning_room_lighting_vacancy_off_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return room-vacancy-lighting tuning diff lines."""
    del flow, proposal
    is_it = language.startswith("it")
    details: list[str] = []

    current_delay_s = target_cfg.get("vacancy_delay_s")
    proposed_delay_s = cfg.get("vacancy_delay_s")
    if isinstance(current_delay_s, (int, float)) and isinstance(proposed_delay_s, (int, float)):
        current_delay_min = max(1, int(current_delay_s) // 60)
        proposed_delay_min = max(1, int(proposed_delay_s) // 60)
        if current_delay_min != proposed_delay_min:
            details.append(
                f"Ritardo spegnimento: {current_delay_min} -> {proposed_delay_min} minuti"
                if is_it
                else f"Lights-off delay: {current_delay_min} -> {proposed_delay_min} minutes"
            )

    current_steps = target_cfg.get("entity_steps")
    proposed_steps = cfg.get("entity_steps")
    if isinstance(current_steps, list) and isinstance(proposed_steps, list):
        details.extend(
            render_entity_steps_tuning_details(
                current_steps,
                proposed_steps,
                language=language,
            )
        )

    return details


def present_room_lighting_vacancy_off_proposal_label(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> str | None:
    del flow, proposal
    room_id = str(cfg.get("room_id") or "").strip()
    if not room_id:
        return None
    return (
        f"Spegni {room_id} per assenza" if language.startswith("it") else f"Vacancy off {room_id}"
    )


def present_room_lighting_vacancy_off_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_followup: bool,
) -> str | None:
    del flow
    if getattr(proposal, "origin", "") == "admin_authored":
        return None
    base = present_room_lighting_vacancy_off_proposal_label(None, proposal, cfg, language)
    if not base:
        return None
    if is_followup:
        return (
            f"Affinamento spegnimento luci: {base}"
            if language.startswith("it")
            else f"Lights-off tuning: {base}"
        )
    return (
        f"Nuovo spegnimento luci: {base}"
        if language.startswith("it")
        else f"New lights-off automation: {base}"
    )


def _parse_snapshot_epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(ts).timestamp()
    except (TypeError, ValueError):
        return None
