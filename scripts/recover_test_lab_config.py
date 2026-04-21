#!/usr/bin/env python3
"""Recovery script: restore Heima test-lab configuration to the canonical baseline.

Uses all entities defined in packages/heima_test_lab.yaml.
Run this whenever the test-lab HA instance gets into an inconsistent state.

Usage:
    python3 scripts/recover_test_lab_config.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAApiError, HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError

# ---------------------------------------------------------------------------
# Canonical baseline configuration
# All entity IDs must match packages/heima_test_lab.yaml
# ---------------------------------------------------------------------------

GENERAL_CONFIG = {
    "engine_enabled": True,
    "timezone": "Europe/Rome",
    "language": "it",
    "lighting_apply_mode": "scene",
    "vacation_mode_entity": "input_boolean.test_heima_vacation_mode",
    "guest_mode_entity": "input_boolean.test_heima_guest_mode",
    "sleep_window_entity": "binary_sensor.test_heima_sleep_window",
    "relax_mode_entity": "binary_sensor.test_heima_relax_mode",
    "work_window_entity": "binary_sensor.test_heima_work_window",
}

# Entities assigned to room areas so recorder/analyzer room resolution stays stable.
ROOM_AREA_ENTITIES: dict[str, list[str]] = {
    "living": [
        "light.test_heima_living_main",
        "light.test_heima_living_spot",
        "light.test_heima_living_floor",
    ],
    "studio": [
        "light.test_heima_studio_main",
        "light.test_heima_studio_spot",
        "light.test_heima_studio_desk",
        "sensor.test_heima_studio_lux",
        "sensor.test_heima_studio_humidity",
        "sensor.test_heima_studio_temperature",
        "sensor.test_heima_studio_co2",
        "switch.test_heima_studio_fan",
    ],
    "bathroom": [
        "binary_sensor.test_heima_room_bathroom_motion",
        "sensor.test_heima_bathroom_humidity",
        "sensor.test_heima_bathroom_temperature",
        "switch.test_heima_bathroom_fan",
    ],
}

# HA area names (recover_lighting_areas creates them and returns the area_ids)
ROOM_AREA_NAMES: dict[str, str] = {
    "living": "Test Heima Living",
    "studio": "Test Heima Studio",
    "bathroom": "Test Heima Bathroom",
}

ROOMS_BASELINE = [
    {
        "room_id": "studio",
        "display_name": "Studio",
        "area_id": None,  # filled dynamically by recover_rooms() when area_ids provided
        "occupancy_mode": "derived",
        "occupancy_sources": ["binary_sensor.test_heima_room_studio_motion"],
        "learning_sources": [
            "sensor.test_heima_studio_lux",
            "sensor.test_heima_studio_humidity",
            "sensor.test_heima_studio_temperature",
            "sensor.test_heima_studio_co2",
        ],
        "logic": "any_of",
        "on_dwell_s": 5,
        "off_dwell_s": 120,
        "max_on_s": None,
        "signals": [
            {
                "entity_id": "sensor.test_heima_studio_lux",
                "signal_name": "room_lux",
                "device_class": "illuminance",
                "buckets": [
                    {"label": "dark", "upper_bound": 30.0},
                    {"label": "dim", "upper_bound": 100.0},
                    {"label": "ok", "upper_bound": 300.0},
                    {"label": "bright", "upper_bound": None},
                ],
            },
            {
                "entity_id": "sensor.test_heima_studio_humidity",
                "signal_name": "room_humidity",
                "device_class": "humidity",
                "buckets": [
                    {"label": "low", "upper_bound": 40.0},
                    {"label": "ok", "upper_bound": 70.0},
                    {"label": "high", "upper_bound": None},
                ],
                "burst_threshold": 5.0,
                "burst_window_s": 600,
                "burst_direction": "rise",
            },
            {
                "entity_id": "sensor.test_heima_studio_temperature",
                "signal_name": "room_temperature",
                "device_class": "temperature",
                "buckets": [
                    {"label": "cool", "upper_bound": 20.0},
                    {"label": "ok", "upper_bound": 24.0},
                    {"label": "warm", "upper_bound": 27.0},
                    {"label": "hot", "upper_bound": None},
                ],
                "burst_threshold": 1.5,
                "burst_window_s": 600,
                "burst_direction": "rise",
            },
            {
                "entity_id": "sensor.test_heima_studio_co2",
                "signal_name": "room_co2",
                "device_class": "carbon_dioxide",
                "buckets": [
                    {"label": "ok", "upper_bound": 800.0},
                    {"label": "elevated", "upper_bound": 1200.0},
                    {"label": "high", "upper_bound": None},
                ],
            },
        ],
    },
    {
        "room_id": "bathroom",
        "display_name": "Bagno",
        "area_id": None,
        "occupancy_mode": "derived",
        "occupancy_sources": ["binary_sensor.test_heima_room_bathroom_motion"],
        "learning_sources": [
            "sensor.test_heima_bathroom_humidity",
            "sensor.test_heima_bathroom_temperature",
        ],
        "logic": "any_of",
        "on_dwell_s": 5,
        "off_dwell_s": 180,
        "max_on_s": None,
        "signals": [
            {
                "entity_id": "sensor.test_heima_bathroom_humidity",
                "signal_name": "room_humidity",
                "device_class": "humidity",
                "buckets": [
                    {"label": "low", "upper_bound": 40.0},
                    {"label": "ok", "upper_bound": 70.0},
                    {"label": "high", "upper_bound": None},
                ],
                "burst_threshold": 5.0,
                "burst_window_s": 600,
                "burst_direction": "rise",
            },
            {
                "entity_id": "sensor.test_heima_bathroom_temperature",
                "signal_name": "room_temperature",
                "device_class": "temperature",
                "buckets": [
                    {"label": "cool", "upper_bound": 20.0},
                    {"label": "ok", "upper_bound": 24.0},
                    {"label": "warm", "upper_bound": 27.0},
                    {"label": "hot", "upper_bound": None},
                ],
                "burst_threshold": 0.8,
                "burst_window_s": 600,
                "burst_direction": "rise",
            },
        ],
    },
    {
        "room_id": "living",
        "display_name": "Soggiorno",
        "area_id": None,  # filled dynamically by recover_rooms() when area_ids provided
        "occupancy_mode": "derived",
        "occupancy_sources": ["binary_sensor.test_heima_room_living_motion"],
        "learning_sources": [],
        "logic": "any_of",
        "on_dwell_s": 5,
        "off_dwell_s": 120,
        "max_on_s": None,
    },
]

PEOPLE_BASELINE = [
    {
        "slug": "test_user",
        "display_name": "Test User",
        "presence_method": "quorum",
        "sources": ["binary_sensor.test_heima_room_studio_motion"],
        "group_strategy": "quorum",
        "required": 1,
        "arrive_hold_s": 10,
        "leave_hold_s": 120,
        "enable_override": True,
    },
]

PEOPLE_ANON_CONFIG = {
    "enabled": True,
    "sources": ["binary_sensor.test_heima_anonymous_presence"],
    "group_strategy": "quorum",
    "required": 1,
    "arrive_hold_s": 5,
    "leave_hold_s": 60,
}

HEATING_GENERAL = {
    "climate_entity": "climate.test_heima_thermostat",
    "apply_mode": "delegate_to_scheduler",
    "temperature_step": 0.5,
    "manual_override_guard": True,
    "outdoor_temperature_entity": "sensor.test_heima_outdoor_temp",
    "vacation_hours_from_start_entity": "sensor.test_heima_vacation_hours_from_start",
    "vacation_hours_to_end_entity": "sensor.test_heima_vacation_hours_to_end",
    "vacation_total_hours_entity": "sensor.test_heima_vacation_total_hours",
    "vacation_is_long_entity": "binary_sensor.test_heima_vacation_is_long",
}

HEATING_VACATION_BRANCH = {
    "house_state": "vacation",
    "branch_type": "vacation_curve",
    "params": {
        "vacation_ramp_down_h": 8,
        "vacation_ramp_up_h": 1,
        "vacation_min_temp": 16.5,
        "vacation_comfort_temp": 19.5,
        "vacation_min_total_hours_for_ramp": 24,
    },
}

SECURITY_CONFIG = {
    "enabled": True,
    "security_state_entity": "alarm_control_panel.test_heima_alarm",
    "armed_away_value": "armed_away",
    "armed_home_value": "armed_home",
    "camera_evidence_sources": {
        "entry_cam": {
            "id": "entry_cam",
            "display_name": "Front Door Camera",
            "enabled": True,
            "role": "entry",
            "motion_entity": "binary_sensor.test_heima_camera_entry_motion",
            "person_entity": "binary_sensor.test_heima_camera_entry_person",
            "contact_entity": "binary_sensor.test_heima_front_door_contact",
            "return_home_contributor": True,
            "security_priority": "high",
        },
        "garage_cam": {
            "id": "garage_cam",
            "display_name": "Garage Camera",
            "enabled": True,
            "role": "garage",
            "person_entity": "binary_sensor.test_heima_camera_garage_person",
            "vehicle_entity": "binary_sensor.test_heima_camera_garage_vehicle",
            "contact_entity": "binary_sensor.test_heima_garage_door_contact",
            "return_home_contributor": True,
            "security_priority": "high",
        },
    },
}

NOTIFICATIONS_CONFIG = {
    "recipients": {},
    "recipient_groups": {},
    "route_targets": [],
    "enabled_event_categories": ["people", "occupancy", "lighting", "heating", "security"],
    "dedup_window_s": 60,
    "rate_limit_per_key_s": 300,
    "occupancy_mismatch_policy": "smart",
    "occupancy_mismatch_min_derived_rooms": 2,
    "occupancy_mismatch_persist_s": 600,
    "security_mismatch_policy": "smart",
    "security_mismatch_event_mode": "explicit_only",
    "security_mismatch_persist_s": 300,
}

LEARNING_CONFIG = {
    "outdoor_temp_entity": "sensor.test_heima_outdoor_temp",
    "context_signal_entities": [
        "sensor.test_heima_bathroom_humidity",
        "sensor.test_heima_bathroom_temperature",
        "switch.test_heima_bathroom_fan",
        "sensor.test_heima_studio_humidity",
        "sensor.test_heima_studio_temperature",
        "sensor.test_heima_studio_lux",
        "sensor.test_heima_studio_co2",
        "switch.test_heima_studio_fan",
    ],
}

MQTT_BASELINE = {
    "broker": "mosquitto-test",
    "port": 1883,
}


# ---------------------------------------------------------------------------
# Flow client
# ---------------------------------------------------------------------------


class HAFlowClient(HAClient):
    def config_flow_init(self, handler: str) -> dict[str, Any]:
        data = self.post("/api/config/config_entries/flow", {"handler": handler})
        if not isinstance(data, dict):
            raise HAApiError(f"invalid config flow init response for {handler}: {type(data)}")
        return data

    def config_flow_configure(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.post(f"/api/config/config_entries/flow/{flow_id}", payload)
        if not isinstance(data, dict):
            raise HAApiError(f"invalid config flow response: {type(data)}")
        return data

    def options_flow_init(self, entry_id: str) -> dict[str, Any]:
        data = self.post("/api/config/config_entries/options/flow", {"handler": entry_id})
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow init response: {type(data)}")
        return data

    def options_flow_configure(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.post(f"/api/config/config_entries/options/flow/{flow_id}", payload)
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow response: {type(data)}")
        return data

    def options_flow_abort(self, flow_id: str) -> None:
        self.delete(f"/api/config/config_entries/options/flow/{flow_id}")


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    got = result.get("step_id")
    if got != step_id:
        raise RuntimeError(f"expected step_id={step_id!r}, got={got!r} — full result: {result}")


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _flow_save(client: HAFlowClient, flow_id: str) -> None:
    result = _menu_next(client, flow_id, "save")
    if result.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry on save, got: {result}")


def _select_room_for_edit(
    client: HAFlowClient,
    flow_id: str,
    room: dict[str, Any],
) -> dict[str, Any]:
    """Select an existing room in rooms_edit using the current flow contract.

    Older/newer flow implementations may accept either the stable room_id or the
    user-facing selector label like ``Studio [configured]``.
    """
    candidates = [str(room["room_id"])]
    display_name = str(room.get("display_name") or room["room_id"]).strip()
    if display_name:
        candidates.extend(
            [
                f"{display_name} [configured]",
                f"{display_name} [new]",
            ]
        )

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return client.options_flow_configure(flow_id, {"room": candidate})
        except HAApiError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"unable to select room for edit: {room}")


def _select_room_choice(
    client: HAFlowClient,
    flow_id: str,
    room: dict[str, Any],
) -> dict[str, Any]:
    candidates = [str(room.get("room_id") or "").strip()]
    display_name = str(room.get("display_name") or room.get("room_id") or "").strip()
    if display_name:
        candidates.extend(
            [
                f"{display_name} [configured]",
                f"{display_name} [new]",
            ]
        )

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return client.options_flow_configure(flow_id, {"room": candidate})
        except HAApiError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"unable to select room choice: {room}")


def _enter_room_edit_form(
    client: HAFlowClient,
    flow_id: str,
    room: dict[str, Any],
) -> dict[str, Any]:
    """Navigate to rooms_edit_form across current/legacy room edit flows."""
    step = _select_room_for_edit(client, flow_id, room)
    if step.get("step_id") == "rooms_edit_form":
        return step
    if step.get("step_id") == "rooms_edit_actions":
        step = _menu_next(client, flow_id, "rooms_edit_form")
        _expect_step(step, "rooms_edit_form")
        return step
    raise RuntimeError(f"expected rooms_edit_form or rooms_edit_actions, got: {step}")


def _configured_rooms(client: HAFlowClient, entry_id: str) -> list[dict[str, Any]]:
    root = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    entry = root.get("data", {}).get("entry", {}) if isinstance(root, dict) else {}
    if not isinstance(entry, dict) or not entry:
        entry = client.get_entry(entry_id)
    options = entry.get("options", {}) if isinstance(entry, dict) else {}
    if not isinstance(options, dict):
        return []
    rooms = options.get("rooms", [])
    if not isinstance(rooms, list):
        return []
    return [room for room in rooms if isinstance(room, dict)]


# ---------------------------------------------------------------------------
# Recovery steps
# ---------------------------------------------------------------------------


def recover_general(client: HAFlowClient, entry_id: str) -> None:
    print("  → general + house signals")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "general")
    _expect_step(step, "general")
    result = client.options_flow_configure(flow_id, GENERAL_CONFIG)
    _expect_step(result, "init")
    _flow_save(client, flow_id)


def _open_rooms_menu(client: HAFlowClient, entry_id: str) -> tuple[str, dict]:
    """Open a new options flow and navigate to rooms_menu. Returns (flow_id, step)."""
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "rooms_menu")
    _expect_step(step, "rooms_menu")
    return flow_id, step


def recover_lighting_areas(client: HAFlowClient) -> dict[str, str]:
    """Create HA areas for each room and assign light entities.

    Returns {room_id: ha_area_id} so recover_rooms() can set area_id on rooms.
    Uses WebSocket API (area/entity registry are not available via REST).
    """
    area_ids: dict[str, str] = {}
    entry_id = client.find_heima_entry_id()
    current_rooms = {
        str(room.get("room_id") or "").strip(): room
        for room in _configured_rooms(client, entry_id)
        if isinstance(room, dict)
    }
    with HAWebSocketClient(client.base_url, client.token) as ws:
        existing_areas = {
            str(area.get("area_id") or ""): area
            for area in ws.list_areas()
            if isinstance(area, dict)
        }
        for room_id, area_name in ROOM_AREA_NAMES.items():
            preferred_area_id = str(
                (current_rooms.get(room_id, {}) or {}).get("area_id") or ""
            ).strip()
            if preferred_area_id and preferred_area_id in existing_areas:
                area_id = preferred_area_id
            else:
                area_id = ws.get_or_create_area(area_name)
            area_ids[room_id] = area_id
            print(f"     area '{area_name}' → {area_id}")
            entity_ids = ROOM_AREA_ENTITIES.get(room_id, [])
            if not entity_ids:
                print(
                    f"     WARN: no lab entities configured for room {room_id}, skipping area assignment"
                )
                continue
            for entity_id in entity_ids:
                if client.entity_exists(entity_id):
                    ws.assign_entity_to_area(entity_id, area_id)
                    print(f"     {entity_id} → area {area_id}")
                else:
                    print(f"     WARN: {entity_id} not found, skipping area assignment")
    return area_ids


def recover_lighting_areas_with_retry(
    client: HAFlowClient,
    *,
    ws_retries: int,
    ws_retry_delay_s: float,
) -> dict[str, str]:
    """Retry-safe wrapper for lighting area bootstrap over HA WebSocket."""
    last_ws_error: Exception | None = None
    for attempt in range(1, ws_retries + 1):
        try:
            return recover_lighting_areas(client)
        except HAWebSocketError as exc:
            last_ws_error = exc
            if attempt >= ws_retries:
                raise
            print(
                f"  WARN: websocket attempt {attempt}/{ws_retries} failed: {exc}; "
                f"retry in {ws_retry_delay_s:.1f}s"
            )
            time.sleep(ws_retry_delay_s)
    if last_ws_error is not None:
        raise last_ws_error
    return {}


def recover_rooms(
    client: HAFlowClient, entry_id: str, area_ids: dict[str, str] | None = None
) -> None:
    print("  → rooms")
    flow_id, _ = _open_rooms_menu(client, entry_id)

    baseline_room_ids = {str(room["room_id"]) for room in ROOMS_BASELINE}
    current_rooms = _configured_rooms(client, entry_id)
    extra_rooms = [
        room
        for room in current_rooms
        if str(room.get("room_id") or "").strip()
        and str(room.get("room_id") or "").strip() not in baseline_room_ids
    ]
    for room in extra_rooms:
        room_id = str(room.get("room_id") or "").strip()
        print(f"    pruning extra room: {room_id}")
        step = _menu_next(client, flow_id, "rooms_remove")
        _expect_step(step, "rooms_remove")
        result = _select_room_choice(client, flow_id, room)
        _expect_step(result, "rooms_remove_confirm")
        result = client.options_flow_configure(flow_id, {"confirm": True})
        _expect_step(result, "rooms_menu")

    if extra_rooms and area_ids is not None:
        refreshed_area_ids = recover_lighting_areas(client)
        area_ids.clear()
        area_ids.update(refreshed_area_ids)
    if extra_rooms:
        client.options_flow_abort(flow_id)
        flow_id, _ = _open_rooms_menu(client, entry_id)

    for room in ROOMS_BASELINE:
        room_data = dict(room)
        if area_ids and room_data.get("area_id") is None:
            room_data["area_id"] = area_ids.get(room_data["room_id"])
        payload = {k: v for k, v in room_data.items() if v is not None}
        if "signals" in payload:
            payload["signals"] = json.dumps(payload["signals"], ensure_ascii=True, indent=2)

        # Try add first; if duplicate, abort + reopen + edit existing.
        step = _menu_next(client, flow_id, "rooms_add")
        _expect_step(step, "rooms_add")
        result = client.options_flow_configure(flow_id, payload)

        if result.get("step_id") == "rooms_menu":
            continue  # added OK

        if result.get("step_id") in {"rooms_edit_form", "rooms_edit_actions"}:
            client.options_flow_abort(flow_id)
            flow_id, _ = _open_rooms_menu(client, entry_id)
            step = _menu_next(client, flow_id, "rooms_edit")
            _expect_step(step, "rooms_edit")
            step = _enter_room_edit_form(client, flow_id, room)
            result = client.options_flow_configure(flow_id, payload)
            if result.get("step_id") == "rooms_edit_form":
                errors = result.get("errors") or {}
                if errors.get("area_id") == "duplicate" and "area_id" in payload:
                    fallback_payload = dict(payload)
                    fallback_payload.pop("area_id", None)
                    result = client.options_flow_configure(flow_id, fallback_payload)
            _expect_step(result, "rooms_menu")
            continue

        errors = result.get("errors") or {}
        if errors.get("room_id") != "duplicate":
            raise RuntimeError(f"rooms_add unexpected error: {errors}")

        # Room already exists — abort flow, reopen, edit.
        client.options_flow_abort(flow_id)
        flow_id, _ = _open_rooms_menu(client, entry_id)
        step = _menu_next(client, flow_id, "rooms_edit")
        _expect_step(step, "rooms_edit")
        step = _enter_room_edit_form(client, flow_id, room)
        result = client.options_flow_configure(flow_id, payload)
        _expect_step(result, "rooms_menu")

    saved = _menu_next(client, flow_id, "rooms_save")
    if saved.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry from rooms_save, got: {saved}")


def _open_people_menu(client: HAFlowClient, entry_id: str) -> tuple[str, dict]:
    """Open a new options flow and navigate to people_menu. Returns (flow_id, step)."""
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "people_menu")
    _expect_step(step, "people_menu")
    return flow_id, step


def recover_people(client: HAFlowClient, entry_id: str) -> None:
    print("  → people")
    flow_id, _ = _open_people_menu(client, entry_id)

    for person in PEOPLE_BASELINE:
        # Try add first; if duplicate, abort + reopen + edit existing.
        step = _menu_next(client, flow_id, "people_add")
        _expect_step(step, "people_add")
        result = client.options_flow_configure(flow_id, person)

        if result.get("step_id") == "people_menu":
            continue  # added OK

        errors = result.get("errors") or {}
        if errors.get("slug") != "duplicate":
            raise RuntimeError(f"people_add unexpected error: {errors}")

        # Person already exists — abort flow, reopen, edit.
        client.options_flow_abort(flow_id)
        flow_id, _ = _open_people_menu(client, entry_id)
        step = _menu_next(client, flow_id, "people_edit")
        _expect_step(step, "people_edit")
        step = client.options_flow_configure(flow_id, {"person": person["slug"]})
        _expect_step(step, "people_edit_form")
        result = client.options_flow_configure(flow_id, person)
        _expect_step(result, "people_menu")

    # Anonymous presence
    anon_step = _menu_next(client, flow_id, "people_anonymous")
    _expect_step(anon_step, "people_anonymous")
    result = client.options_flow_configure(flow_id, PEOPLE_ANON_CONFIG)
    _expect_step(result, "people_menu")

    saved = _menu_next(client, flow_id, "people_save")
    if saved.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry from people_save, got: {saved}")


def recover_heating(client: HAFlowClient, entry_id: str) -> None:
    print("  → heating + vacation branch")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "heating")
    _expect_step(step, "heating")
    result = client.options_flow_configure(flow_id, HEATING_GENERAL)
    _expect_step(result, "heating_branches_menu")

    # Configure vacation branch
    b = HEATING_VACATION_BRANCH
    step = _menu_next(client, flow_id, "heating_branches_edit")
    _expect_step(step, "heating_branches_edit")
    step = client.options_flow_configure(flow_id, {"house_state": b["house_state"]})
    _expect_step(step, "heating_branch_select")
    step = client.options_flow_configure(flow_id, {"branch": b["branch_type"]})
    _expect_step(step, "heating_branch_edit_form")
    result = client.options_flow_configure(flow_id, b["params"])
    if result.get("errors"):
        raise RuntimeError(f"heating branch validation error: {result['errors']}")
    _expect_step(result, "heating_branches_menu")

    step = _menu_next(client, flow_id, "heating_branches_save")
    _expect_step(step, "init")
    _flow_save(client, flow_id)


def recover_security(client: HAFlowClient, entry_id: str) -> None:
    print("  → security")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "security")
    _expect_step(step, "security")
    result = client.options_flow_configure(flow_id, SECURITY_CONFIG)
    _expect_step(result, "init")
    _flow_save(client, flow_id)


def recover_notifications(client: HAFlowClient, entry_id: str) -> None:
    print("  → notifications")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "notifications")
    _expect_step(step, "notifications")
    result = client.options_flow_configure(flow_id, NOTIFICATIONS_CONFIG)
    _expect_step(result, "init")
    _flow_save(client, flow_id)


def recover_learning(client: HAFlowClient, entry_id: str) -> None:
    print("  → learning")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "learning")
    _expect_step(step, "learning")
    result = client.options_flow_configure(flow_id, LEARNING_CONFIG)
    _expect_step(result, "init")
    _flow_save(client, flow_id)


def recover_mqtt(client: HAFlowClient) -> None:
    print("  → mqtt")
    existing = [
        entry for entry in client.list_config_entries() if str(entry.get("domain") or "") == "mqtt"
    ]
    if existing:
        title = str(existing[0].get("title") or "")
        print(f"    mqtt already configured: {title or '<untitled>'}")
        return

    flow = client.config_flow_init("mqtt")
    flow_id = str(flow.get("flow_id") or "")
    if flow.get("type") != "form" or flow.get("step_id") != "broker" or not flow_id:
        raise RuntimeError(f"unexpected mqtt flow init result: {flow}")

    result = client.config_flow_configure(flow_id, MQTT_BASELINE)
    if result.get("type") != "create_entry":
        raise RuntimeError(f"unexpected mqtt flow result: {result}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore Heima test-lab configuration to baseline")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--ws-retries", type=int, default=5)
    parser.add_argument("--ws-retry-delay-s", type=float, default=2.0)
    parser.add_argument(
        "--section",
        choices=[
            "all",
            "mqtt",
            "general",
            "rooms",
            "people",
            "heating",
            "security",
            "notifications",
            "learning",
            "lighting_areas",
        ],
        default="all",
    )
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()
    print(f"Heima entry_id={entry_id}")

    # When running all sections: create lighting areas first so recover_rooms gets area_ids
    if args.section == "lighting_areas":
        try:
            print("  → lighting_areas")
            area_ids = recover_lighting_areas_with_retry(
                client,
                ws_retries=args.ws_retries,
                ws_retry_delay_s=args.ws_retry_delay_s,
            )
            print(f"  ✓ lighting_areas: {area_ids}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ lighting_areas: {exc}", file=sys.stderr)
            return 1
        print("Recovery complete.")
        return 0

    area_ids: dict[str, str] = {}
    if args.section in {"all", "rooms"}:
        try:
            print("  → lighting_areas (pre-step)")
            area_ids = recover_lighting_areas_with_retry(
                client,
                ws_retries=args.ws_retries,
                ws_retry_delay_s=args.ws_retry_delay_s,
            )
            print(f"  ✓ lighting_areas: {area_ids}")
        except Exception as exc:  # noqa: BLE001
            print(
                f"  WARN: lighting_areas failed ({exc}), continuing without area_ids",
                file=sys.stderr,
            )

    sections = {
        "mqtt": lambda c, _eid: recover_mqtt(c),
        "general": lambda c, eid: recover_general(c, eid),
        "rooms": lambda c, eid: recover_rooms(c, eid, area_ids),
        "people": lambda c, eid: recover_people(c, eid),
        "heating": lambda c, eid: recover_heating(c, eid),
        "security": lambda c, eid: recover_security(c, eid),
        "notifications": lambda c, eid: recover_notifications(c, eid),
        "learning": lambda c, eid: recover_learning(c, eid),
    }

    to_run = list(sections.keys()) if args.section == "all" else [args.section]

    for name in to_run:
        try:
            sections[name](client, entry_id)
            print(f"  ✓ {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {name}: {exc}", file=sys.stderr)
            return 1

    print("Recovery complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
