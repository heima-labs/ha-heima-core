#!/usr/bin/env python3
"""Live check: configured workday evidence drives house_state=working."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


class HAFlowClient(HAClient):
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


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    got = result.get("step_id")
    if got != step_id:
        raise RuntimeError(f"expected step_id={step_id!r}, got={got!r}: {result}")


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    data = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    entry = data.get("data", {}).get("entry", {}) if isinstance(data, dict) else {}
    options = entry.get("options", {}) if isinstance(entry, dict) else {}
    if not isinstance(options, dict):
        raise RuntimeError(f"invalid entry options payload: {type(options)}")
    return options


def _engine_house_state(client: HAClient, entry_id: str) -> dict[str, Any]:
    data = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    runtime = data.get("data", {}).get("runtime", {}) if isinstance(data, dict) else {}
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    house_state = engine.get("house_state", {}) if isinstance(engine, dict) else {}
    if not isinstance(house_state, dict):
        raise RuntimeError(f"invalid house_state diagnostics payload: {type(house_state)}")
    return house_state


def _resolve_entity_id(client: HAClient, *, exact: str, prefix: str) -> str:
    if client.entity_exists(exact):
        state = str(client.get_state(exact).get("state") or "").strip().lower()
        if state not in {"unavailable", "unknown"}:
            return exact
    matches: list[tuple[str, str]] = []
    for item in client.all_states():
        entity_id = str(item.get("entity_id") or "")
        if entity_id == exact or entity_id.startswith(prefix):
            matches.append((entity_id, str(item.get("state") or "").strip().lower()))
    if not matches:
        raise RuntimeError(f"no entity found for exact={exact!r} prefix={prefix!r}")
    for entity_id, state in matches:
        if state not in {"unavailable", "unknown"}:
            return entity_id
    return matches[0][0]


def _normalized_general_payload(options: dict[str, Any]) -> dict[str, Any]:
    house_signals = options.get("house_signals", {})
    if not isinstance(house_signals, dict):
        house_signals = {}
    house_state_cfg = options.get("house_state_config", {})
    if not isinstance(house_state_cfg, dict):
        house_state_cfg = {}
    payload = {
        "engine_enabled": bool(options.get("engine_enabled", True)),
        "timezone": str(options.get("timezone", "UTC")),
        "language": str(options.get("language", "en")),
        "lighting_apply_mode": str(options.get("lighting_apply_mode", "scene")),
        "media_active_entities": [
            str(entity_id).strip()
            for entity_id in list(house_state_cfg.get("media_active_entities", []) or [])
            if str(entity_id).strip()
        ],
        "sleep_enter_min": int(house_state_cfg.get("sleep_enter_min", 10)),
        "sleep_exit_min": int(house_state_cfg.get("sleep_exit_min", 2)),
        "work_enter_min": int(house_state_cfg.get("work_enter_min", 5)),
        "relax_enter_min": int(house_state_cfg.get("relax_enter_min", 2)),
        "relax_exit_min": int(house_state_cfg.get("relax_exit_min", 10)),
        "sleep_requires_media_off": bool(house_state_cfg.get("sleep_requires_media_off", True)),
        "sleep_charging_min_count": (
            int(house_state_cfg["sleep_charging_min_count"])
            if house_state_cfg.get("sleep_charging_min_count") not in (None, "")
            else None
        ),
    }
    for field_name, signal_name in (
        ("vacation_mode_entity", "vacation_mode"),
        ("guest_mode_entity", "guest_mode"),
        ("sleep_window_entity", "sleep_window"),
        ("relax_mode_entity", "relax_mode"),
        ("work_window_entity", "work_window"),
    ):
        value = str(house_signals.get(signal_name, "") or "").strip()
        if value:
            payload[field_name] = value
    workday_entity = str(house_state_cfg.get("workday_entity", "") or "").strip()
    if workday_entity:
        payload["workday_entity"] = workday_entity
    return payload


def _normalized_calendar_payload(options: dict[str, Any]) -> dict[str, Any]:
    calendar = options.get("calendar", {})
    if not isinstance(calendar, dict):
        calendar = {}
    keywords = calendar.get("calendar_keywords", {})
    if not isinstance(keywords, dict):
        keywords = {}
    priority = calendar.get("category_priority", [])
    if not isinstance(priority, list):
        priority = []
    return {
        "calendar_entities": list(calendar.get("calendar_entities") or []),
        "lookahead_days": int(calendar.get("lookahead_days") or 7),
        "cache_ttl_hours": int(calendar.get("cache_ttl_hours") or 2),
        "calendar_keywords": dict(keywords),
        "priority_text": ", ".join(str(item).strip() for item in priority if str(item).strip()),
    }


def _save_options_slice(client: HAFlowClient, entry_id: str, *, step_id: str, payload: dict[str, Any]) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, step_id)
    _expect_step(step, step_id)
    step = client.options_flow_configure(flow_id, payload)
    _expect_step(step, "init")
    step = _menu_next(client, flow_id, "save")
    if step.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry on save, got: {step}")


def _save_general(client: HAFlowClient, entry_id: str, payload: dict[str, Any]) -> None:
    _save_options_slice(client, entry_id, step_id="general", payload=payload)


def _save_calendar(client: HAFlowClient, entry_id: str, payload: dict[str, Any]) -> None:
    _save_options_slice(client, entry_id, step_id="calendar", payload=payload)


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_house_state(
    client: HAClient,
    entry_id: str,
    *,
    expected_state: str,
    expected_reason: str | None,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _engine_house_state(client, entry_id)
        trace = last.get("resolution_trace", {})
        state = trace.get("resolved_state_after")
        reason = trace.get("winning_reason")
        if state == expected_state and (expected_reason is None or reason == expected_reason):
            return last
        time.sleep(poll_s)
    raise RuntimeError(
        f"timeout waiting for house_state={expected_state!r} reason={expected_reason!r}; "
        f"last_trace={last.get('resolution_trace')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify workday evidence drives house_state working")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    required = [
        "script.test_heima_reset",
        "input_boolean.test_heima_vacation_mode",
        "input_boolean.test_heima_guest_mode",
        "input_boolean.test_heima_work_mode",
        "binary_sensor.test_heima_work_window",
        "binary_sensor.test_heima_room_studio_motion",
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    occupancy_entity = _resolve_entity_id(
        client,
        exact="binary_sensor.heima_occupancy_studio",
        prefix="binary_sensor.heima_occupancy_studio",
    )
    original_options = _entry_options(client, entry_id)
    restore_payload = _normalized_general_payload(original_options)
    restore_calendar_payload = _normalized_calendar_payload(original_options)

    test_payload = dict(restore_payload)
    test_payload["work_window_entity"] = "binary_sensor.test_heima_work_window"
    test_payload["workday_entity"] = "binary_sensor.test_heima_work_window"
    test_payload["work_enter_min"] = 0
    test_calendar_payload = dict(restore_calendar_payload)
    test_calendar_payload["calendar_entities"] = []

    try:
        _save_calendar(client, entry_id, test_calendar_payload)
        _save_general(client, entry_id, test_payload)

        client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
        client.wait_state("input_boolean.test_heima_vacation_mode", "off", args.timeout_s, args.poll_s)
        client.wait_state("input_boolean.test_heima_guest_mode", "off", args.timeout_s, args.poll_s)
        client.wait_state("binary_sensor.test_heima_work_window", "off", args.timeout_s, args.poll_s)
        client.wait_state("binary_sensor.test_heima_room_studio_motion", "off", args.timeout_s, args.poll_s)

        client.call_service(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.test_heima_room_studio_motion_raw"},
        )
        client.wait_state("binary_sensor.test_heima_room_studio_motion", "on", args.timeout_s, args.poll_s)
        _recompute(client)
        client.wait_state(occupancy_entity, "on", args.timeout_s, args.poll_s)
        home_diag = _wait_house_state(
            client,
            entry_id,
            expected_state="home",
            expected_reason="default",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )

        client.call_service(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.test_heima_work_mode"},
        )
        client.wait_state("binary_sensor.test_heima_work_window", "on", args.timeout_s, args.poll_s)
        _recompute(client)
        working_diag = _wait_house_state(
            client,
            entry_id,
            expected_state="working",
            expected_reason="work_candidate_confirmed",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )

        client.call_service(
            "input_boolean",
            "turn_off",
            {"entity_id": "input_boolean.test_heima_work_mode"},
        )
        client.wait_state("binary_sensor.test_heima_work_window", "off", args.timeout_s, args.poll_s)
        _recompute(client)
        final_diag = _wait_house_state(
            client,
            entry_id,
            expected_state="home",
            expected_reason="default",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )

        print("PASS: configured workday evidence drives house_state working")
        print(f"Resolved occupancy entity: {occupancy_entity}")
        print(f"Home trace: {home_diag.get('resolution_trace')}")
        print(f"Working trace: {working_diag.get('resolution_trace')}")
        print(f"Final trace: {final_diag.get('resolution_trace')}")
        return 0
    finally:
        _save_general(client, entry_id, restore_payload)
        _save_calendar(client, entry_id, restore_calendar_payload)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
