#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Live diagnostic check for Phase N semantic policy suggestions."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


SEMANTIC_RULES = {
    "alarm_away_lights_off": "alarm_state_action",
    "alarm_triggered_lights_on": "alarm_state_action",
    "alarm_away_climate_off": "alarm_state_action",
    "alarm_night_climate_sleep": "alarm_state_action",
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


def _light_entities(options: dict[str, Any]) -> list[str]:
    entities: list[str] = []
    for key in ("rooms", "lighting_rooms"):
        for room in options.get(key, []) or []:
            if not isinstance(room, dict):
                continue
            for entity_id in room.get("light_entities", []) or []:
                entity = str(entity_id or "").strip()
                if entity.startswith("light.") and entity not in entities:
                    entities.append(entity)
    return entities


def _expected_rule_ids(options: dict[str, Any]) -> set[str]:
    security = options.get("security", {})
    if not isinstance(security, dict) or not str(security.get("security_state_entity") or ""):
        return set()

    expected: set[str] = set()
    if _light_entities(options):
        expected.update({"alarm_away_lights_off", "alarm_triggered_lights_on"})

    heating = options.get("heating", {})
    if isinstance(heating, dict) and str(heating.get("climate_entity") or ""):
        expected.update({"alarm_away_climate_off", "alarm_night_climate_sleep"})
    return expected


def _proposal_map(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    proposals = _diagnostics_data(client, entry_id).get("runtime", {}).get("proposals", {})
    if not isinstance(proposals, dict):
        return {}
    items = proposals.get("proposals", [])
    if not isinstance(items, list):
        return {}
    mapped: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        identity_key = str(item.get("identity_key") or "").strip()
        if identity_key:
            mapped[identity_key] = item
    return mapped


def _wait_for_semantic_proposals(
    client: HAClient,
    entry_id: str,
    expected: set[str],
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last: dict[str, dict[str, Any]] = {}
    while time.time() < deadline:
        last = _proposal_map(client, entry_id)
        if expected.issubset(last):
            return last
        time.sleep(poll_s)
    missing = sorted(expected.difference(last))
    raise AssertionError(f"semantic policy proposals missing after reload: {missing}")


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
    expected = _expected_rule_ids(options)
    _assert(
        bool(expected),
        "lab config does not expose a semantic-policy topology "
        "(requires security plus lights and/or climate)",
    )

    print(f"Using heima entry_id={entry_id}")
    print(f"Expected semantic rules from topology: {sorted(expected)}")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    proposals = _wait_for_semantic_proposals(
        client,
        entry_id,
        expected,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    for rule_id in sorted(expected):
        proposal = proposals[rule_id]
        _assert(
            proposal.get("type") == SEMANTIC_RULES[rule_id],
            f"{rule_id} has wrong reaction type: {proposal}",
        )
        _assert(proposal.get("origin") == "admin_authored", f"{rule_id} origin mismatch")
        _assert(
            proposal.get("analyzer") == "semantic_policy_suggestions",
            f"{rule_id} analyzer mismatch: {proposal}",
        )

    print("PASS: semantic policy proposals are present with admin-authored origin")


if __name__ == "__main__":
    main()
