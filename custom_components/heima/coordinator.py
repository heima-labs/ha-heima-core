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
    create_builtin_learning_plugin_registry,
)
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
from .runtime.plugin_contracts import AnomalySignal
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
        for plugin in self.engine.builtin_domain_plugins():
            self.engine.register_plugin(plugin)
        self.engine.finalize_dag()
        self._event_store = EventStore(hass)
        self._context_builder = ContextBuilder(hass, self._get_learning_config(entry))
        self.engine.set_context_builder(self._context_builder)
        self.engine.register_behavior(
            EventRecorderBehavior(hass, self._event_store, self._context_builder)
        )
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
        for plugin in self._learning_plugin_registry.analyzers():
            self._proposal_engine.register_analyzer(plugin)
        self._finding_router = FindingRouter(
            proposal_engine=self._proposal_engine,
            anomaly_handler=self._async_handle_anomaly_finding,
        )
        self._unsub_proposal_tick = None
        self._unsub_state_changed = None
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
        await self._proposal_engine.async_initialize()
        await self.engine.async_initialize()
        if changed:
            await self.engine.async_reload_options(
                self.entry, changed_keys={"people_named", "rooms"}
            )
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
        self.engine.reset_learning_state()
        self._write_event_store_sensor()
        await self.async_refresh()

    async def async_run_learning_now(self) -> None:
        """Run learning analyzers immediately and refresh exposed state."""
        await self._proposal_engine.async_run()
        self._write_event_store_sensor()
        await self.async_refresh()

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

    async def _async_run_proposal_tick(self) -> None:
        try:
            summary, changed = await self._async_reconcile_ha_backed_objects()
            if changed:
                await self._async_emit_reconciliation_events(summary)
            await self._proposal_engine.async_run()
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
