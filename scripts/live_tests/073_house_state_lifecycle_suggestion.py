#!/usr/bin/env python3
"""Seeded live path for house-state lifecycle replacement suggestions."""

# ruff: noqa: I001

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


HOUSE_STATE_PROPOSAL_TYPE = "house_state_learned_context"
PROBE_REACTION_ID = "ad9_house_state_lifecycle_probe"


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


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    _assert(isinstance(raw, dict), f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    _assert(isinstance(data, dict), "diagnostics payload missing data object")
    return data


def _proposal_rows(client: HAClient, entry_id: str) -> list[dict[str, Any]]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    proposals = runtime.get("proposals", {}) if isinstance(runtime, dict) else {}
    rows = proposals.get("proposals", []) if isinstance(proposals, dict) else []
    return [dict(item) for item in rows if isinstance(item, dict)]


def _proposal_by_id(client: HAClient, entry_id: str, proposal_id: str) -> dict[str, Any] | None:
    for row in _proposal_rows(client, entry_id):
        if str(row.get("id") or "") == proposal_id:
            return row
    return None


def _lifecycle_records(client: HAClient, entry_id: str) -> list[dict[str, Any]]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    proposals = runtime.get("proposals", {}) if isinstance(runtime, dict) else {}
    lifecycle = proposals.get("lifecycle_monitoring", {}) if isinstance(proposals, dict) else {}
    rows = lifecycle.get("records", []) if isinstance(lifecycle, dict) else []
    return [dict(item) for item in rows if isinstance(item, dict)]


def _run_learning(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima",
        "command",
        {"command": "learning_run", "target": {"entry_id": entry_id}},
    )


def _seed_snapshots(
    client: HAClient,
    entry_id: str,
    *,
    weekday: int,
    minute: int,
    state: str,
) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "seed_house_state_snapshots",
            "target": {"entry_id": entry_id},
            "params": {
                "weekday": weekday,
                "minute": minute,
                "count": 3,
                "house_state": state,
                "anyone_home": True,
                "occupied_rooms": ["studio"],
                "room_device_context": {},
            },
        },
    )


def _seed_lifecycle_events(
    client: HAClient,
    entry_id: str,
    *,
    weekday: int,
    minute: int,
    state: str,
) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "seed_house_state_events",
            "target": {"entry_id": entry_id},
            "params": {
                "weekday": weekday,
                "minute": minute,
                "count": 3,
                "house_state": state,
                "anyone_home": True,
                "occupied_rooms": ["studio"],
            },
        },
    )


def _wait_for_house_state_proposal(
    client: HAClient,
    entry_id: str,
    *,
    state: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _run_learning(client, entry_id)
        for proposal in _proposal_rows(client, entry_id):
            if str(proposal.get("type") or "") != HOUSE_STATE_PROPOSAL_TYPE:
                continue
            if str(proposal.get("status") or "") != "pending":
                continue
            if state not in str(proposal.get("description") or ""):
                continue
            return proposal
        time.sleep(poll_s)
    raise AssertionError(f"house-state proposal for {state!r} not visible within timeout")


def _proposal_step_matches(step: dict[str, Any], proposal: dict[str, Any]) -> bool:
    proposal_id = str(proposal.get("id") or "")
    description = str(proposal.get("description") or "")
    identity_key = str(proposal.get("identity_key") or "")
    placeholders = step.get("description_placeholders") or {}
    haystack = " ".join(
        str(placeholders.get(key) or "")
        for key in ("proposal_label", "proposal_details", "summary")
    )
    if bool(proposal_id) and (proposal_id in haystack or description in haystack):
        return True
    if str(proposal.get("type") or "") != HOUSE_STATE_PROPOSAL_TYPE:
        return False
    if "house_state_learned_context:" not in identity_key:
        return False
    state_token = ""
    if ":state:" in identity_key:
        state_token = identity_key.rsplit(":state:", 1)[-1].strip()
    return bool(state_token) and f"→ {state_token}" in haystack


def _accept_proposal(client: HAFlowClient, entry_id: str, proposal: dict[str, Any]) -> str:
    proposal_id = str(proposal.get("id") or "")
    _assert(proposal_id, f"proposal id missing: {proposal}")

    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _assert(init.get("step_id") == "init", f"unexpected options init: {init}")
        step = client.options_flow_configure(flow_id, {"next_step_id": "proposals"})
        _assert(step.get("step_id") == "proposals", f"unexpected proposal step: {step}")

        for _ in range(30):
            if _proposal_step_matches(step, proposal):
                break
            step = client.options_flow_configure(flow_id, {"review_action": "skip"})
            if step.get("type") == "menu" and step.get("step_id") == "init":
                raise AssertionError("review queue ended before target proposal")
            _assert(step.get("step_id") == "proposals", f"unexpected proposal step: {step}")
        else:
            raise AssertionError(f"proposal {proposal_id} not reachable in review queue")

        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        _assert(
            result.get("type") in {"menu", "create_entry"} or result.get("step_id") == "proposals",
            f"unexpected result after accept: {result}",
        )
        return proposal_id
    finally:
        client.options_flow_abort(flow_id)


def _wait_for_accepted(
    client: HAClient,
    entry_id: str,
    proposal_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proposal = _proposal_by_id(client, entry_id, proposal_id)
        if proposal is not None and proposal.get("status") == "accepted":
            return proposal
        time.sleep(poll_s)
    raise AssertionError(f"proposal {proposal_id} did not become accepted")


def _upsert_probe_reaction(client: HAClient, entry_id: str, proposal: dict[str, Any]) -> None:
    proposal_id = str(proposal.get("id") or "")
    identity_key = str(proposal.get("identity_key") or "")
    _assert(proposal_id and identity_key, f"accepted proposal missing source metadata: {proposal}")
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    PROBE_REACTION_ID: {
                        "reaction_type": HOUSE_STATE_PROPOSAL_TYPE,
                        "origin": "learned",
                        "author_kind": "heima",
                        "source_request": "learned_pattern",
                        "source_proposal_id": proposal_id,
                        "source_proposal_identity_key": identity_key,
                        "enabled": True,
                    }
                },
                "labels": {
                    PROBE_REACTION_ID: "AD9 house-state lifecycle probe",
                },
            },
        },
    )


def _wait_for_replacement_suggestion(
    client: HAClient,
    entry_id: str,
    proposal_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _run_learning(client, entry_id)
        for proposal in _proposal_rows(client, entry_id):
            if str(proposal.get("status") or "") != "pending":
                continue
            if str(proposal.get("followup_kind") or "") != "replacement_suggestion":
                continue
            if str(proposal.get("target_reaction_id") or "") != proposal_id:
                continue
            return proposal
        time.sleep(poll_s)
    records = _lifecycle_records(client, entry_id)
    raise AssertionError(
        f"replacement suggestion for {proposal_id} not visible; lifecycle_records={records}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima house-state lifecycle suggestion path")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=45)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()
    weekday = 3
    minute = 17 * 60

    client.call_service(
        "heima",
        "command",
        {"command": "learning_reset", "target": {"entry_id": entry_id}},
    )
    _seed_snapshots(client, entry_id, weekday=weekday, minute=minute, state="working")

    proposal = _wait_for_house_state_proposal(
        client,
        entry_id,
        state="working",
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    proposal_id = _accept_proposal(client, entry_id, proposal)
    accepted = _wait_for_accepted(
        client,
        entry_id,
        proposal_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _upsert_probe_reaction(client, entry_id, accepted)

    _seed_lifecycle_events(client, entry_id, weekday=weekday, minute=minute, state="home")
    suggestion = _wait_for_replacement_suggestion(
        client,
        entry_id,
        proposal_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    print(f"accepted_house_state_proposal={proposal_id}")
    print(f"replacement_suggestion={suggestion.get('id')}")
    print("PASS: house-state lifecycle replacement suggestion path is live")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
