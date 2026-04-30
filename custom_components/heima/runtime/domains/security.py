"""SecurityDomain: security state normalization and mismatch detection."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from ...const import (
    DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
    DEFAULT_SECURITY_MISMATCH_PERSIST_S,
    DEFAULT_SECURITY_MISMATCH_POLICY,
)
from ..contracts import HeimaEvent
from ..domain_result_bag import DomainResultBag
from ..normalization.config import (
    SECURITY_CORROBORATION_STRATEGY_CONTRACT,
    build_signal_set_strategy_cfg_for_contract,
)
from ..normalization.service import InputNormalizer
from ..state_store import CanonicalState
from .events import EventsDomain
from .security_camera_evidence import SecurityCameraEvidenceResult

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecurityDomainResult:
    """Current-cycle Security plugin output."""

    security_state: str
    security_reason: str
    breach_candidates: list[dict[str, Any]]


class SecurityDomain:
    """Normalizes security state and detects armed-away-but-home mismatches."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._security_observation_trace: dict[str, Any] = {}
        self._security_corroboration_trace: dict[str, Any] = {}
        self._camera_evidence_trace: dict[str, Any] = {}
        self._security_armed_away_but_home_since: float | None = None
        self._security_armed_away_but_home_emitted: bool = False
        self._plugin_security_config_provider: Callable[[], dict[str, Any]] | None = None
        self._plugin_options_provider: Callable[[], dict[str, Any]] | None = None
        self._plugin_camera_evidence_provider: Callable[[], Any] | None = None
        self._plugin_events_provider: Callable[[], EventsDomain] | None = None
        self._plugin_schedule_recheck: Callable[..., None] | None = None
        self._plugin_room_configs_provider: Callable[[], dict[str, dict[str, Any]]] | None = None
        self._plugin_room_occupancy_mode_fn: Callable[[dict[str, Any]], str] | None = None
        self._plugin_notifications_config_provider: Callable[[], dict[str, Any]] | None = None

    @property
    def domain_id(self) -> str:
        return "security"

    @property
    def depends_on(self) -> list[str]:
        return ["people", "occupancy"]

    def bind_plugin_runtime(
        self,
        *,
        security_config_provider: Callable[[], dict[str, Any]],
        options_provider: Callable[[], dict[str, Any]],
        camera_evidence_provider: Callable[[], Any],
        events_provider: Callable[[], EventsDomain],
        schedule_recheck: Callable[..., None],
        room_configs_provider: Callable[[], dict[str, dict[str, Any]]],
        room_occupancy_mode_fn: Callable[[dict[str, Any]], str],
        notifications_config_provider: Callable[[], dict[str, Any]],
    ) -> None:
        """Bind engine-owned dependencies used by the plugin wrapper."""
        self._plugin_security_config_provider = security_config_provider
        self._plugin_options_provider = options_provider
        self._plugin_camera_evidence_provider = camera_evidence_provider
        self._plugin_events_provider = events_provider
        self._plugin_schedule_recheck = schedule_recheck
        self._plugin_room_configs_provider = room_configs_provider
        self._plugin_room_occupancy_mode_fn = room_occupancy_mode_fn
        self._plugin_notifications_config_provider = notifications_config_provider

    def reset(self) -> None:
        """Called on options reload."""
        self._security_observation_trace = {}
        self._security_corroboration_trace = {}
        self._camera_evidence_trace = {}
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
            "camera_evidence_trace": dict(self._camera_evidence_trace),
        }

    # ------------------------------------------------------------------
    # Observation compute
    # ------------------------------------------------------------------

    def compute(
        self,
        canonical_state: CanonicalState,
        domain_results: DomainResultBag,
        signals: list[Any] | None = None,
    ) -> SecurityDomainResult:
        """Compute security through the plugin contract."""
        del signals
        if (
            self._plugin_security_config_provider is None
            or self._plugin_options_provider is None
            or self._plugin_camera_evidence_provider is None
            or self._plugin_events_provider is None
            or self._plugin_schedule_recheck is None
            or self._plugin_room_configs_provider is None
            or self._plugin_room_occupancy_mode_fn is None
            or self._plugin_notifications_config_provider is None
        ):
            raise RuntimeError("Security plugin runtime is not bound")

        security_cfg = dict(self._plugin_security_config_provider())
        camera_evidence = self._plugin_camera_evidence_provider()
        people_result = domain_results.require("people")
        occupancy_result = domain_results.require("occupancy")

        security_state, security_reason = self.compute_security_state(
            security_cfg=security_cfg,
            state=canonical_state,
        )
        canonical_state.set_sensor_attributes(
            "heima_security_state",
            {
                **(canonical_state.get_sensor_attributes("heima_security_state") or {}),
                "camera_evidence": camera_evidence.as_dict(),
            },
        )
        canonical_state.set_sensor_attributes(
            "heima_security_reason",
            {
                **(canonical_state.get_sensor_attributes("heima_security_reason") or {}),
                "camera_evidence": camera_evidence.as_dict(),
            },
        )
        breach_candidates = self.consume_camera_evidence(
            security_state=security_state,
            camera_evidence=camera_evidence,
            state=canonical_state,
        )
        self.queue_security_consistency_events(
            anyone_home=bool(people_result.anyone_home),
            security_state=security_state,
            security_reason=security_reason,
            options=dict(self._plugin_options_provider()),
            people_home_list=list(people_result.people_home_list),
            occupied_rooms=list(occupancy_result.occupied_rooms),
            events=self._plugin_events_provider(),
            schedule_recheck=self._plugin_schedule_recheck,
            room_configs=dict(self._plugin_room_configs_provider()),
            state=canonical_state,
            room_occupancy_mode_fn=self._plugin_room_occupancy_mode_fn,
            notifications_cfg=dict(self._plugin_notifications_config_provider()),
        )
        return SecurityDomainResult(
            security_state=security_state,
            security_reason=security_reason,
            breach_candidates=breach_candidates,
        )

    def compute_security_state(
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

    def consume_camera_evidence(
        self,
        *,
        security_state: str,
        camera_evidence: SecurityCameraEvidenceResult,
        state: CanonicalState,
    ) -> list[dict[str, Any]]:
        """Turn provider output into bounded security breach candidates."""
        active_evidence = list(camera_evidence.active_evidence)
        configured_sources = {
            str(item.get("id") or ""): dict(item)
            for item in camera_evidence.configured_sources
            if isinstance(item, dict)
        }
        candidates: list[dict[str, Any]] = []

        if security_state == "armed_away":
            for record in active_evidence:
                source = configured_sources.get(record.source_id, {})
                role = str(record.role or source.get("role") or "")
                kinds = set(source.get("active_kinds", [])) if isinstance(source, dict) else set()
                contact_active = (
                    bool(source.get("contact_active")) if isinstance(source, dict) else False
                )

                if role == "entry" and record.kind == "person":
                    candidates.append(
                        {
                            "rule": "armed_away_entry_person",
                            "severity": "suspicious",
                            "source_id": record.source_id,
                            "role": role,
                            "evidence_kinds": sorted(kinds or {record.kind}),
                            "contact_active": contact_active,
                            "reason": "entry_person_detected_while_armed_away",
                        }
                    )
                elif role == "garage" and ({"person", "vehicle"} & kinds) and contact_active:
                    candidates.append(
                        {
                            "rule": "armed_away_garage_open_with_presence",
                            "severity": "strong",
                            "source_id": record.source_id,
                            "role": role,
                            "evidence_kinds": sorted(kinds),
                            "contact_active": True,
                            "reason": "garage_contact_active_with_person_or_vehicle_while_armed_away",
                        }
                    )
                elif role == "indoor_sensitive" and record.kind in {"motion", "person"}:
                    candidates.append(
                        {
                            "rule": "armed_away_indoor_sensitive_activity",
                            "severity": "strong",
                            "source_id": record.source_id,
                            "role": role,
                            "evidence_kinds": sorted(kinds or {record.kind}),
                            "contact_active": contact_active,
                            "reason": "indoor_sensitive_activity_while_armed_away",
                        }
                    )

        deduped = self._dedupe_candidates(candidates)
        self._camera_evidence_trace = {
            "security_state": security_state,
            "active_evidence": [item.as_dict() for item in active_evidence],
            "source_status_counts": camera_evidence.as_dict().get("source_status_counts", {}),
            "return_home_hint": bool(camera_evidence.return_home_hint),
            "return_home_hint_reasons": [
                dict(item) for item in camera_evidence.return_home_hint_reasons
            ],
            "breach_candidates": list(deduped),
        }
        state.set_sensor_attributes(
            "heima_security_state",
            {
                **(state.get_sensor_attributes("heima_security_state") or {}),
                "camera_breach_candidates": list(deduped),
            },
        )
        state.set_sensor_attributes(
            "heima_security_reason",
            {
                **(state.get_sensor_attributes("heima_security_reason") or {}),
                "camera_breach_candidates": list(deduped),
            },
        )
        return deduped

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
                reason="anonymous_presence_on"
                if has_anonymous_evidence
                else "anonymous_presence_off",
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
        policy = str(
            notifications_cfg.get("security_mismatch_policy", DEFAULT_SECURITY_MISMATCH_POLICY)
        )
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
                notifications_cfg.get(
                    "security_mismatch_persist_s", DEFAULT_SECURITY_MISMATCH_PERSIST_S
                )
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

    @staticmethod
    def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            key = (
                str(candidate.get("rule") or ""),
                str(candidate.get("source_id") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(dict(candidate))
        return deduped
