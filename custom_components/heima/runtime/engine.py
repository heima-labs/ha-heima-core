"""Heima runtime engine — orchestrates domain handlers."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from ..const import (
    DEFAULT_LIGHTING_APPLY_MODE,
    DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
    DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S,
    DEFAULT_OCCUPANCY_MISMATCH_POLICY,
    OPT_CALENDAR,
    OPT_HEATING,
    OPT_HOUSE_SIGNALS,
    OPT_HOUSE_STATE_CONFIG,
    OPT_LIGHTING_APPLY_MODE,
    OPT_LIGHTING_ROOMS,
    OPT_LIGHTING_ZONES,
    OPT_NOTIFICATIONS,
    OPT_PEOPLE_ANON,
    OPT_PEOPLE_DEBUG_ALIASES,
    OPT_PEOPLE_NAMED,
    OPT_REACTIONS,
    OPT_ROOMS,
    OPT_SECURITY,
)
from ..entities.registry import build_registry
from ..models import HeimaOptions
from ..room_sources import room_all_source_entity_ids
from .analyzers.context_episode_sampling import canonicalize_context_snapshot
from .behaviors.base import HeimaBehavior
from .contracts import ApplyPlan, ApplyStep, HeimaEvent, ScriptApplyBatch
from .dag import resolve_dag
from .domain_result_bag import DomainResultBag
from .domains.calendar import CalendarDomain
from .domains.events import EventsDomain
from .domains.heating import HeatingDomain, HeatingDomainResult
from .domains.house_state import HouseStateDomain
from .domains.lighting import LightingDomain, LightingDomainResult
from .domains.occupancy import OccupancyDomain
from .domains.people import PeopleDomain
from .domains.security import SecurityDomain, SecurityDomainResult
from .domains.security_camera_evidence import (
    SecurityCameraEvidenceProvider,
    SecurityCameraEvidenceResult,
)
from .external_context import ExternalContext, ExternalContextNormalizer
from .invariant_check import InvariantCheckState, evaluate_invariant_state
from .invariants import (
    HeatingHomeEmpty,
    PresenceWithoutOccupancy,
    SecurityPresenceMismatch,
    SensorStuck,
)
from .normalization.service import InputNormalizer
from .plugin_contracts import IDomainPlugin, IInvariantCheck, InvariantViolation
from .reactions import (
    create_builtin_reaction_plugin_registry,
    normalize_reaction_options_payload,
    resolve_reaction_type,
)
from .reactions.base import HeimaReaction
from .scheduler import ScheduledRuntimeJob
from .snapshot import DecisionSnapshot
from .snapshot_buffer import SnapshotBuffer
from .state_store import CanonicalState

_LOGGER = logging.getLogger(__name__)

_LIGHTING_MIN_SECONDS_BETWEEN_APPLIES = 10


@dataclass(frozen=True)
class EngineHealth:
    """Health status for the runtime engine."""

    ok: bool
    reason: str


def _constraint_blocker(step: "ApplyStep", constraints: set[str]) -> str:
    """Return the constraint tag that blocks this step, or '' if none."""
    if "security.armed_away" in constraints:
        # Block lighting activations while armed away, regardless of whether they
        # come from the lighting domain pipeline or a direct scheduled routine.
        if step.action == "scene.turn_on":
            return "security.armed_away"
        if step.action == "light.turn_on":
            return "security.armed_away"
        if step.domain == "lighting" and step.action != "light.turn_off":
            return "security.armed_away"
    return ""


class HeimaEngine:
    """Core runtime engine with canonical compute pipeline."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._options = HeimaOptions.from_entry(entry)
        self._health = EngineHealth(ok=True, reason="initialized")
        self._snapshot = DecisionSnapshot.empty()
        self._state = CanonicalState()
        self._apply_plan = ApplyPlan.empty()
        self._last_engine_enabled_state: bool | None = None
        self._normalizer = InputNormalizer(hass)
        self._ext_ctx_normalizer = ExternalContextNormalizer(hass)
        self._ext_ctx_normalizer.update_config(dict(entry.options))
        self._external_context: ExternalContext = ExternalContext.empty()
        self._context_builder: Any = None
        self._events_domain = EventsDomain(hass)
        self._security_camera_evidence_provider = SecurityCameraEvidenceProvider(
            hass, self._normalizer
        )
        self._people_domain = PeopleDomain(hass, self._normalizer)
        self._occupancy_domain = OccupancyDomain(hass, self._normalizer)
        self._calendar_domain = CalendarDomain(hass)
        self._house_state_domain = HouseStateDomain(hass, self._normalizer)
        self._lighting_domain = LightingDomain(hass, self._normalizer)
        self._heating_domain = HeatingDomain(hass, self._normalizer)
        self._security_domain = SecurityDomain(hass, self._normalizer)
        self._current_security_camera_evidence: SecurityCameraEvidenceResult | None = None
        self._registered_domain_plugins: dict[str, IDomainPlugin] = {}
        self._domain_plugin_order: list[IDomainPlugin] = []
        self._domain_plugins_finalized = False
        self._invariant_checks: list[IInvariantCheck] = []
        self._invariant_states: dict[str, InvariantCheckState] = {}
        self._last_domain_results = DomainResultBag.empty()
        self._timed_rechecks: dict[str, dict[str, Any]] = {}
        self._last_config_issues_fingerprint: str | None = None
        self._active_constraints: set[str] = set()
        self._behaviors: list[HeimaBehavior] = []
        self._reactions: list[HeimaReaction] = []
        self._muted_reactions: set[str] = set()
        self._configured_reaction_ids: set[str] = set()
        self._snapshot_buffer = SnapshotBuffer()
        self._recent_script_applies: dict[str, ScriptApplyBatch] = {}
        self._reaction_plugin_registry = create_builtin_reaction_plugin_registry()
        self._bind_domain_plugin_runtime()

    @property
    def health(self) -> EngineHealth:
        return self._health

    @property
    def snapshot_history(self) -> list[DecisionSnapshot]:
        """Chronological list of recent snapshots (oldest first, newest last)."""
        return self._snapshot_buffer.history()

    @property
    def snapshot(self) -> DecisionSnapshot:
        return self._snapshot

    @property
    def state(self) -> CanonicalState:
        return self._state

    @property
    def lighting_last_apply_ts_by_room(self) -> dict[str, float]:
        """Wall-clock timestamps of the last Heima lighting apply per room_id.

        Used by LightingRecorderBehavior to distinguish Heima-applied changes
        from user-initiated light changes.
        """
        return self._lighting_domain.last_apply_ts_by_room

    @property
    def lighting_recent_apply_state(self) -> dict[str, Any]:
        """Recent lighting apply provenance for recorder attribution."""
        state = self._lighting_domain.recent_apply_state()
        state["scripts"] = {
            script_id: payload.as_dict()
            for script_id, payload in self._recent_script_applies.items()
        }
        return state

    def _infer_step_room_id(self, step: ApplyStep) -> str | None:
        """Best-effort room scope for a reaction-generated step."""
        reaction = self._reaction_from_step_source(step)
        if reaction is None:
            return None
        try:
            diagnostics = reaction.diagnostics()
        except Exception:
            return None
        room_id = diagnostics.get("room_id") if isinstance(diagnostics, dict) else None
        if isinstance(room_id, str) and room_id.strip():
            return room_id.strip()
        return None

    def _reaction_from_step_source(self, step: ApplyStep) -> HeimaReaction | None:
        """Return the originating reaction when a step source is reaction-tagged."""
        source = str(step.source or "").strip()
        if not source.startswith("reaction:"):
            return None
        reaction_id = source.split(":", 1)[1].strip()
        if not reaction_id:
            return None
        return next((item for item in self._reactions if item.reaction_id == reaction_id), None)

    def _reaction_type_for_reaction_id(self, reaction_id: str) -> str | None:
        provenance = self._configured_reaction_metadata(reaction_id)
        reaction_type = provenance.get("reaction_type")
        if isinstance(reaction_type, str) and reaction_type.strip():
            return reaction_type.strip()
        return None

    def signal_bucket(self, room_id: str, signal_name: str) -> str | None:
        """Return the current canonical bucket for a room signal when available."""
        for behavior in self._behaviors:
            bucket_for = getattr(behavior, "bucket_for", None)
            if callable(bucket_for):
                try:
                    bucket = bucket_for(room_id, signal_name)
                except Exception:
                    continue
                if isinstance(bucket, str) and bucket.strip():
                    return bucket.strip()
        return None

    def signal_burst_recent(self, room_id: str, signal_name: str, *, window_s: int) -> bool:
        """Return whether a canonical burst was observed recently for a room signal."""
        for behavior in self._behaviors:
            burst_recent_for = getattr(behavior, "burst_recent_for", None)
            if not callable(burst_recent_for):
                continue
            try:
                if bool(burst_recent_for(room_id, signal_name, window_s=window_s)):
                    return True
            except Exception:
                continue
        return False

    def room_occupancy_age_s(self, room_id: str) -> float | None:
        """Return effective occupancy age in seconds for a room when currently occupied."""
        trace = dict(self._occupancy_domain.room_trace).get(room_id)
        room_trace = dict(trace or {})
        if str(room_trace.get("effective_state") or "") != "on":
            return None
        effective_since = room_trace.get("effective_since")
        if not isinstance(effective_since, (int, float)):
            return None
        age = time.monotonic() - float(effective_since)
        return age if age >= 0 else 0.0

    async def async_initialize(self) -> None:
        _LOGGER.debug("Heima engine initialize")
        self._options = HeimaOptions.from_entry(self._entry)
        self._health = EngineHealth(ok=True, reason="initialized")
        self._rebuild_configured_reactions()
        self._build_default_state()
        for behavior in self._behaviors:
            try:
                await behavior.async_setup()
            except Exception:
                _LOGGER.exception("Behavior %s raised in async_setup", behavior.behavior_id)
        await self.async_evaluate(reason="initialize")

    async def async_shutdown(self) -> None:
        _LOGGER.debug("Heima engine shutdown")
        self._health = EngineHealth(ok=True, reason="shutdown")
        for behavior in self._behaviors:
            try:
                await behavior.async_teardown()
            except Exception:
                _LOGGER.exception("Behavior %s raised in async_teardown", behavior.behavior_id)

    async def async_reload_options(
        self,
        entry: ConfigEntry,
        *,
        changed_keys: set[str] | None = None,
    ) -> None:
        _LOGGER.debug("Heima engine reload options")
        self._entry = entry
        self._migrate_legacy_reaction_types()
        self._options = HeimaOptions.from_entry(entry)
        self._ext_ctx_normalizer.update_config(dict(entry.options))
        self._reset_domains_for_reload(changed_keys)
        self._recent_script_applies = {}
        self._last_config_issues_fingerprint = None
        options = dict(entry.options)
        for behavior in self._behaviors:
            try:
                behavior.on_options_reloaded(options)
            except Exception:
                _LOGGER.exception("Behavior %s raised in on_options_reloaded", behavior.behavior_id)
                self._queue_behavior_error_event(
                    component="behavior",
                    object_id=behavior.behavior_id,
                    hook="on_options_reloaded",
                    error="exception_raised",
                )
        for reaction in self._reactions:
            try:
                reaction.on_options_reloaded(options)
            except Exception:
                _LOGGER.exception("Reaction %s raised in on_options_reloaded", reaction.reaction_id)
                self._queue_behavior_error_event(
                    component="reaction",
                    object_id=reaction.reaction_id,
                    hook="on_options_reloaded",
                    error="exception_raised",
                )
        # Rebuild reactions from accepted proposals (may add/remove configured reactions)
        self._rebuild_configured_reactions()
        # Restore persisted mute state from options
        persisted_muted = set(options.get("reactions", {}).get("muted", []))
        known_ids = {r.reaction_id for r in self._reactions}
        self._muted_reactions = persisted_muted & known_ids
        if changed_keys is None:
            self._build_default_state()
        await self.async_evaluate(reason="options_reloaded")

    def _reset_domains_for_reload(self, changed_keys: set[str] | None) -> None:
        if changed_keys is None:
            self._security_camera_evidence_provider.reset()
            self._people_domain.reset()
            self._occupancy_domain.reset()
            self._calendar_domain.reset()
            self._house_state_domain.reset()
            self._lighting_domain.reset()
            self._heating_domain.reset()
            self._security_domain.reset()
            self._bind_domain_plugin_runtime()
            return

        changed = set(changed_keys)
        if OPT_PEOPLE_ANON in changed:
            self._people_domain.reset()
        if OPT_CALENDAR in changed:
            self._calendar_domain.reset()
        if changed & {OPT_HOUSE_SIGNALS, OPT_HOUSE_STATE_CONFIG, OPT_CALENDAR}:
            self._house_state_domain.reset()
        if changed & {OPT_LIGHTING_ROOMS, OPT_LIGHTING_APPLY_MODE}:
            self._lighting_domain.reset()
        if OPT_HEATING in changed:
            self._heating_domain.reset()
        if OPT_SECURITY in changed:
            self._security_camera_evidence_provider.reset()
            self._security_domain.reset()
        self._bind_domain_plugin_runtime()

    # ------------------------------------------------------------------
    # Behavior registration
    # ------------------------------------------------------------------

    def set_context_builder(self, context_builder: Any) -> None:
        """Wire the coordinator's ContextBuilder so ext_ctx is propagated each cycle."""
        self._context_builder = context_builder

    def register_behavior(self, behavior: HeimaBehavior) -> None:
        """Register a behavior. Call before first async_evaluate."""
        self._behaviors.append(behavior)
        _LOGGER.debug("Heima behavior registered: %s", behavior.behavior_id)

    def register_reaction(self, reaction: HeimaReaction) -> None:
        """Register a reactive behavior. Call before first async_evaluate."""
        self._reactions.append(reaction)
        _LOGGER.debug("Heima reaction registered: %s", reaction.reaction_id)

    def builtin_invariant_checks(self) -> list[IInvariantCheck]:
        """Return built-in invariant checks owned by this engine."""
        return [
            PresenceWithoutOccupancy(),
            SecurityPresenceMismatch(),
            HeatingHomeEmpty(),
            SensorStuck(),
        ]

    def register_invariant_check(self, check: IInvariantCheck) -> None:
        """Register a per-cycle invariant check."""
        if any(existing.check_id == check.check_id for existing in self._invariant_checks):
            raise ValueError(f"Duplicate invariant check id: {check.check_id}")
        self._invariant_checks.append(check)
        self._invariant_states.setdefault(check.check_id, InvariantCheckState())
        _LOGGER.debug("Heima invariant check registered: %s", check.check_id)

    def builtin_domain_plugins(self) -> list[IDomainPlugin]:
        """Return built-in domain plugins owned by this engine."""
        return [self._security_domain, self._lighting_domain, self._heating_domain]

    def register_plugin(self, plugin: IDomainPlugin) -> None:
        """Register a domain plugin before DAG finalization."""
        domain_id = plugin.domain_id
        existing = self._registered_domain_plugins.get(domain_id)
        if existing is plugin:
            return
        if self._domain_plugins_finalized:
            raise RuntimeError("Cannot register domain plugin after finalize_dag()")
        if existing is not None:
            raise ValueError(f"Duplicate domain plugin id: {domain_id}")
        self._registered_domain_plugins[domain_id] = plugin
        _LOGGER.debug("Heima domain plugin registered: %s", domain_id)

    def finalize_dag(self) -> None:
        """Resolve the domain plugin DAG once for this engine instance."""
        self._domain_plugin_order = resolve_dag(self._registered_domain_plugins.values())
        self._domain_plugins_finalized = True
        _LOGGER.debug(
            "Heima domain plugin DAG finalized: %s",
            [plugin.domain_id for plugin in self._domain_plugin_order],
        )

    def _ensure_domain_plugins_finalized(self) -> None:
        if self._domain_plugins_finalized:
            return
        for plugin in self.builtin_domain_plugins():
            self.register_plugin(plugin)
        self.finalize_dag()

    def _bind_domain_plugin_runtime(self) -> None:
        """Bind engine-owned providers used by built-in plugin wrappers."""
        self._lighting_domain.bind_plugin_runtime(
            options_provider=lambda: dict(self._entry.options),
            room_configs_provider=self._room_configs,
            room_occupancy_mode_fn=self._room_occupancy_mode,
        )
        self._heating_domain.bind_plugin_runtime(
            heating_config_provider=lambda: dict(dict(self._entry.options).get(OPT_HEATING, {})),
            events_provider=lambda: self._events_domain,
            schedule_recheck=self._schedule_timed_recheck_deadline,
            external_outdoor_temp_provider=lambda: self._external_context.outdoor_temp,
        )
        self._security_domain.bind_plugin_runtime(
            security_config_provider=lambda: dict(dict(self._entry.options).get(OPT_SECURITY, {})),
            options_provider=lambda: dict(self._entry.options),
            camera_evidence_provider=self._security_camera_evidence_for_plugins,
            events_provider=lambda: self._events_domain,
            schedule_recheck=self._schedule_timed_recheck_deadline,
            room_configs_provider=self._room_configs,
            room_occupancy_mode_fn=self._room_occupancy_mode,
            notifications_config_provider=self._notifications_config,
        )

    def _security_camera_evidence_for_plugins(self) -> SecurityCameraEvidenceResult:
        if self._current_security_camera_evidence is None:
            return self._security_camera_evidence_provider.compute({})
        return self._current_security_camera_evidence

    def reset_learning_state(self) -> None:
        """Reset runtime-local learning state without re-emitting bootstrap events."""
        self._snapshot_buffer.clear()
        for behavior in self._behaviors:
            try:
                behavior.reset_learning_state()
            except Exception:
                _LOGGER.exception(
                    "Behavior %s raised in reset_learning_state", behavior.behavior_id
                )
                self._queue_behavior_error_event(
                    component="behavior",
                    object_id=behavior.behavior_id,
                    hook="reset_learning_state",
                    error="exception_raised",
                )
        for reaction in self._reactions:
            try:
                reaction.reset_learning_state()
            except Exception:
                _LOGGER.exception(
                    "Reaction %s raised in reset_learning_state", reaction.reaction_id
                )
                self._queue_behavior_error_event(
                    component="reaction",
                    object_id=reaction.reaction_id,
                    hook="reset_learning_state",
                    error="exception_raised",
                )
        self._sync_reactions_sensor()

    def mute_reaction(self, reaction_id: str) -> bool:
        """Mute a reaction by ID. Returns True if the reaction exists."""
        exists = any(r.reaction_id == reaction_id for r in self._reactions)
        if exists:
            self._muted_reactions.add(reaction_id)
            self._sync_reactions_sensor()
        return exists

    def unmute_reaction(self, reaction_id: str) -> bool:
        """Unmute a reaction by ID. Returns True if the reaction exists."""
        exists = any(r.reaction_id == reaction_id for r in self._reactions)
        if exists:
            self._muted_reactions.discard(reaction_id)
            self._sync_reactions_sensor()
        return exists

    def mute_reactions_by_type(self, reaction_type: str) -> list[str]:
        """Mute all configured reactions matching a reaction_type."""
        target = str(reaction_type or "").strip()
        if not target:
            return []
        matched = self._configured_reaction_ids_by_type(target)
        if not matched:
            return []
        self._muted_reactions.update(matched)
        self._sync_reactions_sensor()
        return matched

    def unmute_reactions_by_type(self, reaction_type: str) -> list[str]:
        """Unmute all configured reactions matching a reaction_type."""
        target = str(reaction_type or "").strip()
        if not target:
            return []
        matched = self._configured_reaction_ids_by_type(target)
        if not matched:
            return []
        for reaction_id in matched:
            self._muted_reactions.discard(reaction_id)
        self._sync_reactions_sensor()
        return matched

    def _configured_reaction_ids_by_type(self, reaction_type: str) -> list[str]:
        configured = dict(dict(self._entry.options).get(OPT_REACTIONS, {}).get("configured", {}))
        known_ids = {reaction.reaction_id for reaction in self._reactions}
        matched: list[str] = []
        for reaction_id, cfg in configured.items():
            if reaction_id not in known_ids or not isinstance(cfg, dict):
                continue
            value = self._reaction_type_from_config(cfg)
            if value == reaction_type:
                matched.append(str(reaction_id))
        return sorted(matched)

    def _rebuild_configured_reactions(self) -> None:
        """Instantiate reactions from accepted proposals stored in options."""
        # Remove previously configured reactions
        self._reactions = [
            r for r in self._reactions if r.reaction_id not in self._configured_reaction_ids
        ]
        self._configured_reaction_ids = set()

        configured: dict = dict(self._entry.options).get(OPT_REACTIONS, {}).get("configured", {})
        for proposal_id, cfg in configured.items():
            if not bool(dict(cfg or {}).get("enabled", True)):
                continue
            reaction_type = self._reaction_type_from_config(cfg)
            builder = self._reaction_plugin_registry.builder_for(reaction_type)
            if builder is None:
                _LOGGER.debug(
                    "Skipping configured reaction with unknown type %r (proposal %s)",
                    reaction_type,
                    proposal_id,
                )
                continue
            normalized_cfg = dict(cfg)
            if reaction_type:
                normalized_cfg["reaction_type"] = reaction_type
            normalized_cfg.pop("reaction_class", None)
            reaction = builder(self, proposal_id, normalized_cfg)
            if reaction is not None:
                self._reactions.append(reaction)
                self._configured_reaction_ids.add(reaction.reaction_id)
            else:
                _LOGGER.warning(
                    "Malformed %s config for proposal %s",
                    reaction_type or "<unknown>",
                    proposal_id,
                )

    @staticmethod
    def _reaction_type_from_config(cfg: dict[str, Any]) -> str:
        return resolve_reaction_type(cfg)

    def _migrate_legacy_reaction_types(self) -> None:
        options = dict(getattr(self._entry, "options", {}) or {})
        normalized_options, changed = normalize_reaction_options_payload(options)
        if not changed:
            return
        setattr(self._entry, "options", normalized_options)

    def set_house_state_override(
        self,
        *,
        mode: str,
        enabled: bool,
        source: str,
    ) -> tuple[str, str | None, str | None]:
        return self._house_state_domain.set_override(mode=mode, enabled=enabled, source=source)

    async def async_evaluate(self, reason: str) -> DecisionSnapshot:
        """Evaluate canonical state from configured bindings."""
        _LOGGER.debug("Heima evaluation requested: %s", reason)
        calendar_cfg = dict(self._entry.options.get(OPT_CALENDAR, {}))
        await self._calendar_domain.async_maybe_refresh(calendar_cfg)
        snapshot = self._compute_snapshot(reason=reason)
        self._snapshot = snapshot
        self._snapshot_buffer.push(snapshot)
        self._apply_snapshot_to_canonical_state(snapshot)
        self._dispatch_on_snapshot(snapshot)
        self._run_invariant_checks(snapshot)

        plan = self._build_apply_plan(snapshot)
        plan = self._dispatch_apply_filter(plan, snapshot)
        self._apply_plan = plan
        self._sync_reactions_sensor()
        await self._emit_lighting_hold_events()
        await self._emit_queued_events()

        if (
            self._last_engine_enabled_state is None
            or self._last_engine_enabled_state != self._options.engine_enabled
        ):
            if not self._options.engine_enabled:
                await self._emit_event_obj(
                    HeimaEvent(
                        type="system.engine_disabled",
                        key="system.engine_disabled",
                        severity="info",
                        title="Heima engine disabled",
                        message="Heima engine apply phases are disabled; canonical state continues updating.",
                        context={"reason": "engine_enabled_false"},
                    )
                )
                self._sync_event_sensors()
            self._last_engine_enabled_state = self._options.engine_enabled

        if self._options.engine_enabled and self._lighting_apply_mode() == "scene":
            await self._execute_apply_plan(plan)

        return snapshot

    async def async_emit_external_event(
        self,
        *,
        event_type: str,
        key: str,
        severity: str,
        title: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Emit an external/runtime event through the unified event pipeline."""
        emitted = await self._emit_event_obj(
            HeimaEvent(
                type=event_type,
                key=key,
                severity=severity,
                title=title,
                message=message,
                context=dict(context or {}),
            )
        )
        self._sync_event_sensors()
        return emitted

    def tracked_entity_ids(self) -> set[str]:
        """Entities that should trigger recomputation on state change."""
        options = dict(self._entry.options)
        tracked: set[str] = set(self._configured_house_signal_entities().values())

        for person in options.get(OPT_PEOPLE_NAMED, []):
            entity = person.get("person_entity")
            if entity:
                tracked.add(str(entity))
            for source in person.get("sources", []):
                tracked.add(str(source))

        debug_aliases_cfg = options.get(OPT_PEOPLE_DEBUG_ALIASES, {})
        if isinstance(debug_aliases_cfg, dict) and debug_aliases_cfg.get("enabled"):
            aliases = debug_aliases_cfg.get("aliases", {})
            if isinstance(aliases, dict):
                for raw in aliases.values():
                    if not isinstance(raw, dict):
                        continue
                    entity = raw.get("person_entity")
                    if entity:
                        tracked.add(str(entity))

        anon = options.get(OPT_PEOPLE_ANON, {})
        for source in anon.get("sources", []):
            tracked.add(str(source))

        for room in options.get(OPT_ROOMS, []):
            for source in room_all_source_entity_ids(room):
                tracked.add(str(source))

        security = options.get(OPT_SECURITY, {})
        security_entity = security.get("security_state_entity")
        if security_entity:
            tracked.add(str(security_entity))
        for source in security.get("camera_evidence_sources", []) or []:
            if not isinstance(source, dict):
                continue
            for key in ("motion_entity", "person_entity", "vehicle_entity", "contact_entity"):
                value = source.get(key)
                if value:
                    tracked.add(str(value))

        heating = options.get(OPT_HEATING, {})
        for key in (
            "climate_entity",
            "outdoor_temperature_entity",
            "vacation_hours_from_start_entity",
            "vacation_hours_to_end_entity",
            "vacation_total_hours_entity",
            "vacation_is_long_entity",
        ):
            value = heating.get(key)
            if value:
                tracked.add(str(value))

        return tracked

    def _configured_house_signal_entities(self) -> dict[str, str]:
        raw = self._entry.options.get(OPT_HOUSE_SIGNALS, {})
        if not isinstance(raw, dict):
            return {}
        configured: dict[str, str] = {}
        for signal_name in (
            "vacation_mode",
            "guest_mode",
            "sleep_window",
            "relax_mode",
            "work_window",
        ):
            value = raw.get(signal_name)
            if value in (None, ""):
                continue
            entity_id = str(value).strip()
            if entity_id:
                configured[signal_name] = entity_id
        return configured

    def _build_default_state(self) -> None:
        registry = build_registry(self._entry)
        self._state.binary_sensors = {desc.key: False for desc in registry.binary_sensors}
        self._state.sensors = {desc.key: None for desc in registry.sensors}
        self._state.sensor_attributes = {}
        self._state.selects = {
            desc.key: self._state.selects.get(desc.key, desc.options[0])
            for desc in registry.selects
        }

        if "heima_people_count" in self._state.sensors:
            self._state.sensors["heima_people_count"] = 0
        if "heima_people_home_list" in self._state.sensors:
            self._state.sensors["heima_people_home_list"] = ""
        if "heima_house_state" in self._state.sensors:
            self._state.sensors["heima_house_state"] = "unknown"
        if "heima_house_state_reason" in self._state.sensors:
            self._state.sensors["heima_house_state_reason"] = ""
        if "heima_last_event" in self._state.sensors:
            self._state.sensors["heima_last_event"] = ""
        if "heima_event_stats" in self._state.sensors:
            self._state.sensors["heima_event_stats"] = "{}"
        if "heima_reactions_active" in self._state.sensors:
            self._state.sensors["heima_reactions_active"] = 0
            self._state.set_sensor_attributes(
                "heima_reactions_active",
                {"reactions": {}, "total": 0, "muted_total": 0},
            )
        if "heima_reaction_proposals" in self._state.sensors:
            self._state.sensors["heima_reaction_proposals"] = 0
        if "heima_heating_state" in self._state.sensors:
            self._state.sensors["heima_heating_state"] = "idle"
        if "heima_heating_reason" in self._state.sensors:
            self._state.sensors["heima_heating_reason"] = "not_configured"
        if "heima_heating_phase" in self._state.sensors:
            self._state.sensors["heima_heating_phase"] = "normal"
        if "heima_heating_branch" in self._state.sensors:
            self._state.sensors["heima_heating_branch"] = "disabled"
        if "heima_heating_target_temp" in self._state.sensors:
            self._state.sensors["heima_heating_target_temp"] = None
        if "heima_heating_current_setpoint" in self._state.sensors:
            self._state.sensors["heima_heating_current_setpoint"] = None
        if "heima_heating_last_applied_target" in self._state.sensors:
            self._state.sensors["heima_heating_last_applied_target"] = None

    def _compute_snapshot(self, reason: str) -> DecisionSnapshot:
        options = dict(self._entry.options)
        now = datetime.now(timezone.utc).isoformat()
        self._timed_rechecks = {}

        self._external_context = self._ext_ctx_normalizer.compute()
        if self._context_builder is not None:
            self._context_builder.update_ext_ctx(self._external_context)

        security_cfg = dict(options.get(OPT_SECURITY, {}))
        security_camera_evidence = self._security_camera_evidence_provider.compute(security_cfg)
        self._current_security_camera_evidence = security_camera_evidence

        self._people_domain._normalizer = self._normalizer  # keep in sync if tests swap normalizer
        people_result = self._people_domain.compute(
            options,
            self._state,
            self._events_domain,
            camera_evidence=security_camera_evidence,
        )
        anyone_home = people_result.anyone_home
        people_count = people_result.people_count
        people_home_list = people_result.people_home_list

        self._occupancy_domain._normalizer = self._normalizer  # keep in sync
        occ_result = self._occupancy_domain.compute(
            options=options,
            events=self._events_domain,
            mismatch_cfg=self._occupancy_mismatch_config(),
            schedule_recheck=self._schedule_timed_recheck_deadline,
            state=self._state,
            now=now,
        )
        occupied_rooms = occ_result.occupied_rooms

        calendar_cfg = dict(options.get(OPT_CALENDAR, {}))
        calendar_result = self._calendar_domain.compute(calendar_cfg)
        self._state.calendar_result = calendar_result

        self._house_state_domain._normalizer = self._normalizer  # keep in sync
        house_signal_entities = self._configured_house_signal_entities()
        hs_result = self._house_state_domain.compute(
            options=options,
            house_signal_entities=house_signal_entities,
            anyone_home=anyone_home,
            events=self._events_domain,
            state=self._state,
            calendar_result=calendar_result,
            schedule_recheck=self._schedule_timed_recheck_deadline,
        )
        house_state = hs_result.house_state
        house_reason = hs_result.house_reason

        domain_results = (
            DomainResultBag.empty()
            .with_result("people", people_result)
            .with_result("occupancy", occ_result)
            .with_result("calendar", calendar_result)
            .with_result("house_state", hs_result)
        )
        domain_results = self._compute_domain_plugins(domain_results)
        self._last_domain_results = domain_results

        lighting_result = domain_results.require("lighting")
        heating_result = domain_results.require("heating")
        security_result = domain_results.require("security")
        if not isinstance(lighting_result, LightingDomainResult):
            raise RuntimeError("Lighting plugin returned an invalid result")
        if not isinstance(heating_result, HeatingDomainResult):
            raise RuntimeError("Heating plugin returned an invalid result")
        if not isinstance(security_result, SecurityDomainResult):
            raise RuntimeError("Security plugin returned an invalid result")

        lighting_intents = lighting_result.lighting_intents
        security_state = security_result.security_state
        security_reason = security_result.security_reason

        self._state.set_binary("heima_anyone_home", anyone_home)
        self._state.set_sensor("heima_people_count", people_count)
        self._state.set_sensor("heima_people_home_list", ",".join(people_home_list))
        prev_house_state = self._state.get_sensor("heima_house_state")
        house_state_diag = self._house_state_domain.diagnostics()
        resolution_trace = dict(house_state_diag.get("resolution_trace", {}))
        candidate_summary = dict(house_state_diag.get("candidate_summary", {}))
        pending_candidate = str(resolution_trace.get("decision", {}).get("source_candidate") or "")
        pending_remaining = resolution_trace.get("decision", {}).get("pending_remaining_s")
        active_candidates = list(resolution_trace.get("active_candidates", []) or [])
        self._state.set_sensor("heima_house_state", house_state)
        self._state.set_sensor("heima_house_state_reason", house_reason)
        self._state.set_sensor(
            "heima_house_state_path", resolution_trace.get("resolution_path") or ""
        )
        self._state.set_sensor("heima_house_state_active_candidates", ",".join(active_candidates))
        self._state.set_sensor(
            "heima_house_state_pending_candidate",
            pending_candidate
            if resolution_trace.get("decision", {}).get("action") == "pending"
            else "",
        )
        self._state.set_sensor(
            "heima_house_state_pending_remaining_s",
            round(float(pending_remaining), 3)
            if resolution_trace.get("decision", {}).get("action") == "pending"
            and pending_remaining is not None
            else None,
        )
        self._state.set_sensor_attributes(
            "heima_house_state",
            {
                "resolution_trace": resolution_trace,
                "candidate_summary": candidate_summary,
            },
        )
        self._state.set_sensor_attributes(
            "heima_house_state_reason",
            {
                "resolution_trace": resolution_trace,
                "candidate_summary": candidate_summary,
            },
        )
        self._queue_house_state_changed_event(
            previous=str(prev_house_state) if prev_house_state not in (None, "") else None,
            current=house_state,
            reason=house_reason,
        )

        if security_reason == "disabled" and "heima_security_reason" in self._state.sensors:
            self._state.set_sensor("heima_security_reason", security_reason)

        self._occupancy_domain.queue_occupancy_consistency_events(
            anyone_home=anyone_home,
            occupied_rooms=occupied_rooms,
            options=options,
            mismatch_cfg=self._occupancy_mismatch_config(),
            schedule_recheck=self._schedule_timed_recheck_deadline,
            events=self._events_domain,
        )

        self._check_and_queue_config_issues(options)

        return DecisionSnapshot(
            snapshot_id=str(uuid4()),
            ts=now,
            house_state=house_state,
            anyone_home=anyone_home,
            people_count=people_count,
            occupied_rooms=occupied_rooms,
            lighting_intents=lighting_intents,
            security_state=security_state,
            context_signals=self._current_context_signals(options),
            notes=f"reason={reason}",
            heating_setpoint=heating_result.current_setpoint,
            heating_source=heating_result.observed_source,
            heating_provenance=heating_result.observed_provenance,
        )

    def _compute_domain_plugins(self, domain_results: DomainResultBag) -> DomainResultBag:
        self._ensure_domain_plugins_finalized()
        results = domain_results
        for plugin in self._domain_plugin_order:
            plugin_result = plugin.compute(self._state, results, signals=None)
            results = results.with_result(plugin.domain_id, plugin_result)
        return results

    def _run_invariant_checks(self, snapshot: DecisionSnapshot) -> None:
        if not self._invariant_config()["enabled"]:
            return
        for check in self._invariant_checks:
            violation = check.check(snapshot, self._last_domain_results)
            state = self._invariant_states.setdefault(check.check_id, InvariantCheckState())
            outcome = evaluate_invariant_state(
                state=state,
                violation=violation,
                debounce_s=self._invariant_debounce_s(check),
                re_emit_interval_s=self._invariant_config()["re_emit_interval_s"],
            )
            if outcome.violation is not None:
                self._queue_invariant_violation_event(outcome.violation)
            elif outcome.resolved:
                self._queue_invariant_resolved_event(check.check_id)

    def _invariant_config(self) -> dict[str, Any]:
        options = dict(self._entry.options)
        anomaly_cfg = options.get("anomaly", {})
        if not isinstance(anomaly_cfg, dict):
            anomaly_cfg = {}
        return {
            "enabled": bool(
                anomaly_cfg.get("anomaly_enabled", options.get("anomaly_enabled", True))
            ),
            "sensor_stuck_threshold_s": int(
                anomaly_cfg.get(
                    "anomaly_sensor_stuck_threshold_s",
                    options.get("anomaly_sensor_stuck_threshold_s", 86400),
                )
            ),
            "heating_empty_threshold_s": int(
                anomaly_cfg.get(
                    "anomaly_heating_empty_threshold_s",
                    options.get("anomaly_heating_empty_threshold_s", 1800),
                )
            ),
            "notify_on_info": bool(
                anomaly_cfg.get(
                    "anomaly_notify_on_info",
                    options.get("anomaly_notify_on_info", False),
                )
            ),
            "re_emit_interval_s": int(
                anomaly_cfg.get(
                    "anomaly_re_emit_interval_s",
                    options.get("anomaly_re_emit_interval_s", 3600),
                )
            ),
        }

    def _invariant_debounce_s(self, check: IInvariantCheck) -> float:
        cfg = self._invariant_config()
        if check.check_id == "sensor_stuck":
            return float(cfg["sensor_stuck_threshold_s"])
        if check.check_id == "heating_home_empty":
            return float(cfg["heating_empty_threshold_s"])
        return float(check.default_debounce_s)

    def _queue_invariant_violation_event(self, violation: InvariantViolation) -> None:
        cfg = self._invariant_config()
        context = {
            "check_id": violation.check_id,
            "anomaly_type": violation.anomaly_type,
            "notify": bool(violation.severity != "info" or cfg["notify_on_info"]),
            **dict(violation.context),
        }
        self._events_domain.queue_event(
            HeimaEvent(
                type=f"anomaly.{violation.anomaly_type}",
                key=f"anomaly.{violation.check_id}",
                severity=violation.severity,
                title="Invariant violation",
                message=violation.description,
                context=context,
            )
        )

    def _queue_invariant_resolved_event(self, check_id: str) -> None:
        self._events_domain.queue_event(
            HeimaEvent(
                type="anomaly.resolved",
                key=f"anomaly.resolved.{check_id}",
                severity="info",
                title="Invariant resolved",
                message=f"Invariant '{check_id}' is no longer active.",
                context={"check_id": check_id},
            )
        )

    def scheduled_runtime_jobs(self) -> dict[str, ScheduledRuntimeJob]:
        jobs: dict[str, ScheduledRuntimeJob] = {}
        entry_id = str(getattr(self._entry, "entry_id", ""))
        for job_id, spec in self._timed_rechecks.items():
            jobs[job_id] = ScheduledRuntimeJob(
                job_id=job_id,
                owner=str(spec.get("owner", "runtime")),
                entry_id=entry_id,
                due_monotonic=float(spec["due_monotonic"]),
                label=str(spec.get("label", job_id)),
            )
        for reaction in self._reactions:
            try:
                jobs.update(reaction.scheduled_jobs(entry_id))
            except Exception:
                _LOGGER.exception("Reaction %s raised in scheduled_jobs", reaction.reaction_id)
        return jobs

    def next_dwell_recheck_delay_s(self) -> float | None:
        """Return seconds until the earliest scheduled runtime recheck.

        Kept as a thin compatibility helper while tests and callers migrate to
        the explicit scheduler model.
        """
        jobs = self.scheduled_runtime_jobs()
        if not jobs:
            return None
        next_due = min(job.due_monotonic for job in jobs.values())
        return max(0.0, next_due - time.monotonic())

    def _schedule_timed_recheck_deadline(
        self,
        *,
        job_id: str,
        deadline: float,
        owner: str,
        label: str,
    ) -> None:
        current = self._timed_rechecks.get(job_id)
        if current is not None and float(current["due_monotonic"]) <= deadline:
            return
        self._timed_rechecks[job_id] = {
            "owner": owner,
            "label": label,
            "due_monotonic": deadline,
        }

    def _compute_lighting_intents(
        self, house_state: str, occupied_rooms: list[str]
    ) -> dict[str, str]:
        options = dict(self._entry.options)
        room_configs = self._room_configs()
        return self._lighting_domain.compute_intents(
            options=options,
            house_state=house_state,
            occupied_rooms=occupied_rooms,
            state=self._state,
            room_configs=room_configs,
            room_occupancy_mode_fn=self._room_occupancy_mode,
        )

    def _build_apply_plan(self, snapshot: DecisionSnapshot) -> ApplyPlan:
        options = dict(self._entry.options)
        room_maps = self._lighting_room_maps()
        room_configs = self._room_configs()

        # Compute active constraints from security state
        self._active_constraints = self._compute_active_constraints(snapshot.security_state)

        # Lighting steps via LightingDomain
        lighting_steps = self._lighting_domain.build_lighting_steps(
            snapshot=snapshot,
            options=options,
            room_maps=room_maps,
            room_configs=room_configs,
            room_occupancy_mode_fn=self._room_occupancy_mode,
            zone_rooms_fn=self._zone_rooms,
            state=self._state,
            events=self._events_domain,
        )

        steps: list[ApplyStep] = list(lighting_steps)

        # Heating step
        heating_trace = dict(self._heating_domain.trace)
        if heating_trace.get("configured") and heating_trace.get("apply_allowed"):
            climate_entity = str(heating_trace.get("climate_entity", "")).strip()
            target_temperature = heating_trace.get("target_temperature")
            if climate_entity and isinstance(target_temperature, (int, float)):
                heating_params: dict[str, Any] = {
                    "entity_id": climate_entity,
                    "temperature": float(target_temperature),
                }
                hvac_mode_override = heating_trace.get("hvac_mode_override")
                if hvac_mode_override:
                    heating_params["hvac_mode"] = hvac_mode_override
                steps.append(
                    ApplyStep(
                        domain="heating",
                        target=climate_entity,
                        action="climate.set_temperature",
                        params=heating_params,
                        reason=f"branch:{heating_trace.get('selected_branch', 'disabled')}",
                    )
                )

        # Merge reaction-generated steps (tagged with source)
        reaction_steps = self._dispatch_reactions(self._snapshot_buffer.history())
        steps.extend(reaction_steps)

        return ApplyPlan(steps=self._apply_filter(steps, self._active_constraints))

    @staticmethod
    def _compute_active_constraints(security_state: str) -> set[str]:
        constraints: set[str] = set()
        if security_state == "armed_away":
            constraints.add("security.armed_away")
        return constraints

    @staticmethod
    def _apply_filter(steps: list[ApplyStep], constraints: set[str]) -> list[ApplyStep]:
        """Mark steps as blocked based on active constraints. Blocked steps are kept for diagnostics."""
        if not constraints:
            return steps
        filtered: list[ApplyStep] = []
        for step in steps:
            blocker = _constraint_blocker(step, constraints)
            if blocker:
                filtered.append(dataclass_replace(step, blocked_by=blocker))
            else:
                filtered.append(step)
        return filtered

    def _dispatch_on_snapshot(self, snapshot: DecisionSnapshot) -> None:
        for behavior in self._behaviors:
            try:
                behavior.on_snapshot(snapshot)
            except Exception:
                _LOGGER.exception("Behavior %s raised in on_snapshot", behavior.behavior_id)
                self._queue_behavior_error_event(
                    component="behavior",
                    object_id=behavior.behavior_id,
                    hook="on_snapshot",
                    error="exception_raised",
                )

    def _dispatch_reactions(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        """Call each registered reaction and collect their steps. Exceptions are isolated."""
        result: list[ApplyStep] = []
        for reaction in self._reactions:
            rid = reaction.reaction_id
            if rid in self._muted_reactions:
                continue
            try:
                steps = reaction.evaluate(history)
                tagged = [dataclass_replace(step, source=f"reaction:{rid}") for step in steps]
                result.extend(tagged)
                if tagged:
                    self._events_domain.queue_event(
                        HeimaEvent(
                            type="reaction.fired",
                            key=f"reaction.fired.{rid}",
                            severity="info",
                            title=f"Reaction fired: {rid}",
                            message=f"Reaction '{rid}' injected {len(tagged)} step(s).",
                            context={"reaction_id": rid, "step_count": len(tagged)},
                        )
                    )
            except Exception:
                _LOGGER.exception("Reaction %s raised in evaluate", rid)
                self._queue_behavior_error_event(
                    component="reaction",
                    object_id=rid,
                    hook="evaluate",
                    error="exception_raised",
                )
        return result

    def _dispatch_apply_filter(self, plan: ApplyPlan, snapshot: DecisionSnapshot) -> ApplyPlan:
        for behavior in self._behaviors:
            try:
                plan = behavior.apply_filter(plan, snapshot)
            except Exception:
                _LOGGER.exception("Behavior %s raised in apply_filter", behavior.behavior_id)
                self._queue_behavior_error_event(
                    component="behavior",
                    object_id=behavior.behavior_id,
                    hook="apply_filter",
                    error="exception_raised",
                )
        return plan

    def _queue_behavior_error_event(
        self,
        *,
        component: str,
        object_id: str,
        hook: str,
        error: str,
    ) -> None:
        """Emit a stable runtime error event for behavior/reaction hook failures."""
        self._events_domain.queue_event(
            HeimaEvent(
                type="system.behavior_error",
                key=f"system.behavior_error.{component}.{object_id}.{hook}",
                severity="warn",
                title="Behavior hook error",
                message=(f"{component.title()} '{object_id}' raised in hook '{hook}'."),
                context={
                    "component": component,
                    "behavior": object_id,
                    "hook": hook,
                    "error": error,
                },
            )
        )

    async def _execute_apply_plan(self, plan: ApplyPlan) -> None:
        lighting_steps = [s for s in plan.steps if s.domain == "lighting" and not s.blocked_by]
        heating_steps = [s for s in plan.steps if s.domain == "heating" and not s.blocked_by]
        script_steps = [s for s in plan.steps if s.domain == "script" and not s.blocked_by]
        scene_steps = [s for s in plan.steps if s.domain == "scene" and not s.blocked_by]
        light_steps = [s for s in plan.steps if s.domain == "light" and not s.blocked_by]
        switch_steps = [s for s in plan.steps if s.domain == "switch" and not s.blocked_by]
        input_boolean_steps = [
            s for s in plan.steps if s.domain == "input_boolean" and not s.blocked_by
        ]

        await self._lighting_domain.execute_lighting_steps(lighting_steps)

        for step in scene_steps:
            if step.action != "scene.turn_on":
                continue
            scene_entity = step.params.get("entity_id")
            if not isinstance(scene_entity, str) or not scene_entity.startswith("scene."):
                continue
            if self._hass.states.get(scene_entity) is None:
                _LOGGER.warning("Skipping missing scene entity: %s", scene_entity)
                continue
            try:
                await self._hass.services.async_call(
                    "scene",
                    "turn_on",
                    {"entity_id": scene_entity},
                    blocking=False,
                )
            except ServiceNotFound:
                _LOGGER.warning(
                    "Skipping scene apply during startup/race: service scene.turn_on not available"
                )
            except Exception:
                _LOGGER.exception("Scene apply failed for '%s'", scene_entity)

        for step in light_steps:
            if step.action not in {"light.turn_on", "light.turn_off"}:
                continue
            light_entity = step.params.get("entity_id")
            if not isinstance(light_entity, str) or not light_entity.startswith("light."):
                continue
            if self._hass.states.get(light_entity) is None:
                _LOGGER.warning("Skipping missing light entity: %s", light_entity)
                continue
            try:
                call_params = {"entity_id": light_entity}
                if step.action == "light.turn_on":
                    if step.params.get("brightness") is not None:
                        call_params["brightness"] = step.params["brightness"]
                    if step.params.get("rgb_color") is not None:
                        call_params["rgb_color"] = step.params["rgb_color"]
                    elif step.params.get("color_temp_kelvin") is not None:
                        call_params["color_temp_kelvin"] = step.params["color_temp_kelvin"]
                await self._hass.services.async_call(
                    "light",
                    step.action.split(".", 1)[1],
                    call_params,
                    blocking=False,
                )
            except ServiceNotFound:
                _LOGGER.warning(
                    "Skipping light apply during startup/race: service %s not available",
                    step.action,
                )
            except Exception:
                _LOGGER.exception("Light apply failed for '%s'", light_entity)

        for step in heating_steps:
            if step.action == "climate.set_temperature":
                climate_entity = step.params.get("entity_id")
                if not isinstance(climate_entity, str) or not climate_entity.startswith("climate."):
                    continue
                if self._hass.states.get(climate_entity) is None:
                    _LOGGER.warning("Skipping missing climate entity: %s", climate_entity)
                    continue
                try:
                    reaction = self._reaction_from_step_source(step)
                    await self._hass.services.async_call(
                        "climate",
                        "set_temperature",
                        dict(step.params),
                        blocking=False,
                    )
                    applied_temp = (
                        float(step.params["temperature"])
                        if isinstance(step.params.get("temperature"), (int, float))
                        else None
                    )
                    if applied_temp is not None:
                        self._heating_domain.mark_applied(
                            applied_temp,
                            source=step.source,
                            origin_reaction_id=(
                                reaction.reaction_id if reaction is not None else None
                            ),
                            origin_reaction_type=(
                                self._reaction_type_for_reaction_id(reaction.reaction_id)
                                if reaction is not None
                                else None
                            ),
                            climate_entity=climate_entity,
                        )
                    self._state.set_sensor("heima_heating_last_applied_target", applied_temp)
                except ServiceNotFound:
                    _LOGGER.warning(
                        "Skipping heating apply during startup/race: service climate.set_temperature not available"
                    )
                except Exception:
                    _LOGGER.exception("Heating apply failed for climate '%s'", climate_entity)

        for step in script_steps:
            if step.action != "script.turn_on":
                continue
            script_entity = step.params.get("entity_id")
            if not isinstance(script_entity, str) or not script_entity.startswith("script."):
                continue
            if self._hass.states.get(script_entity) is None:
                _LOGGER.warning("Skipping missing script entity: %s", script_entity)
                continue
            try:
                room_id = self._infer_step_room_id(step)
                reaction = self._reaction_from_step_source(step)
                await self._hass.services.async_call(
                    "script",
                    "turn_on",
                    {"entity_id": script_entity},
                    blocking=False,
                )
                expected_subject_ids = (
                    tuple(self._lighting_domain.expected_room_light_entities(room_id))
                    if room_id
                    else ()
                )
                self._recent_script_applies[script_entity] = ScriptApplyBatch(
                    script_entity=script_entity,
                    room_id=room_id,
                    expected_domains=tuple(
                        sorted(
                            {
                                entity_id.split(".", 1)[0]
                                for entity_id in expected_subject_ids
                                if "." in entity_id
                            }
                        )
                    ),
                    expected_subject_ids=expected_subject_ids,
                    expected_entity_ids=expected_subject_ids,
                    applied_ts=time.monotonic(),
                    correlation_id=f"script-apply:{uuid4()}",
                    source=step.source,
                    origin_reaction_id=(reaction.reaction_id if reaction is not None else None),
                    origin_reaction_type=(
                        self._reaction_type_for_reaction_id(reaction.reaction_id)
                        if reaction is not None
                        else None
                    ),
                )
            except ServiceNotFound:
                _LOGGER.warning(
                    "Skipping script apply during startup/race: service script.turn_on not available"
                )
            except Exception:
                _LOGGER.exception("Script apply failed for '%s'", script_entity)

        for step in switch_steps:
            if step.action not in {"switch.turn_on", "switch.turn_off"}:
                continue
            switch_entity = step.params.get("entity_id")
            if not isinstance(switch_entity, str) or not switch_entity.startswith("switch."):
                continue
            if self._hass.states.get(switch_entity) is None:
                _LOGGER.warning("Skipping missing switch entity: %s", switch_entity)
                continue
            try:
                await self._hass.services.async_call(
                    "switch",
                    step.action.split(".", 1)[1],
                    {"entity_id": switch_entity},
                    blocking=False,
                )
            except ServiceNotFound:
                _LOGGER.warning(
                    "Skipping switch apply during startup/race: service %s not available",
                    step.action,
                )
            except Exception:
                _LOGGER.exception("Switch apply failed for '%s'", switch_entity)

        for step in input_boolean_steps:
            if step.action not in {"input_boolean.turn_on", "input_boolean.turn_off"}:
                continue
            helper_entity = step.params.get("entity_id")
            if not isinstance(helper_entity, str) or not helper_entity.startswith("input_boolean."):
                continue
            if self._hass.states.get(helper_entity) is None:
                _LOGGER.warning("Skipping missing input_boolean entity: %s", helper_entity)
                continue
            try:
                await self._hass.services.async_call(
                    "input_boolean",
                    step.action.split(".", 1)[1],
                    {"entity_id": helper_entity},
                    blocking=False,
                )
            except ServiceNotFound:
                _LOGGER.warning(
                    "Skipping input_boolean apply during startup/race: service %s not available",
                    step.action,
                )
            except Exception:
                _LOGGER.exception("Input_boolean apply failed for '%s'", helper_entity)

    def _lighting_room_maps(self) -> dict[str, dict[str, Any]]:
        options = dict(self._entry.options)
        mappings: dict[str, dict[str, Any]] = {}
        for room_map in options.get(OPT_LIGHTING_ROOMS, []):
            room_id = room_map.get("room_id")
            if room_id:
                mappings[str(room_id)] = dict(room_map)
        return mappings

    def _room_configs(self) -> dict[str, dict[str, Any]]:
        options = dict(self._entry.options)
        configs: dict[str, dict[str, Any]] = {}
        for room in options.get(OPT_ROOMS, []):
            room_id = room.get("room_id")
            if room_id:
                configs[str(room_id)] = dict(room)
        return configs

    def _current_context_signals(self, options: dict[str, Any]) -> dict[str, str]:
        learning = dict(options.get("learning", {}) or {})
        raw_entities: list[str] = []
        room_configs = options.get(OPT_ROOMS, [])
        if isinstance(room_configs, list):
            for room in room_configs:
                if not isinstance(room, dict):
                    continue
                for raw_signal in list(room.get("learning_sources") or []):
                    if not isinstance(raw_signal, dict):
                        continue
                    entity_id = str(raw_signal.get("entity_id") or "").strip()
                    if entity_id:
                        raw_entities.append(entity_id)
        for entity_id in list(learning.get("context_signal_entities") or []):
            clean = str(entity_id or "").strip()
            if clean:
                raw_entities.append(clean)

        deduped: set[str] = set()
        raw_snapshot: dict[str, str] = {}
        for entity_id in raw_entities:
            if entity_id in deduped:
                continue
            deduped.add(entity_id)
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            raw_snapshot[entity_id] = str(state.state or "")
        return canonicalize_context_snapshot(raw_snapshot)

    def _queue_event(self, event: HeimaEvent) -> None:
        self._events_domain.queue_event(event)

    def _queue_house_state_changed_event(
        self, *, previous: str | None, current: str, reason: str
    ) -> None:
        self._events_domain.queue_house_state_changed_event(
            previous=previous, current=current, reason=reason
        )

    def _sync_event_sensors(self) -> None:
        self._events_domain.sync_event_sensors(self._state)

    def _sync_reactions_sensor(self) -> None:
        """Publish current reaction state to the heima_reactions_active sensor.

        Keep the sensor state compact to avoid HA's 255-char state limit.
        Detailed reaction payload lives in sensor attributes.
        """
        payload: dict[str, Any] = {}
        for reaction in self._reactions:
            rid = reaction.reaction_id
            diag = reaction.diagnostics()
            provenance = self._configured_reaction_metadata(rid)
            payload[rid] = {
                "muted": rid in self._muted_reactions,
                "fire_count": diag.get("fire_count", 0),
                "suppressed_count": diag.get("suppressed_count", 0),
                "last_fired_ts": diag.get("last_fired_ts"),
                **provenance,
            }
        self._state.set_sensor("heima_reactions_active", len(payload))
        self._state.set_sensor_attributes(
            "heima_reactions_active",
            {
                "reactions": payload,
                "total": len(payload),
                "muted_total": sum(
                    1 for reaction_id in payload if reaction_id in self._muted_reactions
                ),
            },
        )

    def _configured_reaction_metadata(self, reaction_id: str) -> dict[str, Any]:
        configured = dict(dict(self._entry.options).get(OPT_REACTIONS, {}).get("configured", {}))
        cfg = configured.get(reaction_id)
        if not isinstance(cfg, dict):
            return {}
        keys = (
            "reaction_type",
            "origin",
            "author_kind",
            "source_request",
            "source_template_id",
            "source_proposal_id",
            "source_proposal_identity_key",
            "created_at",
            "last_tuned_at",
            "last_tuning_proposal_id",
            "last_tuning_origin",
            "last_tuning_followup_kind",
        )
        return {key: cfg[key] for key in keys if key in cfg and cfg[key] not in ("", [])}

    def _lighting_apply_mode(self) -> str:
        mode = str(
            dict(self._entry.options).get(OPT_LIGHTING_APPLY_MODE, DEFAULT_LIGHTING_APPLY_MODE)
        )
        if mode not in {"scene", "delegate"}:
            return DEFAULT_LIGHTING_APPLY_MODE
        return mode

    async def _emit_lighting_hold_events(self) -> None:
        await self._lighting_domain.emit_hold_events(
            room_maps=self._lighting_room_maps(),
            state=self._state,
            events=self._events_domain,
        )

    def _compute_group_presence(
        self,
        sources: list[str],
        required: int,
        *,
        strategy: str = "quorum",
        weight_threshold: Any = None,
        source_weights: Any = None,
        trace_key: str | None = None,
    ) -> tuple[Any, int]:
        """Backward-compat wrapper delegating to PeopleDomain using current normalizer."""
        # Sync the normalizer so test replacements of engine._normalizer are respected
        self._people_domain._normalizer = self._normalizer
        return self._people_domain._compute_group_presence(
            sources,
            required,
            strategy=strategy,
            weight_threshold=weight_threshold,
            source_weights=source_weights,
            trace_key=trace_key,
        )

    async def _emit_queued_events(self) -> None:
        await self._events_domain.async_emit_queued_events(
            notifications_config=self._notifications_config(),
            state=self._state,
        )

    async def _emit_event_obj(self, event: HeimaEvent) -> bool:
        return await self._events_domain.async_emit_event_obj(
            event, notifications_config=self._notifications_config()
        )

    def _notifications_config(self) -> dict[str, Any]:
        return dict(dict(self._entry.options).get(OPT_NOTIFICATIONS, {}))

    def _occupancy_mismatch_config(self) -> dict[str, Any]:
        cfg = self._notifications_config()
        policy = str(cfg.get("occupancy_mismatch_policy", DEFAULT_OCCUPANCY_MISMATCH_POLICY))
        if policy not in {"off", "smart", "strict"}:
            policy = DEFAULT_OCCUPANCY_MISMATCH_POLICY
        return {
            "policy": policy,
            "min_derived_rooms": int(
                cfg.get(
                    "occupancy_mismatch_min_derived_rooms",
                    DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
                )
            ),
            "persist_s": int(
                cfg.get("occupancy_mismatch_persist_s", DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S)
            ),
        }

    def _collect_config_issues(self, options: dict[str, Any]) -> list[str]:
        issues: list[str] = []

        heating_cfg = options.get(OPT_HEATING, {})
        if heating_cfg:
            apply_mode = str(heating_cfg.get("apply_mode", "") or "")
            climate_entity = str(heating_cfg.get("climate_entity", "") or "").strip()
            if apply_mode == "set_temperature":
                if not climate_entity:
                    issues.append(
                        "heating: apply_mode is set_temperature but climate_entity is not configured"
                    )
                elif self._hass.states.get(climate_entity) is None:
                    issues.append(f"heating: climate_entity '{climate_entity}' not found in HA")

        security_cfg = options.get(OPT_SECURITY, {})
        if security_cfg.get("enabled"):
            entity_id = str(security_cfg.get("security_state_entity", "") or "").strip()
            if not entity_id:
                issues.append("security: enabled but security_state_entity is not configured")
            elif self._hass.states.get(entity_id) is None:
                issues.append(f"security: security_state_entity '{entity_id}' not found in HA")
        camera_sources = security_cfg.get("camera_evidence_sources", [])
        if isinstance(camera_sources, list):
            for idx, raw_source in enumerate(camera_sources):
                if not isinstance(raw_source, dict):
                    issues.append(f"security: camera_evidence_sources[{idx}] is not an object")
                    continue
                if not bool(raw_source.get("enabled", True)):
                    continue
                source_id = str(raw_source.get("id") or "").strip()
                role = str(raw_source.get("role") or "").strip()
                source_label = f" ('{source_id}')" if source_id else ""
                if not source_id:
                    issues.append(f"security: camera_evidence_sources[{idx}] missing id")
                if not role:
                    issues.append(
                        f"security: camera_evidence_sources[{idx}]{source_label} missing role"
                    )
                entity_fields = (
                    "motion_entity",
                    "person_entity",
                    "vehicle_entity",
                    "contact_entity",
                )
                if not any(str(raw_source.get(field) or "").strip() for field in entity_fields):
                    issues.append(
                        f"security: camera_evidence_sources[{idx}]{source_label} has no bound entities"
                    )
                for field in entity_fields:
                    entity_id = str(raw_source.get(field) or "").strip()
                    if entity_id and self._hass.states.get(entity_id) is None:
                        issues.append(
                            f"security: camera_evidence_sources[{idx}]{source_label} "
                            f"{field} '{entity_id}' not found in HA"
                        )

        return issues

    def _check_and_queue_config_issues(self, options: dict[str, Any]) -> None:
        issues = self._collect_config_issues(options)
        fingerprint = "|".join(sorted(issues))
        if fingerprint == self._last_config_issues_fingerprint:
            return
        self._last_config_issues_fingerprint = fingerprint
        if not issues:
            return
        self._events_domain.queue_event(
            HeimaEvent(
                type="system.config_invalid",
                key="system.config_invalid",
                severity="warn",
                title="Heima configuration issue",
                message=f"{len(issues)} configuration issue(s) detected.",
                context={"issues": issues},
            )
        )

    # Backward-compat class-level alias for tests that reference the static method on HeimaEngine
    _heating_vacation_recheck_delay_s = staticmethod(
        HeatingDomain._heating_vacation_recheck_delay_s
    )

    def _compute_house_signal(self, trace_key: str, entity_ids: list[str]) -> bool:
        """Backward-compat wrapper delegating to HouseStateDomain."""
        self._house_state_domain._normalizer = self._normalizer
        return self._house_state_domain._compute_house_signal(trace_key, entity_ids)

    def _is_entity_home(self, entity_id: str | None) -> bool:
        return self._normalizer.presence(entity_id).state == "on"

    def _is_presence_on(self, entity_id: str | None) -> bool:
        return self._normalizer.presence(entity_id).state == "on"

    def _is_on_any(self, entity_ids: list[str]) -> bool:
        return any(
            self._normalizer.boolean_signal(entity_id).state == "on" for entity_id in entity_ids
        )

    def _apply_snapshot_to_canonical_state(self, snapshot: DecisionSnapshot) -> None:
        for zone_id in list(snapshot.lighting_intents.keys()):
            key = f"heima_occ_zone_{zone_id}"
            zone_rooms = self._zone_rooms(zone_id)
            zone_is_on = any(room in snapshot.occupied_rooms for room in zone_rooms)
            if key in self._state.binary_sensors:
                self._state.set_binary(key, zone_is_on)

    def _zone_rooms(self, zone_id: str) -> list[str]:
        options = dict(self._entry.options)
        for zone in options.get(OPT_LIGHTING_ZONES, []):
            if zone.get("zone_id") == zone_id:
                return list(zone.get("rooms", []))
        return []

    def _room_occupancy_mode(self, room_cfg: dict[str, Any]) -> str:
        mode = str(room_cfg.get("occupancy_mode", "derived") or "derived")
        return mode if mode in {"derived", "none"} else "derived"

    def diagnostics(self) -> dict[str, Any]:
        security_camera_evidence_provider = getattr(
            self, "_security_camera_evidence_provider", None
        )
        return {
            "snapshot": self._snapshot.as_dict(),
            "active_constraints": sorted(self._active_constraints),
            "apply_plan": {
                "plan_id": self._apply_plan.plan_id,
                "steps": [
                    {
                        "domain": step.domain,
                        "target": step.target,
                        "action": step.action,
                        "params": dict(step.params),
                        "reason": step.reason,
                        "blocked_by": step.blocked_by,
                    }
                    for step in self._apply_plan.steps
                ],
            },
            "calendar": self._calendar_domain.diagnostics(),
            "lighting": self._lighting_domain.diagnostics(),
            "heating": self._heating_domain.diagnostics(),
            "security_camera_evidence": (
                security_camera_evidence_provider.diagnostics()
                if security_camera_evidence_provider is not None
                else {}
            ),
            "security": self._security_domain.diagnostics(),
            "house_state": self._house_state_domain.diagnostics(),
            "presence": self._people_domain.diagnostics(),
            "occupancy": self._occupancy_domain.diagnostics(),
            "events": self._events_domain.diagnostics(),
            "normalization": self._normalizer.diagnostics(),
            "behaviors": {b.behavior_id: b.diagnostics() for b in self._behaviors},
            "reactions": {r.reaction_id: r.diagnostics() for r in self._reactions},
            "muted_reactions": sorted(self._muted_reactions),
        }
