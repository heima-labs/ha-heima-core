#!/usr/bin/env python3
"""True live E2E test for room darkness lighting assist learning.

The Docker lab fixture provides 4 historical studio darkness/lighting episodes.
This script performs one real studio occupancy + lux drop + lighting activation
sequence through Home Assistant entities so the composite catalog analyzer can
emit a pending `room_darkness_lighting_assist` proposal without seeded runtime
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


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _find_room_darkness_lighting_assist(
    diag: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") != "room_darkness_lighting_assist":
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
    minimum_state_changes: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = diag.get("by_type", {}) or {}
        state_change = _to_int(by_type.get("state_change"))
        lighting = _to_int(by_type.get("lighting"))
        if state_change >= minimum_state_changes and lighting > 0:
            return {"state_change": state_change, "lighting": lighting}
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    by_type = diag.get("by_type", {}) or {}
    raise RuntimeError(
        "Cross-domain darkness fixture baseline not loaded: "
        f"expected at least {minimum_state_changes} historical state_change events, "
        f"found {_to_int(by_type.get('state_change'))} with lighting={_to_int(by_type.get('lighting'))}. "
        "Run the setup tier to restore learning fixtures first."
    )


def _wait_for_event_growth(
    client: HAClient,
    entry_id: str,
    previous_state_changes: int,
    previous_lighting: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = diag.get("by_type", {}) or {}
        state_change = _to_int(by_type.get("state_change"))
        lighting = _to_int(by_type.get("lighting"))
        if lighting >= previous_lighting + 1:
            return {"state_change": state_change, "lighting": lighting}
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    by_type = diag.get("by_type", {}) or {}
    raise RuntimeError(
        "Timeout waiting for darkness live sequence to grow lighting event count "
        f"(state_change {previous_state_changes}->{_to_int(by_type.get('state_change'))}, "
        f"lighting {previous_lighting}->{_to_int(by_type.get('lighting'))})"
    )


def _wait_for_room_darkness_proposal(
    client: HAClient, entry_id: str, previous: int, timeout_s: int, poll_s: float
) -> tuple[str, dict[str, Any], str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _proposal_diagnostics(client, entry_id)
        current = _to_int(diag.get("total"))
        found = _find_room_darkness_lighting_assist(diag)
        if current > previous and found is not None:
            proposal_id, proposal = found
            return proposal_id, proposal, "count_increased"
        if previous > 0 and found is not None:
            proposal_id, proposal = found
            return proposal_id, proposal, "dedup_stable_count"
        time.sleep(poll_s)
    raise RuntimeError("Timeout waiting for pending room_darkness_lighting_assist proposal in diagnostics")


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


def _wait_light_brightness(
    client: HAClient,
    entity_id: str,
    expected_state: str,
    expected_brightness: int,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last_state = ""
    last_brightness: Any = None
    while time.time() < deadline:
        state = client.get_state(entity_id)
        last_state = str(state.get("state") or "")
        last_brightness = (state.get("attributes") or {}).get("brightness")
        if last_state == expected_state and int(last_brightness or 0) == expected_brightness:
            return
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout waiting for {entity_id}={expected_state} brightness={expected_brightness}, "
        f"last_state={last_state!r} last_brightness={last_brightness!r}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima true live room-darkness-lighting-assist test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    required = [
        "script.test_heima_reset",
        "binary_sensor.test_heima_room_studio_motion",
        "binary_sensor.heima_occupancy_studio",
        "sensor.test_heima_studio_lux",
        "light.test_heima_studio_main",
        "input_boolean.test_heima_light_studio_main_raw",
        "input_number.test_heima_light_studio_main_brightness",
        "input_number.test_heima_light_studio_main_color_temp",
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    baseline = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum_state_changes=36,
        timeout_s=min(args.timeout_s, 60),
        poll_s=args.poll_s,
    )
    proposals_diag = _proposal_diagnostics(client, entry_id)
    proposals_before = _to_int(proposals_diag.get("total"))

    print(f"Initial state_change events: {baseline['state_change']}")
    print(f"Initial lighting events: {baseline['lighting']}")
    print(f"Initial proposals count: {proposals_before}")
    existing = _find_room_darkness_lighting_assist(proposals_diag)
    if existing is not None:
        proposal_id, _ = existing
        print(f"PASS: room darkness lighting assist proposal already pending [preexisting] id={proposal_id}")
        return 0

    print("Reloading Heima config entry to refresh runtime wiring...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(2.0)

    print("Preparing lab state without clearing learning history...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.wait_state("binary_sensor.test_heima_room_studio_motion", "off", args.timeout_s, args.poll_s)
    client.wait_state("light.test_heima_studio_main", "off", args.timeout_s, args.poll_s)
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_lux",
        180.0,
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
    client.wait_state("binary_sensor.heima_occupancy_studio", "on", args.timeout_s, args.poll_s)

    before = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum_state_changes=36,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print("Generating real studio darkness + lighting sequence...")
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_studio_lux", "value": 90},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_lux",
        90.0,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    time.sleep(1.0)
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_light_studio_main_brightness", "value": 144},
    )
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_light_studio_main_color_temp", "value": 2900},
    )
    client.call_service(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_light_studio_main_raw"},
    )
    _wait_light_brightness(
        client,
        "light.test_heima_studio_main",
        "on",
        144,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    after = _wait_for_event_growth(
        client,
        entry_id,
        before["state_change"],
        before["lighting"],
        args.timeout_s,
        args.poll_s,
    )
    print(f"Events after live sequence: state_change={after['state_change']} lighting={after['lighting']}")

    print("Reloading Heima config entry to trigger proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    proposal_id, _proposal, mode = _wait_for_room_darkness_proposal(
        client, entry_id, proposals_before, args.timeout_s, args.poll_s
    )
    print(f"PASS: live room darkness lighting assist proposal ready [{mode}] id={proposal_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
