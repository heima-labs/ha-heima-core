#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def require_entities(client: HAClient, entities: list[str]) -> None:
    missing = [e for e in entities if not client.entity_exists(e)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))


def has_entities(client: HAClient, entities: list[str]) -> bool:
    return all(client.entity_exists(entity_id) for entity_id in entities)


def reset_test_lab(client: HAClient) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})


def recompute_heima(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def scenario_house_state_override_working(client: HAClient, timeout_s: int, poll_s: float) -> None:
    print("== Scenario 1: house-state override -> working ==")
    reset_test_lab(client)
    client.call_service("heima", "set_mode", {"mode": "working", "state": True})
    recompute_heima(client)
    client.wait_state("sensor.heima_house_state", "working", timeout_s, poll_s)
    client.wait_state("sensor.heima_house_state_reason", "manual_override:working", timeout_s, poll_s)
    client.call_service("heima", "set_mode", {"mode": "working", "state": False})
    recompute_heima(client)
    print("PASS scenario 1")


def scenario_heating_vacation_curve(client: HAClient, timeout_s: int, poll_s: float) -> None:
    print("== Scenario 2: vacation heating curve branch ==")
    reset_test_lab(client)
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_set_vacation_curve_short"})
    client.call_service(
        "input_number", "set_value", {"entity_id": "input_number.test_heima_outdoor_temp", "value": 8}
    )
    client.call_service("heima", "set_mode", {"mode": "vacation", "state": True})
    recompute_heima(client)
    client.wait_state("sensor.heima_house_state", "vacation", timeout_s, poll_s)
    client.wait_state("sensor.heima_heating_branch", "vacation_curve", timeout_s, poll_s)
    target = client.state_value("sensor.heima_heating_target_temp")
    if target.lower() in {"unknown", "unavailable", "none"}:
        raise RuntimeError(f"Invalid heating target temp: {target}")
    client.call_service("heima", "set_mode", {"mode": "vacation", "state": False})
    recompute_heima(client)
    print(f"PASS scenario 2 (target_temp={target})")


def scenario_notify_event(client: HAClient, timeout_s: int, poll_s: float) -> None:
    print("== Scenario 3: notify_event pipeline smoke ==")
    client.call_service(
        "heima",
        "command",
        {
            "command": "notify_event",
            "params": {
                "type": "debug.live_test",
                "key": "debug.live_test",
                "severity": "info",
                "title": "Heima Live Test",
                "message": "notify_event smoke test",
                "context": {"source": "scripts/live_tests/000_live_smoke.py"},
            },
        },
    )
    client.wait_state("sensor.heima_last_event", "debug.live_test", timeout_s, poll_s)
    print("PASS scenario 3")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima live E2E smoke tests")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=45)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)

    core_required = [
        "sensor.heima_house_state",
        "sensor.heima_house_state_reason",
        "sensor.heima_last_event",
        "input_boolean.test_heima_work_mode",
        "input_boolean.test_heima_vacation_mode",
        "input_datetime.test_heima_vacation_start",
        "input_datetime.test_heima_vacation_end",
        "input_number.test_heima_outdoor_temp",
    ]
    require_entities(client, core_required)

    heating_entities = [
        "sensor.heima_heating_branch",
        "sensor.heima_heating_target_temp",
    ]

    scenario_house_state_override_working(client, args.timeout_s, args.poll_s)

    if has_entities(client, heating_entities):
        scenario_heating_vacation_curve(client, args.timeout_s, args.poll_s)
    else:
        print("SKIP scenario 2 (heating entities not configured)")

    scenario_notify_event(client, args.timeout_s, args.poll_s)

    print("All live scenarios passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
