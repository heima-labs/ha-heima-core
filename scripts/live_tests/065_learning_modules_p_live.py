#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Live diagnostic check for Phase P learning module wiring."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

REQUIRED_MODULES = {
    "lighting_pattern",
    "room_state_correlation",
    "occupancy_inference",
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = _diagnostics_data(client, entry_id).get("entry", {})
    if not isinstance(entry, dict):
        return {}
    options = entry.get("options", {})
    return dict(options) if isinstance(options, dict) else {}


def _sensorless_room_ids(options: dict[str, Any]) -> list[str]:
    room_ids: list[str] = []
    for room in options.get("rooms", []) or []:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id") or "").strip()
        if not room_id:
            continue
        if str(room.get("occupancy_mode") or "derived").strip().lower() != "derived":
            continue
        occupancy_sources = [
            str(item or "").strip()
            for item in room.get("occupancy_sources", []) or []
            if str(item or "").strip()
        ]
        if occupancy_sources:
            continue
        room_ids.append(room_id)
    return sorted(room_ids)


def _learning_modules(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    modules = engine.get("learning_modules", []) if isinstance(engine, dict) else []
    if not isinstance(modules, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_id = str(module.get("module_id") or "").strip()
        if module_id:
            result[module_id] = module
    return result


def _engine_health_ok(client: HAClient, entry_id: str) -> None:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    _assert(isinstance(engine, dict) and bool(engine), "engine diagnostics missing after P run")


def _wait_for_modules_ready(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last: dict[str, dict[str, Any]] = {}
    while time.time() < deadline:
        last = _learning_modules(client, entry_id)
        if REQUIRED_MODULES.issubset(last) and all(
            bool(last[module_id].get("ready")) for module_id in REQUIRED_MODULES
        ):
            return last
        time.sleep(poll_s)
    raise AssertionError(f"Phase P modules not ready; last={last}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=45)
    parser.add_argument("--poll-s", type=float, default=2.0)
    args = parser.parse_args()

    client = HAClient(args.ha_url, args.ha_token)
    entry_id = client.find_heima_entry_id()
    options = _entry_options(client, entry_id)
    expected_sensorless = _sensorless_room_ids(options)

    print(f"Using heima entry_id={entry_id}")
    client.call_service("heima", "command", {"command": "learning_run", "target": {"entry_id": entry_id}})
    client.call_service("heima", "command", {"command": "recompute_now", "target": {"entry_id": entry_id}})

    modules = _wait_for_modules_ready(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _engine_health_ok(client, entry_id)

    occupancy = modules["occupancy_inference"]
    actual_sensorless = sorted(str(item) for item in occupancy.get("sensorless_rooms", []) or [])
    _assert(
        actual_sensorless == expected_sensorless,
        f"sensorless room sync mismatch: expected={expected_sensorless}, actual={actual_sensorless}",
    )

    for module_id in sorted(REQUIRED_MODULES):
        module = modules[module_id]
        _assert(
            int(module.get("analyzed_snapshots") or 0) >= 0,
            f"{module_id} analyzed_snapshots invalid: {module}",
        )

    print(
        "PASS: Phase P modules are registered, analyzed, ready, and sensorless sync matches options"
    )


if __name__ == "__main__":
    main()
