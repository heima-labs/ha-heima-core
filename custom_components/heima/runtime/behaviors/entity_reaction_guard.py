"""Runtime guardrails for reaction-generated entity steps.

Provides a generic guard behavior that blocks reaction-generated actions on entities
when a corresponding manual hold is active. Works for any domain (switch, light, cover, etc.).
"""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from typing import Any

from ..contracts import ApplyPlan
from .base import HeimaBehavior


class EntityReactionGuardBehavior(HeimaBehavior):
    """Block reaction-generated entity steps when manual hold is active.

    This is a generic guard behavior that can be configured to work with any domain
    (switch, light, cover, etc.). It checks for manual hold entities and blocks
    corresponding actions when the hold is active.

    Configuration:
        - hold_entity_pattern: Pattern for hold entities (e.g., "heima_{domain}_manual_hold")
        - target_domain: Domain to filter (e.g., "switch", "light", "cover")
        - extract_entity_id: Optional function to extract entity ID from target

    Hold entities:
        - Global: {hold_entity_pattern} (e.g., "heima_switch_manual_hold")
        - Per-entity: {hold_entity_pattern}_{entity_id} (e.g., "heima_switch_manual_hold_camera1")
    """

    def __init__(
        self,
        state: Any,
        options: dict[str, Any],
        hold_entity_pattern: str = "heima_{domain}_manual_hold",
        target_domain: str = "switch",
    ) -> None:
        self._state = state
        self._hold_entity_pattern = hold_entity_pattern.format(domain=target_domain)
        self._target_domain = target_domain
        self._blocked_total = 0
        self._blocked_by_entity: dict[str, int] = {}

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        """Called when integration options are reloaded."""
        # No dynamic options for this behavior yet
        pass

    def apply_filter(self, plan: ApplyPlan, snapshot: Any) -> ApplyPlan:  # noqa: ARG002
        """Filter out steps that are blocked by manual hold."""
        filtered = []
        for step in plan.steps:
            blocker = self._blocking_reason(step)
            if blocker:
                entity_id = blocker.split(":", 1)[1]
                self._blocked_total += 1
                self._blocked_by_entity[entity_id] = self._blocked_by_entity.get(entity_id, 0) + 1
                filtered.append(dataclass_replace(step, blocked_by=blocker))
            else:
                filtered.append(step)
        return ApplyPlan(plan_id=plan.plan_id, steps=filtered)

    def diagnostics(self) -> dict[str, Any]:
        """Return guard behavior diagnostics."""
        return {
            "hold_entity_pattern": self._hold_entity_pattern,
            "target_domain": self._target_domain,
            "blocked_total": self._blocked_total,
            "blocked_by_entity": dict(sorted(self._blocked_by_entity.items())),
        }

    def _blocking_reason(self, step: Any) -> str:
        """Return blocking reason if step should be blocked, empty string otherwise."""
        # Already blocked by another guard
        if str(getattr(step, "blocked_by", "") or "").strip():
            return ""

        # Wrong domain
        if str(getattr(step, "domain", "") or "").strip() != self._target_domain:
            return ""

        target = str(getattr(step, "target", "") or "").strip()
        if not target or "." not in target:
            return ""

        # Check global hold (e.g., "heima_switch_manual_hold")
        if bool(self._state.get_binary(self._hold_entity_pattern)):
            return f"{self._target_domain}.manual_hold:global"

        # Check per-entity hold
        # Extract entity ID from target (e.g., "switch.camera1_privacy" -> "camera1_privacy")
        entity_id = target.split(".", 1)[1]  # Remove domain prefix
        per_entity_hold = f"{self._hold_entity_pattern}_{entity_id}"
        if bool(self._state.get_binary(per_entity_hold)):
            return f"{self._target_domain}.manual_hold:{entity_id}"

        # Also try without common suffixes (e.g., "camera1_privacy" -> try "camera1" too)
        # This allows users to create hold entities like "heima_switch_manual_hold_camera1"
        # that block all actions for "switch.camera1_*"
        base_entity_id = entity_id.rsplit("_", 1)[0] if "_" in entity_id else entity_id
        if base_entity_id != entity_id:
            base_hold = f"{self._hold_entity_pattern}_{base_entity_id}"
            if bool(self._state.get_binary(base_hold)):
                return f"{self._target_domain}.manual_hold:{base_entity_id}"

        return ""
