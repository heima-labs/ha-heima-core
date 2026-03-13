#!/usr/bin/env python3
"""Live E2E test for Heima learning pipeline (P1 + P1b + P2 + P4)."""

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
    if value in {"unknown", "unavailable", "none", ""}:
        return 0
    try:
        return int(float(value))
    except ValueError:
        raise RuntimeError(f"Expected numeric state for {entity_id}, got '{value}'")


def _wait_for_new_proposal(client: HAClient, entity_id: str, previous: int, timeout_s: int, poll_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        current = _state_int(client, entity_id)
        if current > previous:
            return
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout waiting for {entity_id} to increase (previous={previous}, current={_state_int(client, entity_id)})"
    )


def _ensure_presence_proposal(client: HAClient, entity_id: str) -> None:
    state = client.get_state(entity_id)
    attrs = dict(state.get("attributes") or {})
    if not attrs:
        raise RuntimeError("No proposal attributes found")
    for proposal in attrs.values():
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") == "presence_preheat" and proposal.get("status") == "pending":
            return
    raise RuntimeError("No pending presence_preheat proposal found in attributes")


def _has_presence_proposal(client: HAClient, entity_id: str) -> bool:
    state = client.get_state(entity_id)
    attrs = dict(state.get("attributes") or {})
    for proposal in attrs.values():
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") == "presence_preheat" and proposal.get("status") == "pending":
            return True
    return False


def _wait_for_learning_ready(
    client: HAClient, entity_id: str, previous: int, timeout_s: int, poll_s: float
) -> tuple[int, str]:
    """Wait until learning run produced visible evidence.

    Fresh baseline: count increases.
    Non-fresh baseline: count may stay stable due proposal dedup; in that case
    we accept presence_preheat pending existence as evidence.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        current = _state_int(client, entity_id)
        if current > previous:
            return current, "count_increased"
        if previous > 0 and _has_presence_proposal(client, entity_id):
            return current, "dedup_stable_count"
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout waiting learning evidence on {entity_id} (previous={previous}, current={_state_int(client, entity_id)})"
    )


def _toggle_presence(client: HAClient, person_slug: str, cycles: int, delay_s: float) -> None:
    for _ in range(cycles):
        client.call_service(
            "heima",
            "set_override",
            {"scope": "person", "id": person_slug, "override": "force_home"},
        )
        client.call_service("heima", "command", {"command": "recompute_now"})
        time.sleep(delay_s)
        client.call_service(
            "heima",
            "set_override",
            {"scope": "person", "id": person_slug, "override": "force_away"},
        )
        client.call_service("heima", "command", {"command": "recompute_now"})
        time.sleep(delay_s)

    client.call_service(
        "heima",
        "set_override",
        {"scope": "person", "id": person_slug, "override": "auto"},
    )
    client.call_service("heima", "command", {"command": "recompute_now"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima learning live E2E test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--person-slug", required=True)
    parser.add_argument("--cycles", type=int, default=6, help="arrive/depart cycles to generate")
    parser.add_argument("--delay-s", type=float, default=0.3)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    proposals_entity = "sensor.heima_reaction_proposals"
    initial = _state_int(client, proposals_entity)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")
    print(f"Initial proposals count: {initial}")

    print(f"Generating presence transitions for person '{args.person_slug}'...")
    _toggle_presence(client, args.person_slug, args.cycles, args.delay_s)

    print("Reloading Heima config entry to trigger proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    print("Waiting for learning evidence...")
    final_count, mode = _wait_for_learning_ready(
        client, proposals_entity, initial, args.timeout_s, args.poll_s
    )
    _ensure_presence_proposal(client, proposals_entity)
    print(f"PASS: learning proposal ready [{mode}] (count {initial} -> {final_count})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
