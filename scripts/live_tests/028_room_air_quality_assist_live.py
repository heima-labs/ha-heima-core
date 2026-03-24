#!/usr/bin/env python3
"""True live E2E test for room air-quality assist learning.

The Docker lab fixture provides 4 historical studio CO2/ventilation episodes.
This script performs one real studio occupancy + CO2 rise + fan activation
sequence through Home Assistant entities so the composite catalog analyzer can
emit a pending `room_air_quality_assist` proposal without seeded runtime
commands.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


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


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _find_room_air_quality_assist(diag: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") != "room_air_quality_assist":
            continue
        if proposal.get("status") != "pending":
            continue
        description = str(proposal.get("description") or "")
        if not description.startswith("studio:"):
            continue
        proposal_id = str(proposal.get("id") or "")
        if proposal_id:
            return proposal_id, proposal
    return None


def _wait_for_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum: int,
    timeout_s: int,
    poll_s: float,
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
        if current >= minimum:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
    raise RuntimeError(
        "Cross-domain air-quality fixture baseline not loaded: "
        f"expected at least {minimum} historical state_change events, found {current}. "
        "Run the setup tier to restore learning fixtures first."
    )


def _wait_for_state_change_growth(
    client: HAClient, entry_id: str, previous: int, timeout_s: int, poll_s: float
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
        if current >= previous + 2:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
    raise RuntimeError(
        f"Timeout waiting state_change events to grow by 2 (before={previous}, after={current})"
    )


def _wait_for_room_air_quality_proposal(
    client: HAClient, entry_id: str, previous: int, timeout_s: int, poll_s: float
) -> tuple[str, dict[str, Any], str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _proposal_diagnostics(client, entry_id)
        current = _to_int(diag.get("total"))
        found = _find_room_air_quality_assist(diag)
        if current > previous and found is not None:
            proposal_id, proposal = found
            return proposal_id, proposal, "count_increased"
        if previous > 0 and found is not None:
            proposal_id, proposal = found
            return proposal_id, proposal, "dedup_stable_count"
        time.sleep(poll_s)
    raise RuntimeError("Timeout waiting for pending room_air_quality_assist proposal in diagnostics")


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_numeric_state(
    client: HAClient,
    entity_id: str,
    expected: float,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        last = client.state_value(entity_id)
        try:
            if abs(float(last) - expected) < 0.05:
                return
        except ValueError:
            pass
        time.sleep(poll_s)
    raise RuntimeError(f"Timeout waiting for {entity_id}≈{expected}, last={last!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima true live room-air-quality-assist test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    required = [
        "script.test_heima_reset",
        "binary_sensor.test_heima_room_studio_motion",
        "sensor.test_heima_studio_co2",
        "switch.test_heima_studio_fan",
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
    baseline = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum=32,
        timeout_s=min(args.timeout_s, 60),
        poll_s=args.poll_s,
    )
    proposals_diag = _proposal_diagnostics(client, entry_id)
    proposals_before = _to_int(proposals_diag.get("total"))

    print(f"Initial state_change events: {baseline}")
    print(f"Initial proposals count: {proposals_before}")
    existing = _find_room_air_quality_assist(proposals_diag)
    if existing is not None:
        proposal_id, _ = existing
        print(f"PASS: room air quality assist proposal already pending [preexisting] id={proposal_id}")
        return 0

    print("Reloading Heima config entry to refresh runtime wiring...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(2.0)

    print("Preparing lab state without clearing learning history...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.wait_state("binary_sensor.test_heima_room_studio_motion", "off", args.timeout_s, args.poll_s)
    client.wait_state("switch.test_heima_studio_fan", "off", args.timeout_s, args.poll_s)
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_co2",
        700.0,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    print("Marking studio occupied and recomputing snapshot context...")
    client.call_service(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_room_studio_motion_raw"},
    )
    client.wait_state("binary_sensor.test_heima_room_studio_motion", "on", args.timeout_s, args.poll_s)
    _recompute(client)
    client.wait_state(occupancy_entity, "on", args.timeout_s, args.poll_s)

    before_events = _to_int((_event_store_diagnostics(client, entry_id).get("by_type", {}) or {}).get("state_change"))
    print("Generating real studio CO2 + ventilation sequence...")
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_studio_co2", "value": 940},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_co2",
        940.0,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    time.sleep(1.0)
    client.call_service("switch", "turn_on", {"entity_id": "switch.test_heima_studio_fan"})
    client.wait_state("switch.test_heima_studio_fan", "on", args.timeout_s, args.poll_s)

    after_events = _wait_for_state_change_growth(
        client, entry_id, before_events, args.timeout_s, args.poll_s
    )
    print(f"State_change events after live sequence: {after_events}")

    print("Reloading Heima config entry to trigger proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    proposal_id, _proposal, mode = _wait_for_room_air_quality_proposal(
        client, entry_id, proposals_before, args.timeout_s, args.poll_s
    )
    print(f"PASS: live room air quality assist proposal ready [{mode}] id={proposal_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
