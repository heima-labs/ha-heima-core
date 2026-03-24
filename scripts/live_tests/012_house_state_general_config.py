#!/usr/bin/env python3
"""Live check: general flow persists house-state config and runtime reads it."""

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
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid diagnostics payload: {type(data)}")
    entry = data.get("data", {}).get("entry", {})
    if not isinstance(entry, dict):
        raise RuntimeError(f"invalid entry diagnostics payload: {type(entry)}")
    options = entry.get("options", {})
    if not isinstance(options, dict):
        raise RuntimeError(f"invalid entry options payload: {type(options)}")
    return options


def _engine_house_state(client: HAClient, entry_id: str) -> dict[str, Any]:
    data = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid diagnostics payload: {type(data)}")
    runtime = data.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        raise RuntimeError(f"invalid runtime diagnostics payload: {type(runtime)}")
    engine = runtime.get("engine", {})
    if not isinstance(engine, dict):
        raise RuntimeError(f"invalid engine diagnostics payload: {type(engine)}")
    house_state = engine.get("house_state", {})
    if not isinstance(house_state, dict):
        raise RuntimeError(f"invalid house_state diagnostics payload: {type(house_state)}")
    return house_state


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
        "sleep_charging_entities": [
            str(entity_id).strip()
            for entity_id in list(house_state_cfg.get("sleep_charging_entities", []) or [])
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


def _save_general(client: HAFlowClient, entry_id: str, payload: dict[str, Any]) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "general")
    _expect_step(step, "general")
    step = client.options_flow_configure(flow_id, payload)
    _expect_step(step, "init")
    step = _menu_next(client, flow_id, "save")
    if step.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry on save, got: {step}")


def _wait_for_house_state_config(
    client: HAClient,
    entry_id: str,
    *,
    expected_config: dict[str, Any],
    timeout_s: int,
    poll_s: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_config: dict[str, Any] = {}
    last_timers: dict[str, Any] = {}
    while time.time() < deadline:
        house_state = _engine_house_state(client, entry_id)
        config = house_state.get("config", {})
        timers = house_state.get("timers", {})
        if isinstance(config, dict):
            last_config = config
        if isinstance(timers, dict):
            last_timers = timers
        if all(last_config.get(key) == value for key, value in expected_config.items()):
            return last_config, last_timers
        time.sleep(poll_s)
    raise RuntimeError(
        "house_state diagnostics config did not converge within timeout; "
        f"last_config={last_config}, last_timers={last_timers}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify general flow persists house-state config and runtime reads it"
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    original_options = _entry_options(client, entry_id)
    restore_payload = _normalized_general_payload(original_options)

    test_payload = dict(restore_payload)
    test_payload.update(
        {
            "media_active_entities": ["media_player.cineforum"],
            "sleep_charging_entities": ["binary_sensor.house_work_window"],
            "workday_entity": "binary_sensor.house_work_window",
            "sleep_enter_min": 13,
            "sleep_exit_min": 4,
            "work_enter_min": 7,
            "relax_enter_min": 3,
            "relax_exit_min": 11,
            "sleep_requires_media_off": False,
            "sleep_charging_min_count": 2,
        }
    )
    expected_config = {
        "media_active_entities": ["media_player.cineforum"],
        "sleep_charging_entities": ["binary_sensor.house_work_window"],
        "workday_entity": "binary_sensor.house_work_window",
        "sleep_enter_min": 13,
        "sleep_exit_min": 4,
        "work_enter_min": 7,
        "relax_enter_min": 3,
        "relax_exit_min": 11,
        "sleep_requires_media_off": False,
        "sleep_charging_min_count": 2,
    }
    try:
        _save_general(client, entry_id, test_payload)

        options = _entry_options(client, entry_id)
        persisted = options.get("house_state_config")
        if persisted != expected_config:
            raise RuntimeError(f"unexpected persisted house_state_config: {persisted!r}")

        diag_config, diag_timers = _wait_for_house_state_config(
            client,
            entry_id,
            expected_config=expected_config,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        expected_timers = {
            "sleep_enter_min": 13,
            "sleep_exit_min": 4,
            "work_enter_min": 7,
            "relax_enter_min": 3,
            "relax_exit_min": 11,
        }
        for key, value in expected_timers.items():
            if diag_timers.get(key) != value:
                raise RuntimeError(f"unexpected timer {key}: {diag_timers.get(key)!r}")

        print("PASS: general house_state_config persisted and visible in runtime diagnostics")
        print(f"Persisted config: {persisted}")
        print(f"Runtime config: {diag_config}")
        print(f"Runtime timers: {diag_timers}")
        return 0
    finally:
        _save_general(client, entry_id, restore_payload)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
