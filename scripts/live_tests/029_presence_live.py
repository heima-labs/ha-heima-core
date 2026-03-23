#!/usr/bin/env python3
"""True live E2E test for the Heima presence learning pipeline.

This script drives a real Home Assistant source entity from the Docker lab:

input_boolean.test_heima_room_studio_motion_raw
  -> binary_sensor.test_heima_room_studio_motion
  -> Heima person quorum presence
  -> EventRecorderBehavior presence events
  -> ProposalEngine presence_preheat proposal
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
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


def _has_presence_proposal(client: HAClient, entity_id: str) -> bool:
    attrs = dict(client.get_state(entity_id).get("attributes") or {})
    for proposal in attrs.values():
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") == "presence_preheat" and proposal.get("status") == "pending":
            return True
    return False


def _wait_for_learning_ready(
    client: HAClient, entity_id: str, previous: int, timeout_s: int, poll_s: float
) -> tuple[int, str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        current = _state_int(client, entity_id)
        if current > previous:
            return current, "count_increased"
        if previous > 0 and _has_presence_proposal(client, entity_id):
            return current, "dedup_stable_count"
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout waiting learning evidence on {entity_id} "
        f"(previous={previous}, current={_state_int(client, entity_id)})"
    )


def _ensure_presence_proposal(client: HAClient, entity_id: str) -> None:
    if _has_presence_proposal(client, entity_id):
        return
    raise RuntimeError("No pending presence_preheat proposal found in proposal sensor attributes")


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_state(client: HAClient, entity_id: str, expected: str, timeout_s: int, poll_s: float) -> None:
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
    parser.add_argument("--person-slug", default="stefano")
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
    proposals_entity = "sensor.heima_reaction_proposals"

    required = [
        "script.test_heima_reset",
        args.raw_entity,
        args.derived_entity,
        person_home_entity,
        person_source_entity,
        proposals_entity,
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    initial = _state_int(client, proposals_entity)
    print(f"Using heima entry_id={entry_id}")
    print(f"Initial proposals count: {initial}")

    print("Resetting lab and learning baseline...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.call_service("heima", "command", {"command": "learning_reset"})
    _recompute(client)
    _wait_state(client, args.derived_entity, "off", args.timeout_s, args.poll_s)
    _wait_state(client, person_home_entity, "off", args.timeout_s, args.poll_s)

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

    print("Reloading Heima config entry to trigger proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    print("Waiting for learning evidence...")
    final_count, mode = _wait_for_learning_ready(
        client, proposals_entity, initial, args.timeout_s, args.poll_s
    )
    _ensure_presence_proposal(client, proposals_entity)
    print(f"PASS: live presence proposal ready [{mode}] (count {initial} -> {final_count})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
