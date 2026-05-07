"""Coordinator for Heima runtime."""

# mypy: ignore-errors

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .models import HeimaRuntimeState
from .reconciliation import reconcile_ha_backed_options
from .runtime.analyzers import (
    ActivityAnalyzer,
    create_builtin_learning_plugin_registry,
)
from .runtime.analyzers.base import ReactionProposal
from .runtime.behaviors import (
    ActuationRecorderBehavior,
    EventCanonicalizer,
    EventRecorderBehavior,
    HeatingRecorderBehavior,
    LightingReactionGuardBehavior,
    LightingRecorderBehavior,
)
from .runtime.context_builder import ContextBuilder
from .runtime.engine import HeimaEngine
from .runtime.event_store import EventStore
from .runtime.finding_router import FindingRouter
from .runtime.inference import (
    ACTIVITY_PROPOSAL_TYPE,
    ActivityInferenceModule,
    ApprovalActor,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalStore,
    HeatingPreferenceModule,
    HouseStateInferenceModule,
    LearnedHouseStateCandidate,
    SnapshotStore,
    WeekdayStateModule,
)
from .runtime.inference.approval_store import (
    HOUSE_STATE_PROPOSAL_TYPE,
    activity_context_key,
    activity_context_snapshot,
)
from .runtime.outcome_tracker import OutcomeTracker
from .runtime.plugin_contracts import AnomalySignal
from .runtime.proposal_engine import ActivityProposal, ProposalEngine
from .runtime.scheduler import RuntimeScheduler

_LOGGER = logging.getLogger(__name__)
_PROPOSAL_RUN_INTERVAL_S = 6 * 60 * 60
_ANALYZE_INTERVAL_S = 6 * 60 * 60


class HeimaCoordinator(DataUpdateCoordinator[HeimaRuntimeState]):
    """Owns the Heima runtime engine instance."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=None,  # push-based
        )
        self.entry = entry
        self.engine = HeimaEngine(hass, entry)
        for plugin in self.engine.builtin_domain_plugins():
            self.engine.register_plugin(plugin)
        self.engine.finalize_dag()
        for check in self.engine.builtin_invariant_checks():
            self.engine.register_invariant_check(check)
        self._event_store = EventStore(hass)
        self._context_builder = ContextBuilder(hass, self._get_learning_config(entry))
        self.engine.set_context_builder(self._context_builder)
        self._outcome_tracker = OutcomeTracker()
        self.engine.set_outcome_tracker(self._outcome_tracker)
        self._event_recorder = EventRecorderBehavior(hass, self._event_store, self._context_builder)
        self.engine.register_behavior(self._event_recorder)
        self.engine.set_event_recorder(self._event_recorder)
        self.engine.register_behavior(
            HeatingRecorderBehavior(hass, self._event_store, self._context_builder)
        )
        self.engine.register_behavior(
            LightingReactionGuardBehavior(self.engine.state, dict(entry.options))
        )
        self._lighting_recorder = LightingRecorderBehavior(
            hass,
            self._event_store,
            self._context_builder,
            entry,
            lambda: self.engine.lighting_recent_apply_state,
        )
        self.engine.register_behavior(self._lighting_recorder)
        self.engine.register_behavior(
            ActuationRecorderBehavior(
                hass,
                self._event_store,
                self._context_builder,
                entry,
            )
        )
        self.engine.register_behavior(
            EventCanonicalizer(
                hass,
                self._event_store,
                self._context_builder,
                entry,
            )
        )
        self._house_snapshot_store = SnapshotStore(hass)
        self._learning_plugin_registry = self._build_learning_plugin_registry(entry)
        self._proposal_engine = ProposalEngine(
            hass,
            self._event_store,
            learning_plugin_registry=self._learning_plugin_registry,
            configured_reactions_provider=lambda: dict(
                (((entry.options or {}).get("reactions") or {}).get("configured") or {})
            ),
            sensor_writer=self._write_proposals_sensor,
        )
        self.engine.set_proposal_engine(self._proposal_engine)
        for plugin in self._learning_plugin_registry.analyzers():
            self._proposal_engine.register_analyzer(plugin)
        self._activity_analyzer = ActivityAnalyzer(self._house_snapshot_store)
        self._proposal_engine.register_analyzer(self._activity_analyzer)
        self._finding_router = FindingRouter(
            proposal_engine=self._proposal_engine,
            anomaly_handler=self._async_handle_anomaly_finding,
        )
        self._approval_store = ApprovalStore(hass)
        self._weekday_module = WeekdayStateModule()
        self._heating_module = HeatingPreferenceModule()
        self._house_state_module = HouseStateInferenceModule()
        self._activity_module = ActivityInferenceModule()
        self.engine.set_snapshot_store(self._house_snapshot_store)
        self.engine.register_learning_module(self._weekday_module)
        self.engine.register_learning_module(self._heating_module)
        self.engine.register_learning_module(self._house_state_module)
        self.engine.register_learning_module(self._activity_module)
        self._unsub_analyze_tick = None
        self._unsub_proposal_tick = None
        self._unsub_state_changed = None
        self._notified_house_state_proposal_keys: set[str] = set()
        self._notified_activity_proposal_keys: set[str] = set()
        self.last_options_snapshot: dict = dict(entry.options)
        self._scheduler = RuntimeScheduler(
            hass,
            entry_id=entry.entry_id,
            on_job_due=self._async_handle_scheduled_job,
        )
        self._ha_backed_reconciliation_summary: dict[str, object] = {}
        self.data = HeimaRuntimeState(
            health_ok=True,
            health_reason="booting",
            house_state="unknown",
            house_state_reason="",
            last_decision="",
            last_action="",
        )

    @property
    def scheduler(self) -> RuntimeScheduler:
        return self._scheduler

    @property
    def proposal_engine(self) -> ProposalEngine:
        return self._proposal_engine

    @property
    def learning_plugin_registry(self):
        return self._learning_plugin_registry

    @property
    def finding_router(self) -> FindingRouter:
        return self._finding_router

    async def _async_update_data(self) -> HeimaRuntimeState:
        """Return current runtime state for coordinator refreshes.

        Heima is push-driven: state updates are produced by explicit runtime calls.
        """
        return self.data

    async def async_initialize(self) -> None:
        """Initialize runtime and publish base state."""
        summary, changed = await self._async_reconcile_ha_backed_objects()
        await self._event_store.async_load()
        await self._house_snapshot_store.async_load()
        await self._approval_store.async_load()
        self._sync_house_state_approval_state()
        self._sync_activity_approval_state()
        await self._proposal_engine.async_initialize()
        await self.engine.async_initialize()
        if changed:
            await self.engine.async_reload_options(
                self.entry, changed_keys={"people_named", "rooms"}
            )
        await self._proposal_engine.async_run()
        await self._async_notify_pending_activity_proposals()
        self._write_event_store_sensor()
        self._schedule_proposal_tick()
        self._schedule_analyze_tick()
        self._subscribe_state_changes()
        self._sync_scheduler()
        self.data = HeimaRuntimeState(
            health_ok=self.engine.health.ok,
            health_reason=self.engine.health.reason,
            house_state=self.engine.snapshot.house_state,
            house_state_reason=self.engine.state.get_sensor("heima_house_state_reason") or "",
            last_decision="initialized",
            last_action="",
        )
        if changed:
            await self._async_emit_reconciliation_events(summary)
        await self.async_refresh()

    def _get_learning_config(self, entry: ConfigEntry) -> dict:
        return {
            "learning": dict(entry.options.get("learning", {})),
            "rooms": list(entry.options.get("rooms", [])),
        }

    def _build_learning_plugin_registry(self, entry: ConfigEntry):
        learning = dict(entry.options.get("learning", {}))
        raw_families = learning.get("enabled_plugin_families")
        enabled_families = (
            {str(item).strip() for item in raw_families if str(item).strip()}
            if isinstance(raw_families, list)
            else None
        )
        return create_builtin_learning_plugin_registry(
            enabled_families=enabled_families,
            learning_config=learning,
        )

    async def _async_handle_anomaly_finding(self, signal: AnomalySignal) -> None:
        await self.engine.async_emit_external_event(
            event_type="learning.anomaly",
            key=f"learning.anomaly.{signal.anomaly_type}",
            severity=signal.severity,
            title="Learning anomaly",
            message=signal.description,
            context={
                "anomaly_type": signal.anomaly_type,
                "confidence": signal.confidence,
                **dict(signal.context),
            },
        )

    async def async_reload_options(self, *, changed_keys: set[str] | None = None) -> None:
        """Reload options and refresh state."""
        await self.engine.async_reload_options(self.entry, changed_keys=changed_keys)
        self._context_builder.update_config(self._get_learning_config(self.entry))
        self._learning_plugin_registry = self._build_learning_plugin_registry(self.entry)
        self._proposal_engine.set_learning_plugin_registry(self._learning_plugin_registry)
        self._proposal_engine.set_analyzers(list(self._learning_plugin_registry.analyzers()))
        self._resubscribe_state_changes()
        self._sync_scheduler()
        self.data = HeimaRuntimeState(
            health_ok=self.engine.health.ok,
            health_reason=self.engine.health.reason,
            house_state=self.engine.snapshot.house_state,
            house_state_reason=self.engine.state.get_sensor("heima_house_state_reason") or "",
            last_decision="options_reloaded",
            last_action="",
        )
        await self.async_refresh()

    @property
    def ha_backed_reconciliation_summary(self) -> dict[str, object]:
        return dict(self._ha_backed_reconciliation_summary)

    async def async_request_evaluation(self, reason: str) -> None:
        """Request an evaluation cycle."""
        snapshot = await self.engine.async_evaluate(reason=reason)
        self.data = HeimaRuntimeState(
            health_ok=self.engine.health.ok,
            health_reason=self.engine.health.reason,
            house_state=snapshot.house_state,
            house_state_reason=self.engine.state.get_sensor("heima_house_state_reason") or "",
            last_decision=f"evaluation_requested:{reason}",
            last_action="",
        )
        self._sync_scheduler()
        await self.async_refresh()

    async def async_emit_event(
        self,
        *,
        event_type: str,
        key: str,
        severity: str,
        title: str,
        message: str,
        context: dict | None = None,
        reason: str = "service:notify_event",
    ) -> bool:
        """Emit an event through the engine pipeline and refresh coordinator state."""
        emitted = await self.engine.async_emit_external_event(
            event_type=event_type,
            key=key,
            severity=severity,
            title=title,
            message=message,
            context=context or {},
        )
        self.data = HeimaRuntimeState(
            health_ok=self.engine.health.ok,
            health_reason=self.engine.health.reason,
            house_state=self.engine.snapshot.house_state,
            house_state_reason=self.engine.state.get_sensor("heima_house_state_reason") or "",
            last_decision=f"{reason}:{'emitted' if emitted else 'suppressed'}",
            last_action="event_emitted" if emitted else "event_suppressed",
        )
        await self.async_refresh()
        return emitted

    async def async_set_house_state_override(self, *, mode: str, enabled: bool) -> str:
        """Set or clear the runtime-only final house-state override."""
        action, previous, current = self.engine.set_house_state_override(
            mode=mode,
            enabled=enabled,
            source="service:heima.set_mode",
        )
        await self.engine.async_emit_external_event(
            event_type="system.house_state_override_changed",
            key=(
                "system.house_state_override_changed:"
                f"{previous or 'none'}->{current or 'none'}:{action}"
            ),
            severity="info",
            title="House-state override changed",
            message=(
                f"House-state override {action}: {previous or 'none'} -> {current or 'none'}."
            ),
            context={
                "previous": previous,
                "current": current,
                "source": "service:heima.set_mode",
                "action": action,
            },
        )
        snapshot = await self.engine.async_evaluate(reason=f"service:set_mode:{mode}:{enabled}")
        self.data = HeimaRuntimeState(
            health_ok=self.engine.health.ok,
            health_reason=self.engine.health.reason,
            house_state=snapshot.house_state,
            house_state_reason=self.engine.state.get_sensor("heima_house_state_reason") or "",
            last_decision=f"evaluation_requested:service:set_mode:{mode}:{enabled}",
            last_action=f"house_state_override:{action}",
        )
        self._sync_scheduler()
        await self.async_refresh()
        return action

    async def async_reset_learning_data(self) -> None:
        """Reset learning event/proposal stores and refresh runtime sensors."""
        await self._event_store.async_clear()
        await self._event_store.async_flush()
        await self._proposal_engine.async_clear()
        await self._approval_store.async_clear()
        await self._approval_store.async_flush()
        self._sync_house_state_approval_state()
        self._sync_activity_approval_state()
        if hasattr(self, "_notified_house_state_proposal_keys"):
            self._notified_house_state_proposal_keys.clear()
        if hasattr(self, "_notified_activity_proposal_keys"):
            self._notified_activity_proposal_keys.clear()
        self.engine.reset_learning_state()
        self._write_event_store_sensor()
        await self.async_refresh()

    async def async_run_learning_now(self) -> None:
        """Run learning analyzers immediately and refresh exposed state."""
        await self._async_analyze_inference_modules()
        await self._proposal_engine.async_run()
        await self._async_notify_pending_activity_proposals()
        self._write_event_store_sensor()
        await self.async_refresh()

    async def async_review_proposal(
        self,
        proposal_id: str,
        decision: ApprovalDecision,
        approved_by: ApprovalActor,
    ) -> bool:
        """Review one proposal by dispatching on the proposal's own type."""
        proposal = self._proposal_engine.proposal_by_id(proposal_id)
        proposal_type = _proposal_review_type(proposal)
        if proposal_type == HOUSE_STATE_PROPOSAL_TYPE:
            return await self.async_review_house_state_proposal(
                proposal_id,
                decision=decision,
                approved_by=approved_by,
            )
        if proposal_type == ACTIVITY_PROPOSAL_TYPE:
            return await self.async_review_activity_proposal(
                proposal_id,
                decision=decision,
                approved_by=approved_by,
            )
        return False

    async def async_review_house_state_proposal(
        self,
        proposal_id: str,
        decision: ApprovalDecision,
        approved_by: ApprovalActor,
    ) -> bool:
        """Review a proposal and persist house-state approval decisions when applicable."""
        proposal = self._proposal_engine.proposal_by_id(proposal_id)
        if proposal is None:
            return False

        record = None
        if proposal.reaction_type == HOUSE_STATE_PROPOSAL_TYPE:
            record = _approval_record_from_house_state_proposal(
                proposal,
                decision=decision,
                approved_by=approved_by,
            )
            if record is None:
                return False

        if decision == "approved":
            updated = await self._proposal_engine.async_accept_proposal(proposal_id)
        elif decision == "rejected":
            updated = await self._proposal_engine.async_reject_proposal(proposal_id)
        else:
            return False
        if not updated:
            return False

        if record is not None:
            await self._approval_store.async_record(record)
            await self._approval_store.async_flush()
            self._sync_house_state_approval_state()
            if proposal.identity_key:
                self._notified_house_state_proposal_keys.discard(proposal.identity_key)

        return True

    async def async_review_activity_proposal(
        self,
        proposal_id: str,
        decision: ApprovalDecision,
        approved_by: ApprovalActor,
    ) -> bool:
        """Review a composite activity proposal and persist its approval decision."""
        proposal = self._proposal_engine.proposal_by_id(proposal_id)
        if not isinstance(proposal, ActivityProposal):
            return False
        if proposal.proposal_type != ACTIVITY_PROPOSAL_TYPE:
            return False

        record = _approval_record_from_activity_proposal(
            proposal,
            decision=decision,
            approved_by=approved_by,
        )
        if record is None:
            return False

        if decision == "approved":
            updated = await self._proposal_engine.async_accept_proposal(proposal_id)
        elif decision == "rejected":
            updated = await self._proposal_engine.async_reject_proposal(proposal_id)
        else:
            return False
        if not updated:
            return False

        await self._approval_store.async_record(record)
        await self._approval_store.async_flush()
        self._sync_activity_approval_state()
        if proposal.identity_key:
            self._notified_activity_proposal_keys.discard(proposal.identity_key)
        return True

    async def async_upsert_configured_reactions(
        self,
        configured_updates: dict[str, dict],
        *,
        label_updates: dict[str, str] | None = None,
    ) -> None:
        """Merge configured reactions into entry options for live-test harnesses."""
        options = dict(self.entry.options)
        reactions = dict(options.get("reactions", {}))
        configured = dict(reactions.get("configured", {}))
        labels = dict(reactions.get("labels", {}))

        for reaction_id, cfg in configured_updates.items():
            if not isinstance(cfg, dict):
                continue
            configured[str(reaction_id)] = dict(cfg)
        for reaction_id, label in (label_updates or {}).items():
            text = str(label).strip()
            if text:
                labels[str(reaction_id)] = text

        reactions["configured"] = configured
        reactions["labels"] = labels
        options["reactions"] = reactions
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_seed_lighting_events(
        self,
        *,
        entity_id: str,
        room_id: str,
        action: str = "on",
        weekday: int,
        minute: int,
        brightness: int | None = None,
        color_temp_kelvin: int | None = None,
        count: int = 6,
    ) -> int:
        """Inject synthetic lighting events backfilled across 2 ISO weeks (for testing).

        Returns the number of events appended.
        """
        from datetime import timedelta

        from .runtime.event_store import EventContext, HeimaEvent

        now_utc = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        # Distribute events: first half in week-2, second half in week-1
        n_week1 = count // 2
        n_week2 = count - n_week1
        offsets = [timedelta(weeks=-2)] * n_week1 + [timedelta(weeks=-1)] * n_week2

        ctx = EventContext(
            weekday=weekday,
            minute_of_day=minute,
            month=now_utc.month,
            house_state="home",
            occupants_count=1,
            occupied_rooms=(room_id,),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        )
        for offset in offsets:
            ts = (now_utc + offset).isoformat()
            event = HeimaEvent(
                ts=ts,
                event_type="lighting",
                context=ctx,
                source="user",
                data={
                    "entity_id": entity_id,
                    "room_id": room_id,
                    "action": action,
                    "brightness": brightness if action == "on" else None,
                    "color_temp_kelvin": color_temp_kelvin if action == "on" else None,
                    "rgb_color": None,
                },
            )
            await self._event_store.async_append(event)

        await self._event_store.async_flush()
        self._write_event_store_sensor()
        return count

    async def async_seed_lighting_scene_events(
        self,
        *,
        room_id: str,
        entity_steps: list[dict[str, object]],
        weekday: int,
        minute: int,
        count: int = 6,
        signals: dict[str, str] | None = None,
        house_state: str = "home",
    ) -> int:
        """Inject synthetic multi-entity lighting scene events across 2 ISO weeks.

        Unlike ``async_seed_lighting_events()``, all entity steps belonging to the
        same synthetic episode share the exact same timestamp and context so
        lighting scene matching and context-conditioned sampling remain stable.
        """
        from datetime import timedelta

        from .runtime.event_store import EventContext, HeimaEvent

        now_utc = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        n_week1 = count // 2
        n_week2 = count - n_week1
        offsets = [timedelta(weeks=-2)] * n_week1 + [timedelta(weeks=-1)] * n_week2
        raw_signals = {
            str(entity_id): str(state)
            for entity_id, state in dict(signals or {}).items()
            if str(entity_id or "").strip() and str(state or "").strip()
        }

        total = 0
        for offset in offsets:
            ts = (now_utc + offset).isoformat()
            ctx = EventContext(
                weekday=weekday,
                minute_of_day=minute,
                month=now_utc.month,
                house_state=house_state,
                occupants_count=1,
                occupied_rooms=(room_id,),
                outdoor_lux=None,
                outdoor_temp=None,
                weather_condition=None,
                signals=raw_signals,
            )
            for step in entity_steps:
                entity_id = str(step.get("entity_id") or "").strip()
                action = str(step.get("action") or "").strip().lower()
                if not entity_id or action not in {"on", "off"}:
                    continue
                event = HeimaEvent(
                    ts=ts,
                    event_type="lighting",
                    context=ctx,
                    source="user",
                    domain="lighting",
                    subject_type="entity",
                    subject_id=entity_id,
                    room_id=room_id,
                    data={
                        "entity_id": entity_id,
                        "room_id": room_id,
                        "action": action,
                        "brightness": step.get("brightness") if action == "on" else None,
                        "color_temp_kelvin": (
                            step.get("color_temp_kelvin") if action == "on" else None
                        ),
                        "rgb_color": step.get("rgb_color") if action == "on" else None,
                    },
                )
                await self._event_store.async_append(event)
                total += 1

        await self._event_store.async_flush()
        self._write_event_store_sensor()
        return total

    async def async_shutdown(self) -> None:
        """Shutdown runtime."""
        self._unsubscribe_state_changes()
        self._cancel_proposal_tick()
        self._cancel_analyze_tick()
        await self._proposal_engine.async_shutdown()
        await self._scheduler.async_shutdown()
        await self._event_store.async_flush()
        await self.engine.async_shutdown()
        _LOGGER.debug("Heima runtime shutdown")

    def _resubscribe_state_changes(self) -> None:
        self._unsubscribe_state_changes()
        self._subscribe_state_changes()

    def _unsubscribe_state_changes(self) -> None:
        if self._unsub_state_changed:
            self._unsub_state_changed()
            self._unsub_state_changed = None

    def _sync_scheduler(self) -> None:
        self._scheduler.sync_jobs(self.engine.scheduled_runtime_jobs())

    async def _async_handle_scheduled_job(self, job_id: str) -> None:
        await self.async_request_evaluation(reason=f"scheduler:{job_id}")

    def _subscribe_state_changes(self) -> None:
        tracked_entities = self.engine.tracked_entity_ids()

        @callback
        def _handle_state_changed(event: Event) -> None:
            entity_id = event.data.get("entity_id")
            if entity_id not in tracked_entities and not str(entity_id or "").startswith("person."):
                return
            self.hass.async_create_task(self._async_handle_state_changed(str(entity_id)))

        self._unsub_state_changed = self.hass.bus.async_listen(
            "state_changed", _handle_state_changed
        )

    def _schedule_proposal_tick(self) -> None:
        self._cancel_proposal_tick()

        @callback
        def _handle(_now) -> None:
            self.hass.async_create_task(self._async_run_proposal_tick())

        self._unsub_proposal_tick = async_call_later(self.hass, _PROPOSAL_RUN_INTERVAL_S, _handle)

    def _cancel_proposal_tick(self) -> None:
        if self._unsub_proposal_tick:
            self._unsub_proposal_tick()
            self._unsub_proposal_tick = None

    def _cancel_analyze_tick(self) -> None:
        if self._unsub_analyze_tick:
            self._unsub_analyze_tick()
            self._unsub_analyze_tick = None

    def _schedule_analyze_tick(self) -> None:
        self._cancel_analyze_tick()

        @callback
        def _handle(_now) -> None:  # type: ignore[no-untyped-def]
            self.hass.async_create_task(self._async_run_analyze_tick())

        self._unsub_analyze_tick = async_call_later(self.hass, _ANALYZE_INTERVAL_S, _handle)

    async def _async_run_analyze_tick(self) -> None:
        try:
            await self._async_analyze_inference_modules()
        finally:
            self._schedule_analyze_tick()

    async def _async_analyze_inference_modules(self) -> None:
        self._sync_house_state_approval_state()
        self._sync_activity_approval_state()
        for module in (
            self._weekday_module,
            self._heating_module,
            self._house_state_module,
            self._activity_module,
        ):
            await module.analyze(self._house_snapshot_store)
        await self._async_submit_house_state_candidates()

    async def _async_submit_house_state_candidates(self) -> None:
        self._sync_house_state_approval_state()
        for candidate in self._house_state_module.generate_candidates():
            proposal = _proposal_from_house_state_candidate(candidate)
            proposal_id = await self._proposal_engine.async_submit_proposal(proposal)
            await self._async_notify_house_state_proposal(proposal, proposal_id=proposal_id)

    async def _async_notify_pending_activity_proposals(self) -> None:
        if not hasattr(self._proposal_engine, "pending_proposals"):
            return
        for proposal in self._proposal_engine.pending_proposals():
            if not isinstance(proposal, ActivityProposal):
                continue
            if proposal.proposal_type != ACTIVITY_PROPOSAL_TYPE:
                continue
            await self._async_notify_activity_proposal(
                proposal,
                proposal_id=proposal.proposal_id,
            )

    async def _async_notify_activity_proposal(
        self,
        proposal: ActivityProposal,
        *,
        proposal_id: str,
    ) -> None:
        identity_key = str(proposal.identity_key or "").strip()
        if not identity_key:
            identity_key = (
                self._proposal_engine.proposal_by_id(proposal_id).identity_key
                if self._proposal_engine.proposal_by_id(proposal_id) is not None
                else ""
            )
        if not identity_key:
            identity_key = activity_context_key(
                activity_name=proposal.activity_name,
                primitive_pattern=proposal.primitive_pattern,
                context_conditions=proposal.context_conditions,
            )
        if identity_key in self._notified_activity_proposal_keys:
            return
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "notification_id": _activity_notification_id(identity_key),
                    "title": "Heima has a new activity proposal",
                    "message": _activity_proposal_notification_message(
                        proposal_id=proposal_id,
                        proposal=proposal,
                    ),
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Failed to create activity proposal notification")
        finally:
            self._notified_activity_proposal_keys.add(identity_key)

    async def _async_notify_house_state_proposal(
        self,
        proposal: ReactionProposal,
        *,
        proposal_id: str,
    ) -> None:
        identity_key = str(proposal.identity_key or "").strip()
        if not identity_key or identity_key in self._notified_house_state_proposal_keys:
            return
        cfg = dict(proposal.suggested_reaction_config)
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "notification_id": _house_state_notification_id(identity_key),
                    "title": "Heima has a new house-state proposal",
                    "message": _house_state_proposal_notification_message(
                        proposal_id=proposal_id,
                        context_snapshot=dict(cfg.get("context_snapshot") or {}),
                        confidence=proposal.confidence,
                    ),
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Failed to create house-state proposal notification")
        finally:
            self._notified_house_state_proposal_keys.add(identity_key)

    def _sync_house_state_approval_state(self) -> None:
        approved: set[str] = set()
        rejected: set[str] = set()
        for record in self._approval_store.records():
            if record.proposal_type != HOUSE_STATE_PROPOSAL_TYPE:
                continue
            if record.decision == "approved":
                approved.add(record.context_key)
            elif record.decision == "rejected":
                rejected.add(record.context_key)
        self._house_state_module.sync_approval_state(approved, rejected)

    def _sync_activity_approval_state(self) -> None:
        if not hasattr(self._approval_store, "records") or not hasattr(self, "_activity_module"):
            return
        approved: list[ActivityProposal] = []
        for record in self._approval_store.records():
            if record.proposal_type != ACTIVITY_PROPOSAL_TYPE:
                continue
            if record.decision != "approved":
                continue
            proposal = self._proposal_engine.proposal_by_id(record.proposal_id)
            if isinstance(proposal, ActivityProposal):
                approved.append(proposal)
                continue
            fallback = _activity_proposal_from_approval_record(record)
            if fallback is not None:
                approved.append(fallback)
        self._activity_module.sync_approved_proposals(approved)

    async def _async_run_proposal_tick(self) -> None:
        try:
            summary, changed = await self._async_reconcile_ha_backed_objects()
            if changed:
                await self._async_emit_reconciliation_events(summary)
            await self._proposal_engine.async_run()
            await self._async_notify_pending_activity_proposals()
            self._write_event_store_sensor()
            await self.async_refresh()
        finally:
            self._schedule_proposal_tick()

    async def _async_handle_state_changed(self, entity_id: str) -> None:
        summary, changed = await self._async_reconcile_ha_backed_objects()
        if changed:
            await self._async_emit_reconciliation_events(summary)
            return
        if entity_id in self.engine.tracked_entity_ids():
            await self.async_request_evaluation(reason=f"state_changed:{entity_id}")

    async def _async_reconcile_ha_backed_objects(self) -> tuple[dict[str, object], bool]:
        options = dict(self.entry.options)
        updated_options, summary, changed = reconcile_ha_backed_options(
            options,
            ha_people=self._ha_people_inventory(),
            ha_areas=self._ha_area_inventory(),
        )
        self._ha_backed_reconciliation_summary = summary
        if changed:
            self.hass.config_entries.async_update_entry(self.entry, options=updated_options)
            self.last_options_snapshot = dict(updated_options)
        return summary, changed

    def _ha_people_inventory(self) -> list[dict[str, str]]:
        states = getattr(self.hass, "states", None)
        async_all = getattr(states, "async_all", None)
        if not callable(async_all):
            return []
        try:
            all_states = list(async_all())
        except TypeError:
            all_states = list(async_all("person"))
        people: list[dict[str, str]] = []
        for state in all_states:
            entity_id = str(getattr(state, "entity_id", "")).strip()
            if not entity_id.startswith("person."):
                continue
            name = str(
                getattr(state, "name", None)
                or getattr(state, "attributes", {}).get("friendly_name")
                or entity_id.split(".", 1)[1]
            ).strip()
            people.append({"entity_id": entity_id, "display_name": name})
        return people

    def _ha_area_inventory(self) -> list[dict[str, str]]:
        try:
            area_reg = ar.async_get(self.hass)
        except Exception:
            return []
        lister = getattr(area_reg, "async_list_areas", None)
        if not callable(lister):
            return []
        return [
            {"area_id": str(area.id), "display_name": str(area.name)}
            for area in lister()
            if getattr(area, "id", None)
        ]

    async def _async_emit_reconciliation_events(self, summary: dict[str, object]) -> None:
        people_summary = dict(summary.get("people") or {})
        rooms_summary = dict(summary.get("rooms") or {})

        new_people = [
            str(item) for item in list(people_summary.get("new_labels") or []) if str(item)
        ]
        new_rooms = [str(item) for item in list(rooms_summary.get("new_labels") or []) if str(item)]
        orphaned_people = [
            str(item) for item in list(people_summary.get("orphaned_labels") or []) if str(item)
        ]
        orphaned_rooms = [
            str(item) for item in list(rooms_summary.get("orphaned_labels") or []) if str(item)
        ]

        if new_people:
            await self.engine.async_emit_external_event(
                event_type="system.new_person_discovered",
                key=f"system.new_person_discovered:{','.join(sorted(new_people))}",
                severity="info",
                title="New Home Assistant person discovered",
                message=f"Heima discovered {len(new_people)} new Home Assistant person(s): {', '.join(new_people)}.",
                context={"people": new_people, "reconciliation": "ha_backed_people_rooms"},
            )
        if new_rooms:
            await self.engine.async_emit_external_event(
                event_type="system.new_room_discovered",
                key=f"system.new_room_discovered:{','.join(sorted(new_rooms))}",
                severity="info",
                title="New Home Assistant room discovered",
                message=f"Heima discovered {len(new_rooms)} new Home Assistant room(s): {', '.join(new_rooms)}.",
                context={"rooms": new_rooms, "reconciliation": "ha_backed_people_rooms"},
            )
        if orphaned_people:
            await self.engine.async_emit_external_event(
                event_type="system.person_binding_orphaned",
                key=f"system.person_binding_orphaned:{','.join(sorted(orphaned_people))}",
                severity="warning",
                title="Heima person binding orphaned",
                message=f"Heima found {len(orphaned_people)} orphaned person binding(s): {', '.join(orphaned_people)}.",
                context={"people": orphaned_people, "reconciliation": "ha_backed_people_rooms"},
            )
        if orphaned_rooms:
            await self.engine.async_emit_external_event(
                event_type="system.room_binding_orphaned",
                key=f"system.room_binding_orphaned:{','.join(sorted(orphaned_rooms))}",
                severity="warning",
                title="Heima room binding orphaned",
                message=f"Heima found {len(orphaned_rooms)} orphaned room binding(s): {', '.join(orphaned_rooms)}.",
                context={"rooms": orphaned_rooms, "reconciliation": "ha_backed_people_rooms"},
            )

    def _write_proposals_sensor(self, pending_count: int, attributes: dict) -> None:
        self.engine.state.set_sensor("heima_reaction_proposals", pending_count)
        self.engine.state.set_sensor_attributes("heima_reaction_proposals", attributes)

    def _write_event_store_sensor(self) -> None:
        diag = self._event_store.diagnostics()
        self.engine.state.set_sensor("heima_event_store", diag["total_events"])
        self.engine.state.set_sensor_attributes("heima_event_store", diag["by_type"])


def _proposal_from_house_state_candidate(
    candidate: LearnedHouseStateCandidate,
) -> ReactionProposal:
    """Build a resident-reviewable proposal for one learned house-state context."""
    identity_key = f"{HOUSE_STATE_PROPOSAL_TYPE}:{candidate.context_key}"
    return ReactionProposal(
        analyzer_id="house_state_inference",
        reaction_type=HOUSE_STATE_PROPOSAL_TYPE,
        description=(
            f"Learned house-state context predicts '{candidate.predicted_state}' "
            f"with {candidate.support}/{candidate.total} matching observations."
        ),
        confidence=candidate.confidence,
        origin="learned",
        followup_kind="discovery",
        identity_key=identity_key,
        suggested_reaction_config={
            "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
            "context_key": candidate.context_key,
            "context_snapshot": dict(candidate.context_snapshot),
            "predicted_state": candidate.predicted_state,
            "support": candidate.support,
            "total": candidate.total,
        },
    )


def _approval_record_from_house_state_proposal(
    proposal: ReactionProposal,
    *,
    decision: ApprovalDecision,
    approved_by: ApprovalActor,
) -> ApprovalRecord | None:
    """Convert a reviewed house-state proposal to a durable approval record."""
    cfg = dict(proposal.suggested_reaction_config)
    context_key = str(cfg.get("context_key") or "").strip()
    context_snapshot = cfg.get("context_snapshot")
    if not context_key or not isinstance(context_snapshot, dict) or not context_snapshot:
        return None
    return ApprovalRecord(
        proposal_id=proposal.proposal_id,
        proposal_type=HOUSE_STATE_PROPOSAL_TYPE,
        decision=decision,
        approved_by=approved_by,
        context_key=context_key,
        context_snapshot=dict(context_snapshot),
        metadata={
            "predicted_state": str(cfg.get("predicted_state") or ""),
            "support": cfg.get("support"),
            "total": cfg.get("total"),
            "confidence": proposal.confidence,
        },
    )


def _approval_record_from_activity_proposal(
    proposal: ActivityProposal,
    *,
    decision: ApprovalDecision,
    approved_by: ApprovalActor,
) -> ApprovalRecord | None:
    """Convert a reviewed activity proposal to a durable approval record."""
    context_key = activity_context_key(
        activity_name=proposal.activity_name,
        primitive_pattern=proposal.primitive_pattern,
        context_conditions=proposal.context_conditions,
    )
    context_snapshot = activity_context_snapshot(
        activity_name=proposal.activity_name,
        primitive_pattern=proposal.primitive_pattern,
        context_conditions=proposal.context_conditions,
    )
    if not context_key or not context_snapshot:
        return None
    return ApprovalRecord(
        proposal_id=proposal.proposal_id,
        proposal_type=ACTIVITY_PROPOSAL_TYPE,
        decision=decision,
        approved_by=approved_by,
        context_key=context_key,
        context_snapshot=dict(context_snapshot),
        metadata={
            "activity_name": proposal.activity_name,
            "primitive_pattern": sorted(proposal.primitive_pattern),
            "context_conditions": dict(proposal.context_conditions),
            "occurrence_count": proposal.occurrence_count,
            "confidence": proposal.confidence,
        },
    )


def _activity_proposal_from_approval_record(record: ApprovalRecord) -> ActivityProposal | None:
    snapshot = dict(record.context_snapshot)
    activity_name = str(snapshot.get("activity_name") or "").strip()
    primitive_pattern = snapshot.get("primitive_pattern")
    if not activity_name or not isinstance(primitive_pattern, list | tuple | set | frozenset):
        return None
    context_conditions = snapshot.get("context_conditions")
    if not isinstance(context_conditions, dict):
        context_conditions = {}
    return ActivityProposal(
        proposal_id=record.proposal_id,
        activity_name=activity_name,
        primitive_pattern=frozenset(str(item) for item in primitive_pattern if str(item).strip()),
        context_conditions=dict(context_conditions),
        occurrence_count=int(record.metadata.get("occurrence_count") or 0),
        confidence=float(record.metadata.get("confidence") or 1.0),
        status=record.decision,
    )


def _proposal_review_type(proposal: object | None) -> str:
    if proposal is None:
        return ""
    proposal_type = str(getattr(proposal, "proposal_type", "") or "").strip()
    if proposal_type:
        return proposal_type
    return str(getattr(proposal, "reaction_type", "") or "").strip()


def _house_state_notification_id(identity_key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in identity_key.lower()).strip("_")
    return f"heima_house_state_proposal_{safe[:120]}"


def _activity_notification_id(identity_key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in identity_key.lower()).strip("_")
    return f"heima_activity_proposal_{safe[:120]}"


def _house_state_proposal_notification_message(
    *,
    proposal_id: str,
    context_snapshot: dict[str, object],
    confidence: float,
) -> str:
    predicted_state = str(context_snapshot.get("predicted_state") or "unknown")
    weekday = context_snapshot.get("weekday")
    hour_bucket = context_snapshot.get("hour_bucket")
    rooms = context_snapshot.get("rooms")
    if isinstance(rooms, list | tuple):
        room_label = ", ".join(str(room) for room in rooms) or "no specific room"
    else:
        room_label = "no specific room"
    anyone_home = "someone is home" if context_snapshot.get("anyone_home") else "no one is home"
    return (
        "Heima learned a recurring house-state context and needs a resident review.\n\n"
        f"Suggested state: {predicted_state}\n"
        f"Context: weekday {weekday}, hour {hour_bucket}, rooms: {room_label}, {anyone_home}\n"
        f"Confidence: {confidence:.0%}\n\n"
        "Open the Heima dashboard to approve or reject this proposal.\n"
        f"Proposal ID: {proposal_id}"
    )


def _activity_proposal_notification_message(
    *,
    proposal_id: str,
    proposal: ActivityProposal,
) -> str:
    pattern = ", ".join(sorted(proposal.primitive_pattern)) or "unknown activities"
    room_id = str(proposal.context_conditions.get("room_id") or "").strip()
    hour_range = proposal.context_conditions.get("hour_range")
    context_parts: list[str] = []
    if room_id:
        context_parts.append(f"room {room_id}")
    if isinstance(hour_range, list | tuple) and len(hour_range) == 2:
        context_parts.append(f"hours {hour_range[0]}-{hour_range[1]}")
    context = ", ".join(context_parts) if context_parts else "no specific context"
    return (
        "Heima found a recurring composite activity and needs a resident review.\n\n"
        f"Suggested activity: {proposal.activity_name}\n"
        f"Primitive pattern: {pattern}\n"
        f"Context: {context}\n"
        f"Confidence: {proposal.confidence:.0%}\n\n"
        "Open the Heima dashboard to approve or reject this proposal.\n"
        f"Proposal ID: {proposal_id}"
    )
