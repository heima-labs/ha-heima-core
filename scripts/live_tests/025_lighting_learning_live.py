#!/usr/bin/env python3
"""True live E2E test for lighting learning using fixture history + real actions.

The Docker lab fixture provides 4 historical user lighting occurrences for each
weekday. This script performs a real living-room scene activation through Home
Assistant entities so the current weekday reaches the 5th occurrence required
by LightingPatternAnalyzer, without using `seed_lighting_events`.
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


def _find_lighting_proposal(diag: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") != "lighting_scene_schedule":
            continue
        if proposal.get("status") != "pending":
            continue
        description = str(proposal.get("description") or "")
        if not description.startswith("living:"):
            continue
        proposal_id = str(proposal.get("id") or "")
        if not proposal_id:
            continue
        return proposal_id, proposal
    return None


def _wait_for_lighting_count_growth(
    client: HAClient, entry_id: str, previous: int, timeout_s: int, poll_s: float
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
        if current >= previous + 3:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
    raise RuntimeError(
        f"Timeout waiting lighting events to grow by 3 (before={previous}, after={current})"
    )


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
        current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
        if current >= minimum:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
    raise RuntimeError(
        "Lighting fixture baseline not loaded: "
        f"expected at least {minimum} historical lighting events, found {current}. "
        "Run the setup tier to restore learning fixtures first."
    )


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_for_lighting_proposal(
    client: HAClient, entry_id: str, previous: int, timeout_s: int, poll_s: float
) -> tuple[str, dict[str, Any], str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _proposal_diagnostics(client, entry_id)
        current = _to_int(diag.get("total"))
        found = _find_lighting_proposal(diag)
        if current > previous and found is not None:
            proposal_id, proposal = found
            return proposal_id, proposal, "count_increased"
        if previous > 0 and found is not None:
            proposal_id, proposal = found
            return proposal_id, proposal, "dedup_stable_count"
        time.sleep(poll_s)
    raise RuntimeError("Timeout waiting for pending lighting_scene_schedule proposal in diagnostics")


def _assert_expected_summary(proposal: dict[str, Any]) -> None:
    description = str(proposal.get("description") or "")
    expected_fragments = [
        "living:",
        "test_heima_living_floor off",
    ]
    for fragment in expected_fragments:
        if fragment not in description:
            raise RuntimeError(f"lighting proposal description missing expected fragment: {fragment!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima true live lighting-learning test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    required = [
        "script.test_heima_reset",
        "script.test_heima_set_living_evening_scene",
        "light.test_heima_living_main",
        "light.test_heima_living_spot",
        "light.test_heima_living_floor",
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    if missing:
        raise RuntimeError("Missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    lighting_before = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum=84,
        timeout_s=min(args.timeout_s, 60),
        poll_s=args.poll_s,
    )
    proposals_diag = _proposal_diagnostics(client, entry_id)
    proposals_before = _to_int(proposals_diag.get("total"))

    print(f"Initial lighting events: {lighting_before}")
    print(f"Initial proposals count: {proposals_before}")
    existing = _find_lighting_proposal(proposals_diag)
    if existing is not None:
        proposal_id, proposal = existing
        _assert_expected_summary(proposal)
        print(f"PASS: live lighting proposal already pending [preexisting] id={proposal_id}")
        return 0
    print("Reloading Heima config entry to refresh runtime wiring...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(2.0)

    print("Preparing lab state without clearing learning history...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.wait_state("light.test_heima_living_main", "off", args.timeout_s, args.poll_s)
    client.wait_state("light.test_heima_living_spot", "off", args.timeout_s, args.poll_s)
    client.wait_state("light.test_heima_living_floor", "off", args.timeout_s, args.poll_s)
    _recompute(client)
    time.sleep(0.5)
    client.call_service("light", "turn_on", {"entity_id": "light.test_heima_living_floor"})
    client.wait_state("light.test_heima_living_floor", "on", args.timeout_s, args.poll_s)
    _recompute(client)
    time.sleep(0.5)

    print("Executing real living evening scene through Home Assistant...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_set_living_evening_scene"})

    lighting_after = _wait_for_lighting_count_growth(
        client, entry_id, lighting_before, args.timeout_s, args.poll_s
    )
    print(f"Lighting events after live scene: {lighting_after}")

    print("Reloading Heima config entry to trigger proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    proposal_id, proposal, mode = _wait_for_lighting_proposal(
        client, entry_id, proposals_before, args.timeout_s, args.poll_s
    )
    _assert_expected_summary(proposal)
    print(f"PASS: live lighting proposal ready [{mode}] id={proposal_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
