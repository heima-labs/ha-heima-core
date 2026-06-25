"""Shared manual-hold state and pending-apply provenance."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .contracts import ApplyStep

_DEFAULT_PENDING_APPLY_TTL_S = 5.0
_BRIGHTNESS_TOLERANCE = 5
_COLOR_TEMP_TOLERANCE = 100


@dataclass(frozen=True)
class ManualHoldScope:
    """Scope affected by a manual hold."""

    domain: str
    subject_type: str
    subject_id: str

    @property
    def key(self) -> str:
        """Stable diagnostics/storage key for this scope."""
        return f"{self.domain}:{self.subject_type}:{self.subject_id}"


@dataclass(frozen=True)
class ManualHoldReason:
    """Reason that activated a manual hold."""

    kind: str
    source_entity: str
    message: str = ""


@dataclass
class ManualHoldState:
    """Current manual-hold state for one scope."""

    scope: ManualHoldScope
    reason: ManualHoldReason
    started_monotonic: float
    expires_monotonic: float | None = None
    release_policy: str = "manual_clear"


@dataclass
class PendingApply:
    """Expected state from a Heima-owned service call."""

    entity_id: str
    expected_domain: str
    expected_state: str | None
    timestamp: float
    ttl: float = _DEFAULT_PENDING_APPLY_TTL_S
    expected_attributes: dict[str, Any] = field(default_factory=dict)
    source_reaction_id: str | None = None
    source_reaction_type: str | None = None
    scope: ManualHoldScope | None = None


class ManualHoldManager:
    """Track manual holds and Heima-owned pending applies."""

    def __init__(self, *, monotonic: Any | None = None) -> None:
        self._monotonic = monotonic or time.monotonic
        self._active_holds: dict[str, ManualHoldState] = {}
        self._pending_applies: dict[str, PendingApply] = {}

    def activate_hold(
        self,
        scope: ManualHoldScope,
        reason: ManualHoldReason,
        *,
        expires_in_s: float | None = None,
        release_policy: str = "manual_clear",
    ) -> None:
        """Activate or replace a manual hold for a scope."""
        now = float(self._monotonic())
        expires = now + float(expires_in_s) if expires_in_s is not None else None
        self._active_holds[scope.key] = ManualHoldState(
            scope=scope,
            reason=reason,
            started_monotonic=now,
            expires_monotonic=expires,
            release_policy=release_policy,
        )

    def release_scope(
        self,
        scope: ManualHoldScope,
        *,
        reason: str = "",
        reason_kind: str | None = None,
    ) -> None:
        """Release a manual hold if present."""
        del reason
        if reason_kind is not None:
            state = self._active_holds.get(scope.key)
            if state is None or state.reason.kind != reason_kind:
                return
        self._active_holds.pop(scope.key, None)

    def held_reason_for_scope(self, scope: ManualHoldScope) -> str:
        """Return a blocked_by-compatible reason for an active scope hold."""
        self._expire_holds()
        state = self._active_holds.get(scope.key)
        if state is None:
            return ""
        return f"manual_hold:{scope.key}:{state.reason.kind}"

    def held_reason_for_step(self, step: ApplyStep) -> str:
        """Return a hold reason for an entity-scoped step when held."""
        if step.blocked_by:
            return ""
        scope = self.scope_for_step(step)
        if scope is None:
            if step.domain == "lighting" and str(step.target or "").strip():
                return self.held_reason_for_scope(
                    ManualHoldScope("lighting", "room", str(step.target).strip())
                )
            return ""
        entity_reason = self.held_reason_for_scope(scope)
        if entity_reason:
            return entity_reason
        if scope.domain == "climate" or step.domain == "heating":
            return self.held_reason_for_scope(ManualHoldScope("climate", "domain", "heating"))
        return ""

    def register_pending_apply(
        self,
        step: ApplyStep,
        *,
        scope: ManualHoldScope | None = None,
        source_reaction_type: str | None = None,
    ) -> None:
        """Register pending provenance for an entity-based apply step."""
        pending = self.pending_apply_from_step(
            step,
            scope=scope,
            source_reaction_type=source_reaction_type,
            timestamp=float(self._monotonic()),
        )
        if pending is not None:
            self._pending_applies[pending.entity_id] = pending

    def consume_pending_apply(self, entity_id: str, new_state: Any) -> bool:
        """Return True if a state change matches and consumes a pending apply."""
        entity = str(entity_id or "").strip()
        pending = self._pending_applies.pop(entity, None)
        if pending is None:
            return False
        if float(self._monotonic()) - pending.timestamp >= pending.ttl:
            return False
        state_value = str(getattr(new_state, "state", "") or "").strip().lower()
        if pending.expected_state is not None and state_value != pending.expected_state:
            return False
        attrs = getattr(new_state, "attributes", None)
        attrs = attrs if isinstance(attrs, dict) else {}
        return self._attributes_match(pending, attrs)

    def classify_state_change(self, entity_id: str, new_state: Any) -> str:
        """Classify a tracked state change as Heima-owned or external."""
        if self.consume_pending_apply(entity_id, new_state):
            return "heima_owned"
        return "external"

    def diagnostics(self) -> dict[str, Any]:
        """Return manual-hold diagnostics."""
        self._expire_holds()
        now = float(self._monotonic())
        return {
            "active_holds": [
                {
                    "scope": state.scope.key,
                    "reason": state.reason.kind,
                    "source_entity": state.reason.source_entity,
                    "message": state.reason.message,
                    "age_s": max(0.0, now - state.started_monotonic),
                    "expires_in_s": (
                        max(0.0, state.expires_monotonic - now)
                        if state.expires_monotonic is not None
                        else None
                    ),
                    "release_policy": state.release_policy,
                }
                for state in sorted(self._active_holds.values(), key=lambda item: item.scope.key)
            ],
            "pending_applies": {
                "total": len(self._pending_applies),
                "by_domain": self._pending_apply_counts_by_domain(),
            },
        }

    @staticmethod
    def scope_for_step(step: ApplyStep) -> ManualHoldScope | None:
        """Return the default entity scope for an apply step."""
        entity_id = str(step.params.get("entity_id") or step.target or "").strip()
        if not entity_id or "." not in entity_id:
            return None
        domain = entity_id.split(".", 1)[0]
        if domain not in {"light", "switch", "input_boolean", "climate"}:
            return None
        return ManualHoldScope(domain=domain, subject_type="entity", subject_id=entity_id)

    @staticmethod
    def pending_apply_from_step(
        step: ApplyStep,
        *,
        scope: ManualHoldScope | None,
        source_reaction_type: str | None,
        timestamp: float,
    ) -> PendingApply | None:
        """Build pending provenance from an apply step."""
        entity_id = str(step.params.get("entity_id") or "").strip()
        if not entity_id or "." not in entity_id:
            return None
        domain = entity_id.split(".", 1)[0]
        expected_state = _expected_state_for_action(step.action)
        if domain not in {"light", "switch", "input_boolean"} or expected_state is None:
            return None
        return PendingApply(
            entity_id=entity_id,
            expected_domain=domain,
            expected_state=expected_state,
            timestamp=timestamp,
            expected_attributes=_expected_attributes_for_step(step),
            source_reaction_id=_reaction_id_from_source(step.source),
            source_reaction_type=source_reaction_type,
            scope=scope,
        )

    def _pending_apply_counts_by_domain(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for pending in self._pending_applies.values():
            counts[pending.expected_domain] = counts.get(pending.expected_domain, 0) + 1
        return dict(sorted(counts.items()))

    def _expire_holds(self) -> None:
        now = float(self._monotonic())
        expired = [
            key
            for key, state in self._active_holds.items()
            if state.expires_monotonic is not None and state.expires_monotonic <= now
        ]
        for key in expired:
            self._active_holds.pop(key, None)

    @staticmethod
    def _attributes_match(pending: PendingApply, attrs: dict[str, Any]) -> bool:
        expected_brightness = pending.expected_attributes.get("brightness")
        if not _attr_matches(attrs.get("brightness"), expected_brightness, _BRIGHTNESS_TOLERANCE):
            return False
        expected_color_temp = pending.expected_attributes.get("color_temp_kelvin")
        return _attr_matches(
            attrs.get("color_temp_kelvin"),
            expected_color_temp,
            _COLOR_TEMP_TOLERANCE,
        )


def _expected_state_for_action(action: str) -> str | None:
    if action.endswith(".turn_on"):
        return "on"
    if action.endswith(".turn_off"):
        return "off"
    return None


def _expected_attributes_for_step(step: ApplyStep) -> dict[str, Any]:
    if step.action != "light.turn_on":
        return {}
    attrs: dict[str, Any] = {}
    for key in ("brightness", "color_temp_kelvin"):
        value = _coerce_int(step.params.get(key))
        if value is not None:
            attrs[key] = value
    return attrs


def _reaction_id_from_source(source: str) -> str | None:
    token = str(source or "").strip()
    if not token.startswith("reaction:"):
        return None
    reaction_id = token.split(":", 1)[1].strip()
    return reaction_id or None


def _attr_matches(actual: Any, expected: Any, tolerance: int) -> bool:
    if expected is None:
        return True
    actual_value = _coerce_int(actual)
    expected_value = _coerce_int(expected)
    if actual_value is None or expected_value is None:
        return False
    return abs(actual_value - expected_value) <= tolerance


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
