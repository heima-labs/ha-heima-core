#!/usr/bin/env python3
"""Live-safe checks for Heima recovery observability."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient
from lib.ha_websocket import HAWebSocketClient


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _snapshot(ws: HAWebSocketClient, entry_id: str) -> dict[str, Any]:
    result = ws.call("heima/observability/snapshot", entry_id=entry_id)
    _assert(isinstance(result, dict), f"snapshot result must be a dict: {type(result)}")
    return result


def _assert_recovery_contract(snapshot: dict[str, Any]) -> None:
    recovery = snapshot.get("recovery")
    _assert(isinstance(recovery, dict), "snapshot.recovery must be a dict")
    recovery = cast(dict[str, Any], recovery)
    for key in (
        "state",
        "reason",
        "active",
        "critical_entities",
        "checkpoint",
        "blocked_apply_steps",
        "recent_events",
        "raw",
    ):
        _assert(key in recovery, f"snapshot.recovery missing {key}")

    _assert(isinstance(recovery["state"], str), "recovery.state must be a string")
    _assert(isinstance(recovery["reason"], str), "recovery.reason must be a string")
    _assert(isinstance(recovery["active"], bool), "recovery.active must be a bool")
    for key in (
        "started_at",
        "settling_started_at",
        "degraded_started_at",
        "stabilization_deadline_at",
        "degraded_timeout_at",
    ):
        _assert(key in recovery, f"snapshot.recovery missing {key}")
        _assert(
            recovery[key] is None or isinstance(recovery[key], str),
            f"recovery.{key} must be null or an ISO timestamp string",
        )

    critical = recovery["critical_entities"]
    _assert(isinstance(critical, dict), "recovery.critical_entities must be a dict")
    critical = cast(dict[str, Any], critical)
    for key in ("total", "available", "unavailable", "items", "unavailable_items"):
        _assert(key in critical, f"recovery.critical_entities missing {key}")
    _assert(isinstance(critical["total"], int), "critical_entities.total must be an int")
    _assert(isinstance(critical["available"], int), "critical_entities.available must be an int")
    _assert(
        isinstance(critical["unavailable"], int), "critical_entities.unavailable must be an int"
    )
    _assert(isinstance(critical["items"], list), "critical_entities.items must be a list")
    _assert(
        isinstance(critical["unavailable_items"], list),
        "critical_entities.unavailable_items must be a list",
    )
    _assert(
        critical["available"] + critical["unavailable"] == critical["total"],
        "critical entity availability counts are inconsistent",
    )

    checkpoint = recovery["checkpoint"]
    _assert(isinstance(checkpoint, dict), "recovery.checkpoint must be a dict")
    checkpoint = cast(dict[str, Any], checkpoint)
    for key in ("available", "usable", "stale", "reason", "store"):
        _assert(key in checkpoint, f"recovery.checkpoint missing {key}")
    _assert(isinstance(checkpoint["store"], dict), "recovery.checkpoint.store must be a dict")

    blocked = recovery["blocked_apply_steps"]
    _assert(isinstance(blocked, dict), "recovery.blocked_apply_steps must be a dict")
    blocked = cast(dict[str, Any], blocked)
    _assert(isinstance(blocked.get("total"), int), "blocked_apply_steps.total must be an int")
    _assert(
        isinstance(blocked.get("examples"), list), "blocked_apply_steps.examples must be a list"
    )
    if blocked["total"]:
        _assert(blocked["examples"], "blocked recovery steps must include examples")
        for step in blocked["examples"]:
            _assert(isinstance(step, dict), "blocked apply step example must be a dict")
            _assert(
                str(step.get("blocked_by") or "").startswith("recovery:"),
                "blocked recovery step must carry blocked_by=recovery:<state>",
            )

    events = recovery["recent_events"]
    _assert(isinstance(events, list), "recovery.recent_events must be a list")
    events = cast(list[Any], events)
    for event in events:
        _assert(isinstance(event, dict), "recovery event row must be a dict")
        _assert(
            str(event.get("reason_code") or "").startswith("recovery_"),
            "recovery event reason_code must start with recovery_",
        )


def _assert_health_alignment(client: HAClient, snapshot: dict[str, Any]) -> None:
    health_state = client.get_state("sensor.heima_health")
    _assert(isinstance(health_state, dict), "sensor.heima_health state must be a dict")
    snapshot_health = snapshot.get("health")
    _assert(isinstance(snapshot_health, dict), "snapshot.health must be a dict")
    snapshot_health = cast(dict[str, Any], snapshot_health)
    _assert(
        str(snapshot_health.get("status") or "") == str(health_state.get("state") or ""),
        "observability health status does not match sensor.heima_health",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        snapshot = _snapshot(ws, entry_id)
    _assert_recovery_contract(snapshot)
    _assert_health_alignment(client, snapshot)

    print("PASS: recovery observability live-safe contract")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
