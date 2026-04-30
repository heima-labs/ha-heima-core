"""OccupancyDomain: room occupancy computation and consistency events."""

# mypy: disable-error-code=arg-type

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.core import HomeAssistant

from ...const import OPT_ROOMS
from ...room_sources import room_occupancy_source_entity_ids
from ..contracts import HeimaEvent
from ..normalization.config import (
    ROOM_OCCUPANCY_STRATEGY_CONTRACT,
    build_signal_set_strategy_cfg_for_contract,
)
from ..normalization.service import InputNormalizer
from .events import EventsDomain

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OccupancyResult:
    """Result of OccupancyDomain.compute()."""

    occupied_rooms: list[str]
    sensorized_room_count: int = 0


class OccupancyDomain:
    """Computes room occupancy and queues occupancy consistency events."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._occupancy_room_candidate_state: dict[str, str] = {}
        self._occupancy_room_candidate_since: dict[str, float] = {}
        self._occupancy_room_effective_state: dict[str, str] = {}
        self._occupancy_room_effective_since: dict[str, float] = {}
        self._occupancy_room_trace: dict[str, dict[str, Any]] = {}
        self._occupancy_home_no_room_since: float | None = None
        self._occupancy_home_no_room_emitted: bool = False
        self._occupancy_room_no_home_since: dict[str, float] = {}
        self._occupancy_room_no_home_emitted: set[str] = set()

    def reset(self) -> None:
        """Called on options reload."""
        self._occupancy_room_candidate_state = {}
        self._occupancy_room_candidate_since = {}
        self._occupancy_room_effective_state = {}
        self._occupancy_room_effective_since = {}
        self._occupancy_room_trace = {}
        self._occupancy_home_no_room_since = None
        self._occupancy_home_no_room_emitted = False
        self._occupancy_room_no_home_since = {}
        self._occupancy_room_no_home_emitted = set()

    @property
    def room_trace(self) -> dict[str, dict[str, Any]]:
        return self._occupancy_room_trace

    def diagnostics(self) -> dict[str, Any]:
        return {
            "room_trace": dict(self._occupancy_room_trace),
        }

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    def compute(
        self,
        options: dict[str, Any],
        events: EventsDomain,
        mismatch_cfg: dict[str, Any],
        schedule_recheck: Callable[..., None],
        state: Any,  # CanonicalState - avoided circular to keep simple
        now: str,
        signals: list[Any] | None = None,  # OccupancySignal stub — not applied in v2
    ) -> OccupancyResult:
        del signals
        occupied_rooms: list[str] = []
        sensorized_room_count = 0

        for room in options.get(OPT_ROOMS, []):
            room_id = room.get("room_id")
            if not room_id:
                continue
            if self._room_occupancy_mode(room) == "derived" and room_occupancy_source_entity_ids(
                room
            ):
                sensorized_room_count += 1
            is_occupied, occ_trace = self._compute_room_occupancy(room, schedule_recheck, events)
            prev_value = state.get_binary(f"heima_occupancy_{room_id}")
            state.set_binary(f"heima_occupancy_{room_id}", is_occupied)
            state.set_sensor(
                f"heima_occupancy_{room_id}_source",
                "none"
                if self._room_occupancy_mode(room) == "none"
                else ",".join(room_occupancy_source_entity_ids(room)),
            )
            if prev_value != is_occupied:
                state.set_sensor(f"heima_occupancy_{room_id}_last_change", now)
            self._occupancy_room_trace[str(room_id)] = occ_trace
            if is_occupied:
                occupied_rooms.append(room_id)

        return OccupancyResult(
            occupied_rooms=occupied_rooms,
            sensorized_room_count=sensorized_room_count,
        )

    # ------------------------------------------------------------------
    # Consistency events
    # ------------------------------------------------------------------

    def queue_occupancy_consistency_events(
        self,
        *,
        anyone_home: bool,
        occupied_rooms: list[str],
        options: dict[str, Any],
        mismatch_cfg: dict[str, Any],
        schedule_recheck: Callable[..., None],
        events: EventsDomain,
    ) -> None:
        policy = mismatch_cfg["policy"]
        if policy == "off":
            self._occupancy_home_no_room_since = None
            self._occupancy_home_no_room_emitted = False
            self._occupancy_room_no_home_since.clear()
            self._occupancy_room_no_home_emitted.clear()
            return

        derived_rooms = [
            str(room.get("room_id"))
            for room in options.get(OPT_ROOMS, [])
            if room.get("room_id") and self._room_occupancy_mode(room) == "derived"
        ]
        derived_room_count = len(derived_rooms)
        persist_s = mismatch_cfg["persist_s"]
        min_derived_rooms = mismatch_cfg["min_derived_rooms"]

        home_no_room_condition = anyone_home and not occupied_rooms
        if policy == "smart" and derived_room_count < min_derived_rooms:
            home_no_room_condition = False

        if self._persistent_condition_ready(
            key="home_no_room",
            active=home_no_room_condition,
            persist_s=0 if policy == "strict" else persist_s,
            schedule_recheck=schedule_recheck,
        ):
            events.queue_event(
                HeimaEvent(
                    type="occupancy.inconsistency_home_no_room",
                    key="occupancy.inconsistency_home_no_room",
                    severity="info",
                    title="Occupancy inconsistency",
                    message=(
                        "Presence says someone is home, but no derived room is currently occupied."
                    ),
                    context={
                        "anyone_home": anyone_home,
                        "occupied_rooms": list(occupied_rooms),
                        "policy": policy,
                        "derived_room_count": derived_room_count,
                        "persist_s": 0 if policy == "strict" else persist_s,
                    },
                )
            )

        room_sources = {
            str(room.get("room_id")): room_occupancy_source_entity_ids(room)
            for room in options.get(OPT_ROOMS, [])
            if room.get("room_id")
        }

        room_configs = {
            str(room.get("room_id")): dict(room)
            for room in options.get(OPT_ROOMS, [])
            if room.get("room_id")
        }
        active_room_no_home: set[str] = set()
        if occupied_rooms and not anyone_home:
            for room_id in occupied_rooms:
                room_cfg = room_configs.get(room_id, {})
                if self._room_occupancy_mode(room_cfg) != "derived":
                    self._reset_persistent_room_condition(room_id)
                    continue
                active_room_no_home.add(room_id)
                if not self._persistent_condition_ready(
                    key=f"room_no_home:{room_id}",
                    active=True,
                    persist_s=0 if policy == "strict" else persist_s,
                    schedule_recheck=schedule_recheck,
                ):
                    continue
                events.queue_event(
                    HeimaEvent(
                        type="occupancy.inconsistency_room_no_home",
                        key=f"occupancy.inconsistency_room_no_home.{room_id}",
                        severity="info",
                        title="Occupancy inconsistency",
                        message=(
                            f"Room '{room_id}' is occupied by room logic, but global presence says nobody is home."
                        ),
                        context={
                            "room": room_id,
                            "anyone_home": anyone_home,
                            "source_entities": room_sources.get(room_id, []),
                            "policy": policy,
                            "persist_s": 0 if policy == "strict" else persist_s,
                        },
                    )
                )

        for room_id in list(self._occupancy_room_no_home_since.keys()):
            if room_id not in active_room_no_home:
                self._reset_persistent_room_condition(room_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_room_occupancy(
        self,
        room_cfg: dict[str, Any],
        schedule_recheck: Callable[..., None],
        events: EventsDomain,
    ) -> tuple[bool, dict[str, Any]]:
        room_id = str(room_cfg.get("room_id", ""))
        mode = self._room_occupancy_mode(room_cfg)
        if mode == "none":
            return False, {
                "room_id": room_id,
                "occupancy_mode": "none",
                "source_observations": [],
                "fused_observation": None,
                "plugin_id": None,
                "candidate_state": "off",
                "candidate_since": None,
                "effective_state": "off",
                "effective_since": None,
                "on_dwell_s": None,
                "off_dwell_s": None,
                "max_on_s": None,
                "forced_off_by_max_on": False,
            }

        sources = room_occupancy_source_entity_ids(room_cfg)
        if not sources:
            return False, {
                "room_id": room_id,
                "occupancy_mode": mode,
                "source_observations": [],
                "fused_observation": None,
                "plugin_id": None,
                "candidate_state": "unknown",
                "candidate_since": None,
                "effective_state": "off",
                "effective_since": None,
                "on_dwell_s": int(room_cfg.get("on_dwell_s", 0)),
                "off_dwell_s": int(room_cfg.get("off_dwell_s", 120)),
                "max_on_s": room_cfg.get("max_on_s"),
                "forced_off_by_max_on": False,
            }

        logic = str(room_cfg.get("logic", "any_of"))
        observations = [self._normalizer.presence(entity_id) for entity_id in sources]
        strategy_cfg = build_signal_set_strategy_cfg_for_contract(
            contract=ROOM_OCCUPANCY_STRATEGY_CONTRACT,
            strategy=logic,
            weight_threshold=room_cfg.get("weight_threshold"),
            source_weights=room_cfg.get("source_weights"),
            fallback_state="off",
        )
        fused = self._normalizer.derive(
            kind="presence",
            inputs=observations,
            strategy_cfg=strategy_cfg,
            context={"room_id": room_id},
        )

        candidate_state = fused.state if fused.state in {"on", "off"} else "unknown"
        now = time.monotonic()
        previous_candidate = self._occupancy_room_candidate_state.get(room_id)
        if previous_candidate != candidate_state:
            self._occupancy_room_candidate_state[room_id] = candidate_state
            self._occupancy_room_candidate_since[room_id] = now

        candidate_since = self._occupancy_room_candidate_since.get(room_id, now)
        on_dwell_s = int(room_cfg.get("on_dwell_s", 0))
        off_dwell_s = int(room_cfg.get("off_dwell_s", 120))
        max_on_s_raw = room_cfg.get("max_on_s")
        max_on_s = int(max_on_s_raw) if max_on_s_raw not in (None, "") else None

        effective_state = self._occupancy_room_effective_state.get(room_id)
        if effective_state is None:
            effective_state = "on" if candidate_state == "on" else "off"
            self._occupancy_room_effective_state[room_id] = effective_state
            self._occupancy_room_effective_since[room_id] = now
        elif candidate_state in {"on", "off"} and candidate_state != effective_state:
            dwell = on_dwell_s if candidate_state == "on" else off_dwell_s
            dwell = max(0, dwell)
            if (now - candidate_since) >= dwell:
                effective_state = candidate_state
                self._occupancy_room_effective_state[room_id] = effective_state
                self._occupancy_room_effective_since[room_id] = now
            elif dwell > 0:
                deadline = candidate_since + dwell
                schedule_recheck(
                    job_id=f"occupancy:dwell:{room_id}",
                    deadline=deadline,
                    owner="occupancy",
                    label=f"Occupancy dwell transition ({room_id})",
                )

        forced_off_by_max_on = False
        effective_since = self._occupancy_room_effective_since.get(room_id, now)
        if (
            max_on_s is not None
            and max_on_s > 0
            and effective_state == "on"
            and candidate_state == "off"
        ):
            if (now - effective_since) >= max_on_s:
                forced_off_by_max_on = True
                effective_state = "off"
                self._occupancy_room_effective_state[room_id] = "off"
                self._occupancy_room_effective_since[room_id] = now
                events.queue_event(
                    HeimaEvent(
                        type="occupancy.max_on_timeout",
                        key=f"occupancy.max_on_timeout.{room_id}",
                        severity="info",
                        title="Room occupancy max-on timeout",
                        message=f"Room '{room_id}' occupancy forced off after max_on_s timeout.",
                        context={"room": room_id, "max_on_s": max_on_s},
                    )
                )
            else:
                schedule_recheck(
                    job_id=f"occupancy:max_on:{room_id}",
                    deadline=effective_since + max_on_s,
                    owner="occupancy",
                    label=f"Occupancy max_on timeout ({room_id})",
                )
        effective_since = self._occupancy_room_effective_since.get(room_id, now)

        trace = {
            "room_id": room_id,
            "occupancy_mode": mode,
            "source_observations": [obs.as_dict() for obs in observations],
            "fused_observation": fused.as_dict(),
            "plugin_id": fused.plugin_id,
            "used_plugin_fallback": fused.reason == "plugin_error_fallback",
            "configured_source_weights": (
                dict(room_cfg.get("source_weights", {})) if logic == "weighted_quorum" else {}
            ),
            "effective_source_weights": dict(fused.evidence.get("weights", {}))
            if isinstance(fused.evidence, dict)
            else {},
            "source_weight_contributions": [
                {
                    "entity_id": obs.source_entity_id,
                    "state": obs.state,
                    "weight": (
                        fused.evidence.get("weights", {}).get(obs.source_entity_id or "", 1.0)
                        if isinstance(fused.evidence, dict)
                        else 1.0
                    ),
                    "contributes_to_on": obs.state == "on",
                }
                for obs in observations
            ],
            "candidate_state": candidate_state,
            "candidate_since": candidate_since,
            "effective_state": effective_state,
            "effective_since": effective_since,
            "on_dwell_s": on_dwell_s,
            "off_dwell_s": off_dwell_s,
            "max_on_s": max_on_s,
            "forced_off_by_max_on": forced_off_by_max_on,
        }
        return effective_state == "on", trace

    def _room_occupancy_mode(self, room_cfg: dict[str, Any]) -> str:
        mode = str(room_cfg.get("occupancy_mode", "derived") or "derived")
        return mode if mode in {"derived", "none"} else "derived"

    def _persistent_condition_ready(
        self,
        *,
        key: str,
        active: bool,
        persist_s: int,
        schedule_recheck: Callable[..., None],
    ) -> bool:
        now = time.monotonic()
        if key == "home_no_room":
            if not active:
                self._occupancy_home_no_room_since = None
                self._occupancy_home_no_room_emitted = False
                return False
            if self._occupancy_home_no_room_since is None:
                self._occupancy_home_no_room_since = now
                self._occupancy_home_no_room_emitted = False
            if self._occupancy_home_no_room_emitted:
                return False
            if persist_s <= 0 or (now - self._occupancy_home_no_room_since) >= persist_s:
                self._occupancy_home_no_room_emitted = True
                return True
            schedule_recheck(
                job_id="occupancy:home_no_room",
                deadline=self._occupancy_home_no_room_since + persist_s,
                owner="occupancy",
                label="Occupancy home-no-room persistence",
            )
            return False

        if key.startswith("room_no_home:"):
            room_id = key.split(":", 1)[1]
            if not active:
                self._reset_persistent_room_condition(room_id)
                return False
            if room_id not in self._occupancy_room_no_home_since:
                self._occupancy_room_no_home_since[room_id] = now
                self._occupancy_room_no_home_emitted.discard(room_id)
            if room_id in self._occupancy_room_no_home_emitted:
                return False
            if persist_s <= 0 or (now - self._occupancy_room_no_home_since[room_id]) >= persist_s:
                self._occupancy_room_no_home_emitted.add(room_id)
                return True
            schedule_recheck(
                job_id=f"occupancy:room_no_home:{room_id}",
                deadline=self._occupancy_room_no_home_since[room_id] + persist_s,
                owner="occupancy",
                label=f"Occupancy room-no-home persistence ({room_id})",
            )
            return False

        return False

    def _reset_persistent_room_condition(self, room_id: str) -> None:
        self._occupancy_room_no_home_since.pop(room_id, None)
        self._occupancy_room_no_home_emitted.discard(room_id)
