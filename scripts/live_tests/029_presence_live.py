#!/usr/bin/env python3
"""True live E2E test for the Heima presence learning pipeline.

This script drives a real Home Assistant source entity from the Docker lab:

input_boolean.test_heima_room_studio_motion_raw
  -> binary_sensor.test_heima_room_studio_motion
  -> Heima person quorum presence
  -> EventRecorderBehavior presence events
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def _state_int(client: HAClient, entity_id: str) -> int:
    value = str(client.get_state(entity_id).get("state", "0")).strip()
    if value.lower() in {"unknown", "unavailable", "none", ""}:
        return 0
    try:
        return int(float(value))
    except ValueError as exc:
        raise RuntimeError(f"Expected numeric state for {entity_id}, got '{value}'") from exc


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _wait_for_presence_event_growth(
    client: HAClient,
    entry_id: str,
    previous: int,
    expected_growth: int,
    timeout_s: int,
    poll_s: float,
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _state_int_from_value((diag.get("by_type", {}) or {}).get("presence"))
        if current >= previous + expected_growth:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _state_int_from_value((diag.get("by_type", {}) or {}).get("presence"))
    raise RuntimeError(
        "Timeout waiting presence events to grow "
        f"(previous={previous}, expected_growth={expected_growth}, current={current})"
    )


def _state_int_from_value(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"unknown", "unavailable", "none", ""}:
        return 0
    return int(float(raw))


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_state(
    client: HAClient, entity_id: str, expected: str, timeout_s: int, poll_s: float
) -> None:
    client.wait_state(entity_id, expected, timeout_s, poll_s)


def _toggle_presence_cycles(
    client: HAClient,
    *,
    raw_entity: str,
    derived_entity: str,
    person_home_entity: str,
    person_source_entity: str,
    cycles: int,
    settle_s: float,
    timeout_s: int,
    poll_s: float,
) -> None:
    for idx in range(cycles):
        print(f"  cycle {idx + 1}/{cycles}: source on -> arrival")
        client.call_service("input_boolean", "turn_on", {"entity_id": raw_entity})
        _wait_state(client, derived_entity, "on", timeout_s, poll_s)
        _recompute(client)
        _wait_state(client, person_home_entity, "on", timeout_s, poll_s)
        _wait_state(client, person_source_entity, "quorum", timeout_s, poll_s)
        time.sleep(settle_s)

        print(f"  cycle {idx + 1}/{cycles}: source off -> departure")
        client.call_service("input_boolean", "turn_off", {"entity_id": raw_entity})
        _wait_state(client, derived_entity, "off", timeout_s, poll_s)
        _recompute(client)
        _wait_state(client, person_home_entity, "off", timeout_s, poll_s)
        time.sleep(settle_s)


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima true live presence learning test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--person-slug", default="test_user")
    parser.add_argument("--raw-entity", default="input_boolean.test_heima_room_studio_motion_raw")
    parser.add_argument("--derived-entity", default="binary_sensor.test_heima_room_studio_motion")
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--settle-s", type=float, default=0.35)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    person_home_entity = f"binary_sensor.heima_person_{args.person_slug}_home"
    person_source_entity = f"sensor.heima_person_{args.person_slug}_source"

    required = [
        "script.test_heima_reset",
        args.raw_entity,
        args.derived_entity,
        person_home_entity,
        person_source_entity,
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    print("Resetting lab and learning baseline...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.call_service("heima", "command", {"command": "learning_reset"})
    _recompute(client)
    _wait_state(client, args.derived_entity, "off", args.timeout_s, args.poll_s)
    _wait_state(client, person_home_entity, "off", args.timeout_s, args.poll_s)
    initial_presence_events = _state_int_from_value(
        (_event_store_diagnostics(client, entry_id).get("by_type", {}) or {}).get("presence")
    )
    print(f"Initial presence events: {initial_presence_events}")

    print("Generating real presence transitions through test lab entities...")
    _toggle_presence_cycles(
        client,
        raw_entity=args.raw_entity,
        derived_entity=args.derived_entity,
        person_home_entity=person_home_entity,
        person_source_entity=person_source_entity,
        cycles=args.cycles,
        settle_s=args.settle_s,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    print("Reloading Heima config entry after live presence transitions...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    print("Waiting for recorded presence events...")
    final_presence_events = _wait_for_presence_event_growth(
        client,
        entry_id,
        initial_presence_events,
        args.cycles * 2,
        args.timeout_s,
        args.poll_s,
    )
    print(
        "PASS: live presence events recorded "
        f"({initial_presence_events} -> {final_presence_events})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
