#!/usr/bin/env python3
"""Audit Heima lighting room/area mapping against Home Assistant light registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    data = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid diagnostics payload: {type(data)}")
    entry = _as_dict(_as_dict(data.get("data")).get("entry"))
    options = _as_dict(entry.get("options"))
    return options


def _room_area_map(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rooms = _as_list(options.get("rooms"))
    lighting_rooms = {
        str(item.get("room_id")): item
        for item in _as_list(options.get("lighting_rooms"))
        if isinstance(item, dict) and str(item.get("room_id", "")).strip()
    }
    result: dict[str, dict[str, Any]] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id", "")).strip()
        if not room_id:
            continue
        result[room_id] = {
            "room_id": room_id,
            "display_name": str(room.get("display_name", "")).strip(),
            "area_id": str(room.get("area_id", "")).strip(),
            "occupancy_mode": str(room.get("occupancy_mode", "")).strip(),
            "lighting_configured": room_id in lighting_rooms,
        }
    return result


def _area_name_map(ws: HAWebSocketClient) -> dict[str, str]:
    return {
        str(area.get("area_id")): str(area.get("name"))
        for area in ws.list_areas()
        if isinstance(area, dict) and str(area.get("area_id", "")).strip()
    }


def _light_registry(ws: HAWebSocketClient) -> list[dict[str, Any]]:
    result = ws.call("config/entity_registry/list")
    entries = result if isinstance(result, list) else []
    lights: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entity_id = str(entry.get("entity_id", "")).strip()
        if not entity_id.startswith("light."):
            continue
        lights.append(entry)
    return sorted(lights, key=lambda item: str(item.get("entity_id", "")))


def _device_area_map(ws: HAWebSocketClient) -> dict[str, str]:
    result = ws.call("config/device_registry/list")
    devices = result if isinstance(result, list) else []
    mapping: dict[str, str] = {}
    for device in devices:
        if not isinstance(device, dict):
            continue
        device_id = str(device.get("id", "")).strip()
        area_id = str(device.get("area_id") or "").strip()
        if device_id and area_id:
            mapping[device_id] = area_id
    return mapping


def _fetch_registry_with_retry(
    *,
    ha_url: str,
    ha_token: str,
    ws_retries: int,
    ws_retry_delay_s: float,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    last_error: Exception | None = None
    for attempt in range(1, ws_retries + 1):
        try:
            with HAWebSocketClient(ha_url, ha_token) as ws:
                return _area_name_map(ws), _light_registry(ws), _device_area_map(ws)
        except HAWebSocketError as exc:
            last_error = exc
            if attempt >= ws_retries:
                break
            print(
                f"WARN: websocket attempt {attempt}/{ws_retries} failed: {exc}; "
                f"retry in {ws_retry_delay_s:.1f}s",
                file=sys.stderr,
            )
            time.sleep(ws_retry_delay_s)
    raise RuntimeError(
        "unable to read HA area/entity registry over websocket; "
        f"last error: {last_error}. Try an internal HA URL/host that supports /api/websocket."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Heima lighting room/area mapping")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--show-all-lights", action="store_true", help="Print all light registry rows")
    parser.add_argument("--ws-retries", type=int, default=3)
    parser.add_argument("--ws-retry-delay-s", type=float, default=2.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    options = _entry_options(client, entry_id)
    room_map = _room_area_map(options)

    area_names, light_entries, device_area_map = _fetch_registry_with_retry(
        ha_url=args.ha_url,
        ha_token=args.ha_token,
        ws_retries=args.ws_retries,
        ws_retry_delay_s=args.ws_retry_delay_s,
    )

    expected_area_to_room = {
        room["area_id"]: room_id
        for room_id, room in room_map.items()
        if room["area_id"]
    }

    recorder_matches: dict[str, list[str]] = {room_id: [] for room_id in room_map}
    entity_area_matches: dict[str, list[str]] = {room_id: [] for room_id in room_map}
    device_area_matches: dict[str, list[str]] = {room_id: [] for room_id in room_map}
    unassigned_lights: list[str] = []
    area_mismatch_lights: list[dict[str, str]] = []

    for light in light_entries:
        entity_id = str(light.get("entity_id", "")).strip()
        entity_area_id = str(light.get("area_id") or "").strip()
        device_id = str(light.get("device_id") or "").strip()
        device_area_id = device_area_map.get(device_id, "")
        effective_area_id = entity_area_id or device_area_id
        if not effective_area_id:
            unassigned_lights.append(entity_id)
            continue
        room_id = expected_area_to_room.get(effective_area_id)
        if room_id:
            recorder_matches.setdefault(room_id, []).append(entity_id)
            if entity_area_id:
                entity_area_matches.setdefault(room_id, []).append(entity_id)
            elif device_area_id:
                device_area_matches.setdefault(room_id, []).append(entity_id)
        else:
            area_mismatch_lights.append(
                {
                    "entity_id": entity_id,
                    "entity_area_id": entity_area_id,
                    "device_area_id": device_area_id,
                    "effective_area_id": effective_area_id,
                    "area_name": area_names.get(effective_area_id, ""),
                }
            )

    print("Heima lighting area audit")
    print(f"- heima_rooms: {len(room_map)}")
    print(f"- lighting_rooms_configured: {sum(1 for room in room_map.values() if room['lighting_configured'])}")
    print(f"- light_registry_entities: {len(light_entries)}")
    print(f"- expected_area_bound_rooms: {len(expected_area_to_room)}")
    print(f"- lights_without_area: {len(unassigned_lights)}")
    print(f"- lights_in_non_heima_areas: {len(area_mismatch_lights)}")
    print(f"- entity_area_matches: {sum(len(v) for v in entity_area_matches.values())}")
    print(f"- device_area_fallback_matches: {sum(len(v) for v in device_area_matches.values())}")

    print("- room_area_bindings:")
    for room_id, room in sorted(room_map.items()):
        matched = sorted(recorder_matches.get(room_id, []))
        matched_entity = sorted(entity_area_matches.get(room_id, []))
        matched_device = sorted(device_area_matches.get(room_id, []))
        area_id = room["area_id"]
        area_name = area_names.get(area_id, "") if area_id else ""
        print(
            "  - "
            f"{room_id}: area_id={area_id or '<missing>'} "
            f"area_name={area_name or '<unknown>'} "
            f"lighting_configured={room['lighting_configured']} "
            f"matched_lights={len(matched)} "
            f"(entity_area={len(matched_entity)}, device_area={len(matched_device)})"
        )
        if matched:
            print(f"    lights={matched}")

    if unassigned_lights:
        print("- lights_without_area_list:")
        for entity_id in unassigned_lights:
            print(f"  - {entity_id}")

    if area_mismatch_lights:
        print("- lights_in_non_heima_areas_list:")
        for item in area_mismatch_lights:
            print(
                "  - "
                f"{item['entity_id']} effective_area_id={item['effective_area_id'] or '<missing>'} "
                f"entity_area_id={item['entity_area_id'] or '<missing>'} "
                f"device_area_id={item['device_area_id'] or '<missing>'} "
                f"area_name={item['area_name'] or '<unknown>'}"
            )

    if args.show_all_lights:
        print("\n== ALL_LIGHT_REGISTRY_ENTRIES ==")
        payload = [
            {
                "entity_id": str(entry.get("entity_id", "")),
                "entity_area_id": str(entry.get("area_id") or ""),
                "device_area_id": device_area_map.get(str(entry.get("device_id") or ""), ""),
                "effective_area_id": str(entry.get("area_id") or "")
                or device_area_map.get(str(entry.get("device_id") or ""), ""),
                "area_name": area_names.get(
                    str(entry.get("area_id") or "")
                    or device_area_map.get(str(entry.get("device_id") or ""), ""),
                    "",
                ),
                "device_id": str(entry.get("device_id") or ""),
                "disabled_by": entry.get("disabled_by"),
                "hidden_by": entry.get("hidden_by"),
            }
            for entry in light_entries
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
