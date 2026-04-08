#!/usr/bin/env python3
"""Live runtime E2E: security camera evidence on the fake house lab."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _required_entities() -> list[str]:
    return [
        "alarm_control_panel.test_heima_alarm",
        "sensor.heima_security_state",
        "sensor.heima_security_reason",
        "binary_sensor.test_heima_camera_entry_person",
        "binary_sensor.test_heima_camera_entry_motion",
        "binary_sensor.test_heima_front_door_contact",
        "binary_sensor.test_heima_camera_garage_person",
        "binary_sensor.test_heima_camera_garage_vehicle",
        "binary_sensor.test_heima_garage_door_contact",
        "script.test_heima_camera_clear",
        "script.test_heima_camera_entry_arrival",
        "script.test_heima_camera_garage_arrival",
        "script.test_heima_camera_garage_person_alert",
    ]


def _require_entities(client: HAClient, entity_ids: list[str]) -> None:
    missing = [entity_id for entity_id in entity_ids if not client.entity_exists(entity_id)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _diag(client: HAClient) -> dict[str, Any]:
    entry_id = client.find_heima_entry_id()
    payload = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid diagnostics payload type: {type(payload)}")
    return payload


def _security_trace(client: HAClient) -> dict[str, Any]:
    diag = _diag(client)
    runtime = dict(diag.get("data", {}).get("runtime", {}) or {})
    engine = dict(runtime.get("engine", {}) or {})
    security = dict(engine.get("security", {}) or {})
    return dict(security.get("camera_evidence_trace", {}) or {})


def _security_provider_summary(client: HAClient) -> dict[str, Any]:
    diag = _diag(client)
    runtime = dict(diag.get("data", {}).get("runtime", {}) or {})
    engine = dict(runtime.get("engine", {}) or {})
    provider = dict(engine.get("security_camera_evidence", {}) or {})
    if provider:
        return provider
    plugins = dict(runtime.get("plugins", {}) or {})
    return dict(plugins.get("security_camera_evidence_summary", {}) or {})


def _wait_for_candidate_rule(
    client: HAClient,
    rule: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_trace: dict[str, Any] = {}
    while time.time() < deadline:
        _recompute(client)
        trace = _security_trace(client)
        last_trace = trace
        candidates = list(trace.get("breach_candidates") or [])
        for item in candidates:
            if isinstance(item, dict) and str(item.get("rule") or "") == rule:
                return item
        time.sleep(poll_s)
    raise RuntimeError(f"Timeout waiting for breach candidate rule={rule!r}; last_trace={last_trace}")


def _wait_for_return_home_hint(
    client: HAClient,
    *,
    timeout_s: int,
    poll_s: float,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_trace: dict[str, Any] = {}
    while time.time() < deadline:
        _recompute(client)
        trace = _security_trace(client)
        last_trace = trace
        if trace.get("return_home_hint") is True:
            reasons = [
                dict(item)
                for item in list(trace.get("return_home_hint_reasons") or [])
                if isinstance(item, dict)
            ]
            if reasons:
                return reasons
        time.sleep(poll_s)
    raise RuntimeError(f"Timeout waiting for return_home_hint; last_trace={last_trace}")


def _clear_camera_state(client: HAClient) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_camera_clear"})
    time.sleep(0.4)
    _recompute(client)


def _arm_away(client: HAClient) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_alarm_arm_away"})
    client.wait_state("alarm_control_panel.test_heima_alarm", "armed_away", 20, 0.5)
    _recompute(client)


def _disarm(client: HAClient) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_alarm_disarm"})
    client.wait_state("alarm_control_panel.test_heima_alarm", "disarmed", 20, 0.5)
    _recompute(client)


def _assert_camera_sources_configured(client: HAClient) -> None:
    entry_id = client.find_heima_entry_id()
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    deadline = time.time() + 30
    last_sources: list[dict[str, Any]] = []
    while time.time() < deadline:
        summary = _security_provider_summary(client)
        configured_sources = [
            dict(item) for item in list(summary.get("configured_sources") or []) if isinstance(item, dict)
        ]
        if len(configured_sources) >= 2:
            return
        last_sources = configured_sources
        time.sleep(1.0)
    summary = _security_provider_summary(client)
    configured_sources = list(summary.get("configured_sources") or [])
    _assert(
        len(configured_sources) >= 2,
        f"camera_evidence_sources not configured in runtime summary: {last_sources or configured_sources}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima security camera evidence live test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=45)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)

    _require_entities(client, _required_entities())
    _assert_camera_sources_configured(client)

    print("Resetting lab...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    time.sleep(0.6)
    _clear_camera_state(client)
    _disarm(client)

    print("Scenario 1: entry person while armed_away")
    _arm_away(client)
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_camera_entry_arrival"})
    candidate = _wait_for_candidate_rule(
        client,
        "armed_away_entry_person",
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    reasons = _wait_for_return_home_hint(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _assert(candidate.get("source_id") == "entry_cam", f"unexpected entry candidate: {candidate}")
    _assert(any(str(item.get("source_id") or "") == "entry_cam" for item in reasons), f"unexpected return-home reasons: {reasons}")
    summary = _security_provider_summary(client)
    trace = _security_trace(client)
    _assert(
        len(list(trace.get("breach_candidates") or [])) >= 1,
        f"unexpected camera evidence trace: {trace}; provider={summary}",
    )
    print("PASS scenario 1")

    print("Scenario 2: garage open + vehicle while armed_away")
    _clear_camera_state(client)
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_camera_garage_arrival"})
    garage_candidate = _wait_for_candidate_rule(
        client,
        "armed_away_garage_open_with_presence",
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _assert(garage_candidate.get("source_id") == "garage_cam", f"unexpected garage candidate: {garage_candidate}")
    print("PASS scenario 2")

    _clear_camera_state(client)
    _disarm(client)
    print("PASS: security camera evidence live runtime")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
