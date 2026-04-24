"""LightingDomain: lighting intent computation and scene application."""

# mypy: disable-error-code=assignment

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from ..contracts import ApplyStep, HeimaEvent
from ..lighting import pick_scene_for_intent_with_trace, resolve_zone_intent
from ..normalization.service import InputNormalizer
from ..snapshot import DecisionSnapshot
from ..state_store import CanonicalState
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)

_LIGHTING_MIN_SECONDS_BETWEEN_APPLIES = 10


class LightingDomain:
    """Computes lighting intents and builds/executes lighting apply steps."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._room_area_ids: dict[str, str] = {}
        self._lighting_last_scene: dict[str, str] = {}
        self._lighting_last_ts: dict[str, float] = {}
        self._lighting_recent_entity_applies: dict[str, dict[str, Any]] = {}
        self._lighting_recent_scene_applies: dict[str, dict[str, Any]] = {}
        self._lighting_hold_seen_state: dict[str, bool] = {}
        self._lighting_zone_trace: dict[str, dict[str, Any]] = {}
        self._lighting_room_trace: dict[str, list[dict[str, Any]]] = {}
        self._lighting_conflicts_last_eval: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Called on options reload."""
        self._room_area_ids = {}
        self._lighting_last_scene = {}
        self._lighting_last_ts = {}
        self._lighting_recent_entity_applies = {}
        self._lighting_recent_scene_applies = {}
        self._lighting_hold_seen_state = {}
        self._lighting_zone_trace = {}
        self._lighting_room_trace = {}
        self._lighting_conflicts_last_eval = []

    # ------------------------------------------------------------------
    # Diagnostics accessors
    # ------------------------------------------------------------------

    @property
    def zone_trace(self) -> dict[str, dict[str, Any]]:
        return self._lighting_zone_trace

    @property
    def room_trace(self) -> dict[str, list[dict[str, Any]]]:
        return self._lighting_room_trace

    @property
    def conflicts_last_eval(self) -> list[dict[str, Any]]:
        return self._lighting_conflicts_last_eval

    @property
    def last_scene_by_room(self) -> dict[str, str]:
        return self._lighting_last_scene

    @property
    def last_apply_ts_by_room(self) -> dict[str, float]:
        return self._lighting_last_ts

    @property
    def hold_seen_state_by_room(self) -> dict[str, bool]:
        return self._lighting_hold_seen_state

    @property
    def recent_entity_applies(self) -> dict[str, dict[str, Any]]:
        return {
            entity_id: dict(payload)
            for entity_id, payload in self._lighting_recent_entity_applies.items()
        }

    def recent_apply_state(self) -> dict[str, Any]:
        return {
            "rooms": dict(self._lighting_last_ts),
            "entities": self.recent_entity_applies,
            "scenes": {
                scene_entity: dict(payload)
                for scene_entity, payload in self._lighting_recent_scene_applies.items()
            },
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "zone_trace": dict(self._lighting_zone_trace),
            "room_trace": {
                room_id: list(items) for room_id, items in self._lighting_room_trace.items()
            },
            "conflicts_last_eval": list(self._lighting_conflicts_last_eval),
            "last_scene_by_room": dict(self._lighting_last_scene),
            "last_apply_ts_by_room": dict(self._lighting_last_ts),
            "recent_entity_applies": self.recent_entity_applies,
            "recent_scene_applies": {
                scene_entity: dict(payload)
                for scene_entity, payload in self._lighting_recent_scene_applies.items()
            },
            "hold_seen_state_by_room": dict(self._lighting_hold_seen_state),
        }

    # ------------------------------------------------------------------
    # Compute intents
    # ------------------------------------------------------------------

    def compute_intents(
        self,
        *,
        options: dict[str, Any],
        house_state: str,
        occupied_rooms: list[str],
        state: CanonicalState,
        room_configs: dict[str, dict[str, Any]],
        room_occupancy_mode_fn: Any,
    ) -> dict[str, str]:
        """Compute lighting intents per zone."""
        from ...const import OPT_LIGHTING_ZONES

        occupied = set(occupied_rooms)
        lighting_intents: dict[str, str] = {}
        zone_trace: dict[str, dict[str, Any]] = {}

        for zone in options.get(OPT_LIGHTING_ZONES, []):
            zone_id = zone.get("zone_id")
            if not zone_id:
                continue
            rooms = list(zone.get("rooms", []))
            occupancy_capable_rooms = [
                room_id
                for room_id in rooms
                if room_occupancy_mode_fn(room_configs.get(room_id, {})) == "derived"
            ]
            zone_occupied = any(room_id in occupied for room_id in occupancy_capable_rooms)

            select_key = f"heima_lighting_intent_{zone_id}"
            requested_intent = state.get_select(select_key) or "auto"
            final_intent = resolve_zone_intent(requested_intent, house_state, zone_occupied)
            lighting_intents[zone_id] = final_intent
            zone_trace[str(zone_id)] = {
                "zone_id": str(zone_id),
                "rooms": rooms,
                "occupancy_capable_rooms": occupancy_capable_rooms,
                "zone_occupied": zone_occupied,
                "requested_intent": requested_intent,
                "final_intent": final_intent,
                "house_state": house_state,
            }

        self._lighting_zone_trace = zone_trace
        return lighting_intents

    # ------------------------------------------------------------------
    # Build lighting apply steps
    # ------------------------------------------------------------------

    def build_lighting_steps(
        self,
        *,
        snapshot: DecisionSnapshot,
        options: dict[str, Any],
        room_maps: dict[str, dict[str, Any]],
        room_configs: dict[str, dict[str, Any]],
        room_occupancy_mode_fn: Any,
        zone_rooms_fn: Any,
        state: CanonicalState,
        events: EventsDomain,
    ) -> list[ApplyStep]:
        """Build lighting ApplySteps and update trace state."""
        steps: list[ApplyStep] = []
        room_trace: dict[str, list[dict[str, Any]]] = {}
        room_winner_by_room: dict[str, dict[str, Any]] = {}
        conflicts: list[dict[str, Any]] = []
        self._room_area_ids = {
            str(room_id): str(cfg.get("area_id") or "").strip()
            for room_id, cfg in room_configs.items()
            if str(room_id).strip()
        }

        def _enqueue_lighting_step(
            *,
            room_id: str,
            zone_id: str,
            intent: str,
            action: str,
            action_params: dict[str, Any],
            scene_entity: str | None,
            decision: dict[str, Any],
            reason: str,
        ) -> bool:
            winner = room_winner_by_room.get(room_id)
            if winner is not None:
                conflict = {
                    "room_id": room_id,
                    "policy": "first_wins",
                    "winning_zone": winner["zone_id"],
                    "winning_intent": winner["intent"],
                    "winning_scene": winner.get("scene_entity"),
                    "winning_action": winner["action"],
                    "dropped_zone": zone_id,
                    "dropped_intent": intent,
                    "dropped_scene": scene_entity,
                    "dropped_action": action,
                }
                conflicts.append(conflict)
                decision["skip_reason"] = "zone_conflict_dropped"
                decision["conflict"] = dict(conflict)
                room_trace.setdefault(room_id, []).append(decision)
                events.queue_event(
                    HeimaEvent(
                        type="lighting.zone_conflict",
                        key=f"lighting.zone_conflict.{room_id}",
                        severity="warn",
                        title="Lighting zone conflict",
                        message=(
                            f"Multiple lighting zones targeted room '{room_id}' "
                            f"in the same evaluation; first valid step kept."
                        ),
                        context={
                            "room": room_id,
                            "winning_zone": winner["zone_id"],
                            "winning_intent": winner["intent"],
                            "winning_scene": winner.get("scene_entity"),
                            "dropped_zone": zone_id,
                            "dropped_intent": intent,
                            "dropped_scene": scene_entity,
                            "policy": "first_wins",
                        },
                    )
                )
                _LOGGER.warning(
                    "Lighting zone conflict for room '%s': keeping first valid step from zone=%s intent=%s; dropping zone=%s intent=%s",
                    room_id,
                    winner["zone_id"],
                    winner["intent"],
                    zone_id,
                    intent,
                )
                return False

            decision["apply_queued"] = True
            room_trace.setdefault(room_id, []).append(decision)
            room_winner_by_room[room_id] = {
                "zone_id": zone_id,
                "intent": intent,
                "scene_entity": scene_entity,
                "action": action,
                "params": dict(action_params),
            }
            steps.append(
                ApplyStep(
                    domain="lighting",
                    target=room_id,
                    action=action,
                    params=dict(action_params),
                    reason=reason,
                )
            )
            return True

        for zone_id, intent in snapshot.lighting_intents.items():
            for room_id in zone_rooms_fn(zone_id):
                decision: dict[str, Any] = {
                    "zone_id": zone_id,
                    "room_id": room_id,
                    "intent": intent,
                    "hold": False,
                    "room_occupancy_mode": room_occupancy_mode_fn(room_configs.get(room_id, {})),
                    "contributes_to_zone_occupancy": (
                        room_occupancy_mode_fn(room_configs.get(room_id, {})) == "derived"
                    ),
                    "room_mapping_found": False,
                    "action": None,
                    "action_params": None,
                    "scene_entity": None,
                    "scene_resolution": None,
                    "apply_queued": False,
                    "skip_reason": None,
                }
                if self._is_lighting_room_hold_on(room_id, state):
                    decision["hold"] = True
                    decision["skip_reason"] = "manual_hold"
                    room_trace.setdefault(room_id, []).append(decision)
                    continue

                room_map = room_maps.get(room_id)
                if not room_map:
                    decision["skip_reason"] = "no_room_mapping"
                    room_trace.setdefault(room_id, []).append(decision)
                    continue
                decision["room_mapping_found"] = True

                scene_entity, scene_resolution = pick_scene_for_intent_with_trace(room_map, intent)
                decision["scene_entity"] = scene_entity
                decision["scene_resolution"] = scene_resolution
                if not scene_entity:
                    if intent == "off":
                        area_id = str(room_configs.get(room_id, {}).get("area_id") or "").strip()
                        if area_id:
                            action_fingerprint = f"light.turn_off:area:{area_id}"
                            if not self._should_apply_scene(room_id, action_fingerprint):
                                decision["skip_reason"] = "rate_limited_or_duplicate"
                                decision["scene_resolution"] = "fallback:off->light.turn_off(area)"
                                decision["action"] = "light.turn_off"
                                decision["action_params"] = {"area_id": area_id}
                                room_trace.setdefault(room_id, []).append(decision)
                                continue

                            decision["scene_resolution"] = "fallback:off->light.turn_off(area)"
                            decision["action"] = "light.turn_off"
                            decision["action_params"] = {"area_id": area_id}
                            _enqueue_lighting_step(
                                room_id=room_id,
                                zone_id=zone_id,
                                intent=intent,
                                action="light.turn_off",
                                action_params={"area_id": area_id},
                                scene_entity=None,
                                decision=decision,
                                reason="intent:off(area_fallback)",
                            )
                            continue

                    decision["skip_reason"] = "scene_missing"
                    room_trace.setdefault(room_id, []).append(decision)
                    events.queue_event(
                        HeimaEvent(
                            type="lighting.scene_missing",
                            key=f"lighting.scene_missing.{room_id}.{intent}",
                            severity="warn",
                            title="Lighting scene missing",
                            message=(f"No mapped scene for room '{room_id}' and intent '{intent}'"),
                            context={
                                "room": room_id,
                                "intent": intent,
                                "expected_scene": intent,
                            },
                        )
                    )
                    continue

                if not self._should_apply_scene(room_id, scene_entity):
                    decision["skip_reason"] = "rate_limited_or_duplicate"
                    room_trace.setdefault(room_id, []).append(decision)
                    continue

                _enqueue_lighting_step(
                    room_id=room_id,
                    zone_id=zone_id,
                    intent=intent,
                    action="scene.turn_on",
                    action_params={"entity_id": scene_entity},
                    scene_entity=scene_entity,
                    decision=decision,
                    reason=f"intent:{intent}",
                )

        self._lighting_room_trace = room_trace
        self._lighting_conflicts_last_eval = conflicts
        return steps

    # ------------------------------------------------------------------
    # Execute lighting steps
    # ------------------------------------------------------------------

    async def execute_lighting_steps(self, steps: list[ApplyStep]) -> None:
        """Execute lighting ApplySteps (scene.turn_on / light.turn_off)."""
        apply_batch_id = f"lighting-apply:{uuid4()}"
        for step in steps:
            if step.action == "scene.turn_on":
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
                    expected_subject_ids = self._expected_scene_entities(
                        step.target,
                        scene_entity,
                    )
                    self._mark_room_applied(step.target, scene_entity)
                    self._mark_scene_applied(
                        room_id=step.target,
                        scene_entity=scene_entity,
                        expected_subject_ids=expected_subject_ids,
                        correlation_id=apply_batch_id,
                    )
                    for entity_id in expected_subject_ids:
                        self._mark_entity_applied(
                            room_id=step.target,
                            entity_id=entity_id,
                            action="scene.turn_on",
                            correlation_id=apply_batch_id,
                        )
                except ServiceNotFound:
                    _LOGGER.warning(
                        "Skipping lighting apply during startup/race: service scene.turn_on not available"
                    )
                except Exception:
                    _LOGGER.exception("Lighting apply failed for scene '%s'", scene_entity)

            elif step.action == "light.turn_off":
                area_id = step.params.get("area_id")
                entity_id = step.params.get("entity_id")
                if entity_id:
                    # Entity-level turn_off (from ContextConditionedLightingReaction)
                    try:
                        await self._hass.services.async_call(
                            "light",
                            "turn_off",
                            {"entity_id": entity_id},
                            blocking=False,
                        )
                        self._mark_entity_applied(
                            room_id=step.target,
                            entity_id=entity_id,
                            action="light.turn_off",
                            correlation_id=apply_batch_id,
                        )
                    except ServiceNotFound:
                        _LOGGER.warning(
                            "Skipping lighting apply during startup/race: service light.turn_off not available"
                        )
                    except Exception:
                        _LOGGER.exception("Lighting apply failed for entity '%s'", entity_id)
                elif isinstance(area_id, str) and area_id:
                    # Area-level turn_off (from lighting domain)
                    try:
                        await self._hass.services.async_call(
                            "light",
                            "turn_off",
                            {"area_id": area_id},
                            blocking=False,
                        )
                        self._mark_room_applied(step.target, f"light.turn_off:area:{area_id}")
                    except ServiceNotFound:
                        _LOGGER.warning(
                            "Skipping lighting apply during startup/race: service light.turn_off not available"
                        )
                    except Exception:
                        _LOGGER.exception("Lighting apply failed for room area '%s'", area_id)

            elif step.action == "light.turn_on":
                # Entity-level turn_on with attributes (from ContextConditionedLightingReaction)
                entity_id = step.params.get("entity_id")
                if not isinstance(entity_id, str) or not entity_id:
                    continue
                call_params: dict = {"entity_id": entity_id}
                if step.params.get("brightness") is not None:
                    call_params["brightness"] = step.params["brightness"]
                if step.params.get("rgb_color") is not None:
                    call_params["rgb_color"] = step.params["rgb_color"]
                elif step.params.get("color_temp_kelvin") is not None:
                    call_params["color_temp_kelvin"] = step.params["color_temp_kelvin"]
                try:
                    await self._hass.services.async_call(
                        "light",
                        "turn_on",
                        call_params,
                        blocking=False,
                    )
                    self._mark_entity_applied(
                        room_id=step.target,
                        entity_id=entity_id,
                        action="light.turn_on",
                        correlation_id=apply_batch_id,
                    )
                except ServiceNotFound:
                    _LOGGER.warning(
                        "Skipping lighting apply during startup/race: service light.turn_on not available"
                    )
                except Exception:
                    _LOGGER.exception("Lighting apply failed for entity '%s'", entity_id)

    # ------------------------------------------------------------------
    # Hold events
    # ------------------------------------------------------------------

    async def emit_hold_events(
        self,
        *,
        room_maps: dict[str, dict[str, Any]],
        state: CanonicalState,
        events: EventsDomain,
    ) -> None:
        for room_id, room_map in room_maps.items():
            if not room_map.get("enable_manual_hold", True):
                continue

            current = self._is_lighting_room_hold_on(room_id, state)
            if room_id not in self._lighting_hold_seen_state:
                self._lighting_hold_seen_state[room_id] = current
                continue

            previous = self._lighting_hold_seen_state[room_id]
            if previous == current:
                continue

            self._lighting_hold_seen_state[room_id] = current
            events.queue_event(
                HeimaEvent(
                    type="lighting.hold_on" if current else "lighting.hold_off",
                    key=f"lighting.hold.{room_id}",
                    severity="info",
                    title="Lighting hold enabled" if current else "Lighting hold disabled",
                    message=(
                        f"Manual lighting hold {'enabled' if current else 'disabled'} "
                        f"for room '{room_id}'"
                    ),
                    context={"room": room_id},
                )
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_lighting_room_hold_on(self, room_id: str, state: CanonicalState) -> bool:
        key = f"heima_lighting_hold_{room_id}"
        return bool(state.get_binary(key))

    def _should_apply_scene(self, room_id: str, scene_entity: str) -> bool:
        now = time.monotonic()
        last_scene = self._lighting_last_scene.get(room_id)
        last_ts = self._lighting_last_ts.get(room_id, 0.0)
        if last_scene == scene_entity and (now - last_ts) < _LIGHTING_MIN_SECONDS_BETWEEN_APPLIES:
            return False
        return True

    def _mark_room_applied(self, room_id: str, scene_entity: str) -> None:
        self._lighting_last_scene[room_id] = scene_entity
        self._lighting_last_ts[room_id] = time.monotonic()

    def _mark_entity_applied(
        self,
        *,
        room_id: str,
        entity_id: str,
        action: str,
        correlation_id: str | None = None,
    ) -> None:
        applied_ts = time.monotonic()
        self._lighting_last_scene[room_id] = f"{action}:entity:{entity_id}"
        self._lighting_last_ts[room_id] = applied_ts
        self._lighting_recent_entity_applies[entity_id] = {
            "room_id": room_id,
            "action": action,
            "applied_ts": applied_ts,
            "correlation_id": correlation_id,
        }

    def _mark_scene_applied(
        self,
        *,
        room_id: str,
        scene_entity: str,
        expected_subject_ids: list[str],
        correlation_id: str | None = None,
    ) -> None:
        applied_ts = time.monotonic()
        self._lighting_recent_scene_applies[scene_entity] = {
            "room_id": room_id,
            "scene_entity": scene_entity,
            "action": "scene.turn_on",
            "expected_domains": ["light"],
            "expected_subject_ids": list(expected_subject_ids),
            "expected_entity_ids": list(expected_subject_ids),
            "applied_ts": applied_ts,
            "correlation_id": correlation_id,
        }

    def _expected_scene_entities(self, room_id: str, scene_entity: str) -> list[str]:
        """Best-effort expansion of a scene to concrete light entities.

        Prefer scene-declared members when available on the HA scene state; fall back
        to room-scoped light entities otherwise.
        """
        scene_state = self._hass.states.get(scene_entity)
        if scene_state is not None:
            raw_entities = getattr(scene_state, "attributes", {}).get("entity_id")
            if isinstance(raw_entities, (list, tuple)):
                scene_lights = [
                    str(entity_id).strip()
                    for entity_id in raw_entities
                    if isinstance(entity_id, str) and str(entity_id).startswith("light.")
                ]
                if scene_lights:
                    return sorted(set(scene_lights))
        return self.expected_room_light_entities(room_id)

    def expected_room_light_entities(self, room_id: str) -> list[str]:
        """Best-effort concrete light entities for a room via its mapped HA area."""
        room_id = str(room_id or "").strip()
        if not room_id:
            return []

        area_id = self._room_area_ids.get(room_id, "")
        if not area_id:
            return []

        try:
            from homeassistant.helpers.entity_registry import async_get as async_get_er

            entity_registry = async_get_er(self._hass)
        except Exception:
            return []

        entity_ids: list[str] = []
        for entry in entity_registry.entities.values():
            if not entry.entity_id.startswith("light."):
                continue
            if entry.area_id != area_id:
                continue
            entity_ids.append(entry.entity_id)
        return sorted(entity_ids)
