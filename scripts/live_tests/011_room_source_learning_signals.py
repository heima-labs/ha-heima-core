#!/usr/bin/env python3
"""Live check: room sources marked for learning enter the runtime signal pool."""

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


def _flow_save(client: HAFlowClient, flow_id: str) -> None:
    result = _menu_next(client, flow_id, "save")
    if result.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry on save, got: {result}")


def _engine_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    data = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid diagnostics payload: {type(data)}")
    runtime = data.get("data", {}).get("runtime", {})
    engine = runtime.get("engine", {})
    if not isinstance(engine, dict):
        raise RuntimeError(f"invalid engine diagnostics payload: {type(engine)}")
    return engine


def _tracked_signal_entities(engine_diag: dict[str, Any]) -> list[str]:
    behaviors = engine_diag.get("behaviors", {})
    if not isinstance(behaviors, dict):
        return []
    signal = behaviors.get("signal_recorder", {})
    if not isinstance(signal, dict):
        return []
    tracked = signal.get("tracked_entities", [])
    if not isinstance(tracked, list):
        return []
    return [str(entity_id) for entity_id in tracked]


def _wait_for_tracking(
    client: HAClient,
    entry_id: str,
    *,
    entity_id: str,
    timeout_s: int,
    poll_s: float,
) -> list[str]:
    deadline = time.time() + timeout_s
    last: list[str] = []
    while time.time() < deadline:
        tracked = _tracked_signal_entities(_engine_diagnostics(client, entry_id))
        last = tracked
        if entity_id in tracked:
            return tracked
        time.sleep(poll_s)
    raise RuntimeError(f"{entity_id} not found in tracked_entities within timeout; last={last}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify learning-enabled room sources reach signal recorder")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    tracked_entity = "binary_sensor.test_heima_room_studio_motion"

    before = _tracked_signal_entities(_engine_diagnostics(client, entry_id))
    if tracked_entity in before:
        raise RuntimeError(
            f"precondition failed: {tracked_entity} already tracked before room learning update"
        )

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "rooms_menu")
    _expect_step(step, "rooms_menu")
    step = _menu_next(client, flow_id, "rooms_edit")
    _expect_step(step, "rooms_edit")
    step = client.options_flow_configure(flow_id, {"room": "studio"})
    _expect_step(step, "rooms_edit_form")

    payload = {
        "room_id": "studio",
        "display_name": "Studio",
        "area_id": "test_heima_studio",
        "occupancy_mode": "derived",
        "sources": ["binary_sensor.test_heima_room_studio_motion"],
        "learning_sources": ["binary_sensor.test_heima_room_studio_motion"],
        "logic": "any_of",
        "on_dwell_s": 5,
        "off_dwell_s": 120,
        "max_on_s": None,
    }
    step = client.options_flow_configure(flow_id, payload)
    _expect_step(step, "rooms_menu")
    step = _menu_next(client, flow_id, "rooms_save")
    if step.get("type") != "create_entry":
        raise RuntimeError(f"expected create_entry from rooms_save, got: {step}")

    tracked = _wait_for_tracking(
        client,
        entry_id,
        entity_id=tracked_entity,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print(f"PASS: learning-enabled room source tracked by runtime [{tracked_entity}]")
    print(f"Tracked entities now: {tracked}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
