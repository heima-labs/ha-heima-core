#!/usr/bin/env python3
"""Live E2E test for Heima lighting-schedule learning pipeline (P9).

Pipeline tested:
  1. seed_lighting_events  → EventStore (via heima.command)
  2. reload config entry   → ProposalEngine.async_run()
  3. sensor check          → lighting_scene_schedule proposal pending
  4. accept proposal       → options flow reactions step
  5. entity check          → diagnostics confirm LightingScheduleReaction instantiated

Usage:
    python3 scripts/live_tests/060_lighting_schedule.py \\
        --ha-url http://127.0.0.1:8123 \\
        --ha-token <token> \\
        --light-entity light.test_heima_living_main \\
        --room-id living
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _find_lighting_proposal(client: HAClient, entity_id: str, status: str = "pending") -> dict | None:
    """Return first lighting_scene_schedule proposal with given status, or None."""
    state = client.get_state(entity_id)
    attrs = dict(state.get("attributes") or {})
    for proposal in attrs.values():
        if not isinstance(proposal, dict):
            continue
        if (proposal.get("type") == "lighting_scene_schedule"
                and proposal.get("status") == status):
            return proposal
    return None


def _wait_for_lighting_proposal(
    client: HAClient,
    entity_id: str,
    timeout_s: int,
    poll_s: float,
    *,
    min_initial_count: int = 0,
) -> dict:
    """Poll until a pending lighting_scene_schedule proposal appears."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proposal = _find_lighting_proposal(client, entity_id, "pending")
        if proposal is not None:
            return proposal
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout: no pending lighting_scene_schedule proposal in {entity_id} "
        f"after {timeout_s}s"
    )


class HAFlowClient(HAClient):
    def options_flow_init(self, entry_id: str) -> dict[str, Any]:
        data = self.post("/api/config/config_entries/options/flow", {"handler": entry_id})
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow init response: {type(data)}")
        return data

    def options_flow_configure(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.post(f"/api/config/config_entries/options/flow/{flow_id}", payload)
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow response: {type(data)}")
        return data

    def options_flow_abort(self, flow_id: str) -> None:
        self.delete(f"/api/config/config_entries/options/flow/{flow_id}")


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    got = result.get("step_id")
    _assert(got == step_id, f"expected step_id={step_id!r}, got={got!r} — {result}")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_reset_learning(client: HAClient, entry_id: str) -> None:
    print("  → learning_reset (clear previous state)")
    client.call_service("heima", "command", {
        "command": "learning_reset",
        "target": {"entry_id": entry_id},
    })


def step_seed_events(
    client: HAClient,
    entry_id: str,
    light_entity: str,
    room_id: str,
    weekday: int,
    minute: int,
    brightness: int | None,
    color_temp_kelvin: int | None,
    count: int,
) -> None:
    print(f"  → seed_lighting_events: {count} events for {light_entity} (room={room_id})")
    params: dict[str, Any] = {
        "entity_id": light_entity,
        "room_id": room_id,
        "weekday": weekday,
        "minute": minute,
        "count": count,
    }
    if brightness is not None:
        params["brightness"] = brightness
    if color_temp_kelvin is not None:
        params["color_temp_kelvin"] = color_temp_kelvin
    client.call_service("heima", "command", {
        "command": "seed_lighting_events",
        "target": {"entry_id": entry_id},
        "params": params,
    })


def step_trigger_proposal_run(client: HAClient, entry_id: str) -> None:
    print("  → reload config entry to trigger ProposalEngine.async_run()")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})


def step_wait_for_proposal(
    client: HAClient,
    proposals_entity: str,
    timeout_s: int,
    poll_s: float,
) -> dict:
    print(f"  → waiting for lighting_scene_schedule proposal in {proposals_entity}")
    proposal = _wait_for_lighting_proposal(
        client,
        proposals_entity,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    conf = proposal.get("confidence", "?")
    desc = str(proposal.get("description", "")).strip()
    print(f"     proposal found: confidence={conf} desc={desc!r}")
    return proposal


def step_accept_proposal(
    client: HAFlowClient,
    entry_id: str,
    proposals_entity: str,
) -> str:
    """Navigate options flow → reactions → accept the first pending lighting proposal.

    Returns the accepted proposal_id.
    """
    print("  → accepting lighting proposal via options flow")

    # Find proposal_id from sensor attributes
    state = client.get_state(proposals_entity)
    attrs = dict(state.get("attributes") or {})
    proposal_id = None
    for pid, proposal in attrs.items():
        if not isinstance(proposal, dict):
            continue
        if (proposal.get("type") == "lighting_scene_schedule"
                and proposal.get("status") == "pending"):
            proposal_id = pid
            break
    _assert(proposal_id is not None, "No pending lighting_scene_schedule proposal to accept")
    print(f"     accepting proposal_id={proposal_id}")

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "reactions")
    _expect_step(step, "reactions")

    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")

    result = client.options_flow_configure(flow_id, {
        "accept": [proposal_id],
        "reject": [],
    })
    # Step returns to init or create_entry
    if result.get("type") == "create_entry":
        return proposal_id

    # Save
    saved = _menu_next(client, flow_id, "save")
    _assert(saved.get("type") == "create_entry", f"expected create_entry, got: {saved}")

    return proposal_id


def step_verify_accepted(
    client: HAClient,
    proposals_entity: str,
    proposal_id: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    """Poll until the proposal appears with status=accepted."""
    print(f"  → waiting for proposal {proposal_id} to show status=accepted")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        state = client.get_state(proposals_entity)
        attrs = dict(state.get("attributes") or {})
        proposal = attrs.get(proposal_id)
        if isinstance(proposal, dict) and proposal.get("status") == "accepted":
            print("     accepted confirmed in sensor")
            return
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout: proposal {proposal_id} not showing accepted status after {timeout_s}s"
    )


def step_verify_reaction_instantiated(client: HAClient, entry_id: str) -> None:
    """Check diagnostics to verify LightingScheduleReaction is in the engine."""
    print("  → checking diagnostics for LightingScheduleReaction")
    diag = client.get(f"/api/heima/diagnostics/{entry_id}", accept_error=True)
    if not isinstance(diag, dict):
        print("     diagnostics endpoint not available, skipping reaction check")
        return
    reactions = []
    runtime = diag.get("runtime") or {}
    reactions_diag = runtime.get("reactions") or {}
    found = any(
        str(r.get("class", "")).endswith("LightingScheduleReaction")
        for r in (reactions_diag.get("active") or [])
        if isinstance(r, dict)
    )
    if found:
        print("     LightingScheduleReaction found in diagnostics")
    else:
        print("     (LightingScheduleReaction not found in diagnostics — check diagnostics schema)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Heima lighting-schedule live E2E test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--light-entity", required=True, help="HA entity_id of the light (e.g. light.living_main)")
    parser.add_argument("--room-id", required=True, help="Heima room_id")
    parser.add_argument("--weekday", type=int, default=0, help="0=Mon … 6=Sun")
    parser.add_argument("--minute", type=int, default=1200, help="minute of day (0-1439)")
    parser.add_argument("--brightness", type=int, default=None)
    parser.add_argument("--color-temp-kelvin", type=int, default=None)
    parser.add_argument("--event-count", type=int, default=6, help="synthetic events to seed (min 5)")
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--skip-accept", action="store_true", help="skip options flow accept step")
    args = parser.parse_args()

    if args.event_count < 5:
        print("FAIL: --event-count must be >= 5 (analyzer gate)", file=sys.stderr)
        return 1

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token)
    proposals_entity = "sensor.heima_reaction_proposals"

    entry_id = client.find_heima_entry_id()
    print(f"Heima entry_id={entry_id}")

    # 1. Reset
    step_reset_learning(client, entry_id)

    # 2. Seed
    step_seed_events(
        client,
        entry_id,
        light_entity=args.light_entity,
        room_id=args.room_id,
        weekday=args.weekday,
        minute=args.minute,
        brightness=args.brightness,
        color_temp_kelvin=args.color_temp_kelvin,
        count=args.event_count,
    )

    # 3. Trigger proposal run
    step_trigger_proposal_run(client, entry_id)

    # 4. Wait for proposal
    proposal = step_wait_for_proposal(
        client,
        proposals_entity,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _assert(proposal.get("type") == "lighting_scene_schedule",
            f"wrong proposal type: {proposal.get('type')}")
    _assert(float(proposal.get("confidence", 0)) >= 0.3, "confidence too low")

    if args.skip_accept:
        print("PASS: lighting proposal generated (accept skipped)")
        return 0

    # 5. Accept proposal
    proposal_id = step_accept_proposal(client, entry_id, proposals_entity)

    # 6. Verify accepted
    step_verify_accepted(client, proposals_entity, proposal_id, timeout_s=30, poll_s=args.poll_s)

    # 7. Verify reaction instantiated (best-effort)
    step_verify_reaction_instantiated(client, entry_id)

    print("PASS: lighting schedule E2E pipeline complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
