"""Coordinator for Heima runtime."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .models import HeimaRuntimeState
from .runtime.analyzers import (
    CompositePatternCatalogAnalyzer,
    CrossDomainPatternAnalyzer,
    HeatingPatternAnalyzer,
    LightingPatternAnalyzer,
    PresencePatternAnalyzer,
    RoomCoolingPatternAnalyzer,
)
from .runtime.behaviors import (
    EventRecorderBehavior,
    HeatingRecorderBehavior,
    LightingRecorderBehavior,
    SignalRecorderBehavior,
)
from .runtime.context_builder import ContextBuilder
from .runtime.engine import HeimaEngine
from .runtime.event_store import EventStore
from .runtime.proposal_engine import ProposalEngine
from .runtime.scheduler import RuntimeScheduler

_LOGGER = logging.getLogger(__name__)
_PROPOSAL_RUN_INTERVAL_S = 6 * 60 * 60


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
        self._event_store = EventStore(hass)
        self._context_builder = ContextBuilder(hass, self._get_learning_config(entry))
        self.engine.register_behavior(EventRecorderBehavior(hass, self._event_store, self._context_builder))
        self.engine.register_behavior(HeatingRecorderBehavior(hass, self._event_store, self._context_builder))
        self._lighting_recorder = LightingRecorderBehavior(
            hass,
            self._event_store,
            self._context_builder,
            entry,
            lambda: self.engine.lighting_recent_apply_state,
        )
        self.engine.register_behavior(self._lighting_recorder)
        self.engine.register_behavior(
            SignalRecorderBehavior(hass, self._event_store, self._context_builder, entry)
        )
        self._proposal_engine = ProposalEngine(
            hass,
            self._event_store,
            sensor_writer=self._write_proposals_sensor,
        )
        self._proposal_engine.register_analyzer(PresencePatternAnalyzer())
        self._proposal_engine.register_analyzer(HeatingPatternAnalyzer())
        self._proposal_engine.register_analyzer(LightingPatternAnalyzer())
        self._proposal_engine.register_analyzer(CompositePatternCatalogAnalyzer())
        self._unsub_proposal_tick = None
        self._unsub_state_changed = None
        self.last_options_snapshot: dict = dict(entry.options)
        self._scheduler = RuntimeScheduler(
            hass,
            entry_id=entry.entry_id,
            on_job_due=self._async_handle_scheduled_job,
        )
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

    async def _async_update_data(self) -> HeimaRuntimeState:
        """Return current runtime state for coordinator refreshes.

        Heima is push-driven: state updates are produced by explicit runtime calls.
        """
        return self.data

    async def async_initialize(self) -> None:
        """Initialize runtime and publish base state."""
        await self._event_store.async_load()
        await self._proposal_engine.async_initialize()
        await self.engine.async_initialize()
        await self._proposal_engine.async_run()
        self._write_event_store_sensor()
        self._schedule_proposal_tick()
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
        await self.async_refresh()

    def _get_learning_config(self, entry: ConfigEntry) -> dict:
        return dict(entry.options.get("learning", {}))

    async def async_reload_options(self) -> None:
        """Reload options and refresh state."""
        await self.engine.async_reload_options(self.entry)
        self._context_builder.update_config(self._get_learning_config(self.entry))
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
                f"House-state override {action}: "
                f"{previous or 'none'} -> {current or 'none'}."
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
        self.engine.reset_learning_state()
        self._write_event_store_sensor()
        await self.async_refresh()

    async def async_seed_lighting_events(
        self,
        *,
        entity_id: str,
        room_id: str,
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
        offsets = (
            [timedelta(weeks=-2)] * n_week1
            + [timedelta(weeks=-1)] * n_week2
        )

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
                    "action": "on",
                    "brightness": brightness,
                    "color_temp_kelvin": color_temp_kelvin,
                    "rgb_color": None,
                },
            )
            await self._event_store.async_append(event)

        await self._event_store.async_flush()
        self._write_event_store_sensor()
        return count

    async def async_shutdown(self) -> None:
        """Shutdown runtime."""
        self._unsubscribe_state_changes()
        self._cancel_proposal_tick()
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
            if entity_id not in tracked_entities:
                return
            self.hass.async_create_task(
                self.async_request_evaluation(reason=f"state_changed:{entity_id}")
            )

        self._unsub_state_changed = self.hass.bus.async_listen("state_changed", _handle_state_changed)

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

    async def _async_run_proposal_tick(self) -> None:
        try:
            await self._proposal_engine.async_run()
            self._write_event_store_sensor()
            await self.async_refresh()
        finally:
            self._schedule_proposal_tick()

    def _write_proposals_sensor(self, pending_count: int, attributes: dict) -> None:
        self.engine.state.set_sensor("heima_reaction_proposals", pending_count)
        self.engine.state.set_sensor_attributes("heima_reaction_proposals", attributes)

    def _write_event_store_sensor(self) -> None:
        diag = self._event_store.diagnostics()
        self.engine.state.set_sensor("heima_event_store", diag["total_events"])
        self.engine.state.set_sensor_attributes("heima_event_store", diag["by_type"])
