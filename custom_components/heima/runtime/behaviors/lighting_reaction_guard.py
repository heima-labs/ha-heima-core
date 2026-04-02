"""Runtime guardrails for reaction-generated lighting steps."""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import Any

from ..contracts import ApplyPlan
from .base import HeimaBehavior


class LightingReactionGuardBehavior(HeimaBehavior):
    """Block reaction-generated lighting steps when room manual hold is active."""

    def __init__(self, state: Any, options: dict[str, Any]) -> None:
        self._state = state
        self._manual_hold_rooms: set[str] = set()
        self._blocked_total = 0
        self._blocked_by_room: dict[str, int] = {}
        self._load_options(options)

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        self._load_options(options)

    def apply_filter(self, plan: ApplyPlan, snapshot: Any) -> ApplyPlan:  # noqa: ARG002
        filtered = []
        for step in plan.steps:
            blocker = self._blocking_reason(step)
            if blocker:
                room_id = blocker.split(":", 1)[1]
                self._blocked_total += 1
                self._blocked_by_room[room_id] = self._blocked_by_room.get(room_id, 0) + 1
                filtered.append(dataclass_replace(step, blocked_by=blocker))
            else:
                filtered.append(step)
        return ApplyPlan(plan_id=plan.plan_id, steps=filtered)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "manual_hold_rooms": sorted(self._manual_hold_rooms),
            "blocked_total": self._blocked_total,
            "blocked_by_room": dict(sorted(self._blocked_by_room.items())),
        }

    def _load_options(self, options: dict[str, Any]) -> None:
        rooms = options.get("lighting_rooms", [])
        enabled: set[str] = set()
        if isinstance(rooms, list):
            for item in rooms:
                if not isinstance(item, dict):
                    continue
                if not bool(item.get("enable_manual_hold", True)):
                    continue
                room_id = str(item.get("room_id") or "").strip()
                if room_id:
                    enabled.add(room_id)
        self._manual_hold_rooms = enabled

    def _blocking_reason(self, step: Any) -> str:
        if str(getattr(step, "blocked_by", "") or "").strip():
            return ""
        if str(getattr(step, "domain", "") or "") != "lighting":
            return ""
        source = str(getattr(step, "source", "") or "").strip()
        if not source.startswith("reaction:"):
            return ""
        room_id = str(getattr(step, "target", "") or "").strip()
        if not room_id or room_id not in self._manual_hold_rooms:
            return ""
        if not bool(self._state.get_binary(f"heima_lighting_hold_{room_id}")):
            return ""
        return f"lighting.manual_hold:{room_id}"
