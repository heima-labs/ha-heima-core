"""SecurityDomain: security state normalization and mismatch detection."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from ...const import (
    DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
    DEFAULT_SECURITY_MISMATCH_PERSIST_S,
    DEFAULT_SECURITY_MISMATCH_POLICY,
)
from ..contracts import HeimaEvent
from ..normalization.config import (
    SECURITY_CORROBORATION_STRATEGY_CONTRACT,
    build_signal_set_strategy_cfg_for_contract,
)
from ..normalization.service import InputNormalizer
from ..state_store import CanonicalState
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)


class SecurityDomain:
    """Normalizes security state and detects armed-away-but-home mismatches."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._security_observation_trace: dict[str, Any] = {}
        self._security_corroboration_trace: dict[str, Any] = {}
        self._security_armed_away_but_home_since: float | None = None
        self._security_armed_away_but_home_emitted: bool = False

    def reset(self) -> None:
        """Called on options reload."""
        self._security_observation_trace = {}
        self._security_corroboration_trace = {}
        self._security_armed_away_but_home_since = None
        self._security_armed_away_but_home_emitted = False

    @property
    def observation_trace(self) -> dict[str, Any]:
        return self._security_observation_trace

    @property
    def corroboration_trace(self) -> dict[str, Any]:
        return self._security_corroboration_trace

    def diagnostics(self) -> dict[str, Any]:
        return {
            "observation_trace": dict(self._security_observation_trace),
            "corroboration_trace": dict(self._security_corroboration_trace),
        }

    # ------------------------------------------------------------------
    # Observation compute
    # ------------------------------------------------------------------

    def compute(
        self,
        *,
        security_cfg: dict[str, Any],
        state: CanonicalState,
    ) -> tuple[str, str]:
        """Normalize security state. Returns (security_state, security_reason)."""
        if not security_cfg.get("enabled"):
            self._security_observation_trace = {
                "state": "unknown",
                "reason": "disabled",
                "available": False,
                "source_entity_id": None,
            }
            return "unknown", "disabled"

        entity_id = str(security_cfg.get("security_state_entity", ""))
        security_obs = self._normalizer.security(
            entity_id,
            {
                "armed_away_value": security_cfg.get("armed_away_value", "armed_away"),
                "armed_home_value": security_cfg.get("armed_home_value", "armed_home"),
            },
        )
        security_state = security_obs.state
        security_reason = security_obs.reason or "normalized"
        self._security_observation_trace = security_obs.as_dict()
        state.set_sensor("heima_security_state", security_state)
        state.set_sensor("heima_security_reason", security_reason)
        return security_state, security_reason

    # ------------------------------------------------------------------
    # Mismatch detection
    # ------------------------------------------------------------------

    def queue_security_consistency_events(
        self,
        *,
        anyone_home: bool,
        security_state: str,
        security_reason: str,
        options: dict[str, Any],
        people_home_list: list[str],
        occupied_rooms: list[str],
        events: EventsDomain,
        schedule_recheck: Callable[..., None],
        room_configs: dict[str, dict[str, Any]],
        state: CanonicalState,
        room_occupancy_mode_fn: Callable[[dict[str, Any]], str],
        notifications_cfg: dict[str, Any],
    ) -> None:
        security_cfg = dict(options.get("security", {}))
        if not security_cfg.get("enabled"):
            self._security_armed_away_but_home_since = None
            self._security_armed_away_but_home_emitted = False
            return

        mismatch_cfg = self._mismatch_config(notifications_cfg)
        policy = mismatch_cfg["policy"]
        if policy == "off":
            self._security_armed_away_but_home_since = None
            self._security_armed_away_but_home_emitted = False
            return

        mismatch_active = security_state == "armed_away" and anyone_home
        persist_s = 0 if policy == "strict" else mismatch_cfg["persist_s"]

        has_room_evidence = any(
            room_occupancy_mode_fn(room_configs.get(room_id, {})) == "derived"
            for room_id in occupied_rooms
        )
        has_anonymous_evidence = bool(state.get_binary("heima_anonymous_presence"))
        corroboration_inputs = [
            self._normalizer.boolean_value(
                has_room_evidence,
                source_key="security:derived_room_evidence",
                reason="derived_room_occupied" if has_room_evidence else "no_derived_room_occupied",
            ),
            self._normalizer.boolean_value(
                has_anonymous_evidence,
                source_key="security:anonymous_presence_evidence",
                reason="anonymous_presence_on" if has_anonymous_evidence else "anonymous_presence_off",
            ),
        ]
        corroboration = self._normalizer.derive(
            kind="boolean_signal",
            inputs=corroboration_inputs,
            strategy_cfg=build_signal_set_strategy_cfg_for_contract(
                contract=SECURITY_CORROBORATION_STRATEGY_CONTRACT,
            ),
            context={"source": "security_corroboration"},
        )
        self._security_corroboration_trace = {
            "source_observations": [obs.as_dict() for obs in corroboration_inputs],
            "fused_observation": corroboration.as_dict(),
            "plugin_id": corroboration.plugin_id,
            "used_plugin_fallback": corroboration.reason == "plugin_error_fallback",
        }
        if policy == "smart":
            mismatch_active = mismatch_active and corroboration.state == "on"

        if self._persistent_security_mismatch_ready(
            active=mismatch_active,
            persist_s=persist_s,
            schedule_recheck=schedule_recheck,
        ):
            shared_context = {
                "security_state": security_state,
                "security_observation_reason": self._security_observation_trace.get("reason"),
                "people_home_list": list(people_home_list),
                "policy": policy,
                "persist_s": persist_s,
                "occupied_rooms": list(occupied_rooms),
                "has_room_evidence": has_room_evidence,
                "has_anonymous_evidence": has_anonymous_evidence,
            }
            for event in self._build_security_mismatch_events(
                event_mode=mismatch_cfg["event_mode"],
                subtype="armed_away_but_home",
                shared_context=shared_context,
            ):
                events.queue_event(event)

    def _persistent_security_mismatch_ready(
        self,
        *,
        active: bool,
        persist_s: int,
        schedule_recheck: Callable[..., None],
    ) -> bool:
        now = time.monotonic()
        if not active:
            self._security_armed_away_but_home_since = None
            self._security_armed_away_but_home_emitted = False
            return False
        if self._security_armed_away_but_home_since is None:
            self._security_armed_away_but_home_since = now
            self._security_armed_away_but_home_emitted = False
        if self._security_armed_away_but_home_emitted:
            return False
        if persist_s <= 0 or (now - self._security_armed_away_but_home_since) >= persist_s:
            self._security_armed_away_but_home_emitted = True
            return True
        schedule_recheck(
            job_id="security:armed_away_but_home",
            deadline=self._security_armed_away_but_home_since + persist_s,
            owner="security",
            label="Security armed-away-but-home persistence",
        )
        return False

    @staticmethod
    def _mismatch_config(notifications_cfg: dict[str, Any]) -> dict[str, Any]:
        policy = str(notifications_cfg.get("security_mismatch_policy", DEFAULT_SECURITY_MISMATCH_POLICY))
        if policy not in {"off", "smart", "strict"}:
            policy = DEFAULT_SECURITY_MISMATCH_POLICY
        event_mode = str(
            notifications_cfg.get(
                "security_mismatch_event_mode",
                DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
            )
        )
        if event_mode not in {"explicit_only", "generic_only", "dual_emit"}:
            event_mode = DEFAULT_SECURITY_MISMATCH_EVENT_MODE
        return {
            "policy": policy,
            "event_mode": event_mode,
            "persist_s": int(
                notifications_cfg.get("security_mismatch_persist_s", DEFAULT_SECURITY_MISMATCH_PERSIST_S)
            ),
        }

    @staticmethod
    def _build_security_mismatch_events(
        *,
        event_mode: str,
        subtype: str,
        shared_context: dict[str, Any],
    ) -> list[HeimaEvent]:
        explicit_event = HeimaEvent(
            type=f"security.{subtype}",
            key=f"security.{subtype}",
            severity="warn",
            title="Security inconsistency",
            message="Security is armed away while someone is home.",
            context=dict(shared_context),
        )
        generic_event = HeimaEvent(
            type="security.mismatch",
            key=f"security.mismatch.{subtype}",
            severity="warn",
            title="Security mismatch",
            message=f"Security mismatch detected ({subtype}).",
            context={
                "subtype": subtype,
                "policy": shared_context.get("policy"),
                "persist_s": shared_context.get("persist_s"),
                "evidence": {
                    "has_room_evidence": shared_context.get("has_room_evidence"),
                    "has_anonymous_evidence": shared_context.get("has_anonymous_evidence"),
                    "occupied_rooms": list(shared_context.get("occupied_rooms", [])),
                },
                "details": dict(shared_context),
            },
        )
        if event_mode == "generic_only":
            return [generic_event]
        if event_mode == "dual_emit":
            return [explicit_event, generic_event]
        return [explicit_event]

    def tracked_entities(self, security_cfg: dict[str, Any]) -> set[str]:
        tracked: set[str] = set()
        entity_id = security_cfg.get("security_state_entity")
        if entity_id:
            tracked.add(str(entity_id))
        return tracked
