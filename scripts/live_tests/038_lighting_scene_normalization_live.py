#!/usr/bin/env python3
"""Live test for lighting scene normalization: dedup + deterministic ordering."""

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


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _wait_for_heima_entry_id(client: HAClient, *, timeout_s: int, poll_s: float) -> str:
    probe = HAClient(client.base_url, client.token, timeout_s=min(5, client.timeout_s))
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return probe.find_heima_entry_id()
        except Exception:
            time.sleep(poll_s)
    raise AssertionError("heima config entry not available within timeout")


def _wait_for_lighting_proposal(
    client: HAClient,
    entry_id: str,
    *,
    room_id: str,
    weekday: int,
    minute: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    bucket = (minute // 30) * 30
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        client.call_service(
            "heima",
            "command",
            {"command": "learning_run", "target": {"entry_id": entry_id}},
        )
        diag = _proposal_diagnostics(client, entry_id)
        proposals = diag.get("proposals")
        if isinstance(proposals, list):
            for proposal in proposals:
                if not isinstance(proposal, dict):
                    continue
                if str(proposal.get("type") or "") != "lighting_scene_schedule":
                    continue
                identity_key = str(proposal.get("identity_key") or "")
                if not identity_key.startswith(
                    f"lighting_scene_schedule|room={room_id}|weekday={weekday}|bucket={bucket}"
                ):
                    continue
                if str(proposal.get("status") or "") != "pending":
                    continue
                return proposal
        time.sleep(poll_s)
    raise AssertionError("normalized lighting proposal not visible in diagnostics within timeout")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima lighting scene normalization live test")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entry-id")
    parser.add_argument("--timeout-s", type=int, default=25)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = str(args.entry_id or "").strip() or _wait_for_heima_entry_id(
        client, timeout_s=args.timeout_s, poll_s=args.poll_s
    )
    print(f"Using heima entry_id={entry_id}")

    room_id = "living"
    weekday = 0
    base_minute = 20 * 60

    client.call_service("heima", "command", {"command": "learning_reset", "target": {"entry_id": entry_id}})
    print("Learning reset completed.")

    seed_payloads = [
        {
            "entity_id": "light.test_heima_living_main",
            "room_id": room_id,
            "action": "on",
            "weekday": weekday,
            "minute": base_minute,
            "count": 5,
            "brightness": 190,
            "color_temp_kelvin": 2850,
        },
        {
            "entity_id": "light.test_heima_living_main",
            "room_id": room_id,
            "action": "off",
            "weekday": weekday,
            "minute": base_minute + 5,
            "count": 5,
        },
        {
            "entity_id": "light.test_heima_living_spot",
            "room_id": room_id,
            "action": "on",
            "weekday": weekday,
            "minute": base_minute + 4,
            "count": 5,
            "brightness": 160,
            "color_temp_kelvin": 2600,
        },
    ]

    for payload in seed_payloads:
        client.call_service(
            "heima",
            "command",
            {
                "command": "seed_lighting_events",
                "target": {"entry_id": entry_id},
                "params": payload,
            },
        )
        print(
            "Seeded "
            f"{payload['entity_id']} action={payload['action']} minute={payload['minute']}"
        )

    proposal = _wait_for_lighting_proposal(
        client,
        entry_id,
        room_id=room_id,
        weekday=weekday,
        minute=base_minute,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    print(f"Normalized proposal diagnostics: {proposal}")
    config_summary = dict(proposal.get("config_summary") or {})
    explainability = dict(proposal.get("explainability") or {})
    description = str(proposal.get("description") or "")

    _assert(config_summary.get("entity_steps_count") == 2, f"expected 2 normalized steps, got {config_summary}")
    _assert(explainability.get("entity_steps_count") == 2, f"expected explainability entity_steps_count=2, got {explainability}")
    _assert(explainability.get("cluster_entities") == ["light.test_heima_living_main", "light.test_heima_living_spot"], f"unexpected cluster_entities: {explainability.get('cluster_entities')}")
    _assert(description.count("test_heima_living_main") == 1, f"main entity appears more than once: {description}")
    _assert(description.count("test_heima_living_spot") == 1, f"spot entity appears more than once: {description}")
    _assert(
        description.index("test_heima_living_main") < description.index("test_heima_living_spot"),
        f"description ordering is not deterministic: {description}",
    )

    print("PASS: lighting scene normalization collapsed duplicate entity patterns and kept deterministic ordering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
