#!/usr/bin/env python3
"""Live diagnostics for proposal review grouping.

This test is intentionally non-destructive: it does not reset learning state and
does not approve/reject proposals. It validates the query-time view exposed by
ProposalEngine after a learning run.
"""

# ruff: noqa: I001

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


HOUSE_STATE_PROPOSAL_TYPE = "house_state_learned_context"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    _assert(isinstance(raw, dict), f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    _assert(isinstance(data, dict), "diagnostics payload missing data object")
    return data


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    _assert(isinstance(runtime, dict), "diagnostics runtime must be a dict")
    proposals = runtime.get("proposals", {})
    _assert(isinstance(proposals, dict), "runtime.proposals must be a dict")
    return proposals


def _learning_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
    plugins = _diagnostics_data(client, entry_id).get("runtime", {}).get("plugins", {})
    _assert(isinstance(plugins, dict), "runtime.plugins must be a dict")
    summary = plugins.get("learning_summary", {})
    _assert(isinstance(summary, dict), "plugins.learning_summary must be a dict")
    return summary


def _sensor_pending_count(client: HAClient) -> int:
    state = client.get_state("sensor.heima_reaction_proposals")
    raw = str(state.get("state") or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _pending_representatives(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        proposal
        for proposal in proposals
        if str(proposal.get("status") or "") == "pending"
        and proposal.get("suppressed_by_review_group") is not True
    ]


def _assert_grouping_contract(proposals_diag: dict[str, Any]) -> None:
    proposals_raw = proposals_diag.get("proposals")
    _assert(isinstance(proposals_raw, list), "proposals diagnostics must expose a proposals list")
    proposals = [item for item in proposals_raw if isinstance(item, dict)]

    pending_count = int(proposals_diag.get("pending") or 0)
    visible_pending = _pending_representatives(proposals)
    _assert(
        pending_count == len(visible_pending),
        f"diagnostic pending count {pending_count} != visible pending proposals {len(visible_pending)}",
    )

    suppressed_count = int(proposals_diag.get("suppressed_in_review_count") or 0)
    suppressed = [
        proposal for proposal in proposals if proposal.get("suppressed_by_review_group") is True
    ]
    _assert(
        suppressed_count == len(suppressed),
        f"suppressed count {suppressed_count} != suppressed proposals {len(suppressed)}",
    )

    representatives_by_group: dict[str, list[str]] = {}
    for proposal in visible_pending:
        group_key = str(proposal.get("review_group_key") or "").strip()
        if not group_key:
            continue
        representatives_by_group.setdefault(group_key, []).append(str(proposal.get("id") or ""))
        _assert(
            proposal.get("review_group_role") == "representative",
            f"visible grouped proposal {proposal.get('id')} is not marked representative",
        )

    collisions = {
        group_key: ids for group_key, ids in representatives_by_group.items() if len(ids) > 1
    }
    _assert(not collisions, f"multiple visible representatives per group: {collisions}")

    for proposal in suppressed:
        _assert(
            proposal.get("review_group_role") == "suppressed",
            f"suppressed proposal {proposal.get('id')} missing suppressed role",
        )
        _assert(
            str(proposal.get("review_group_key") or "").strip(),
            f"suppressed proposal {proposal.get('id')} missing review_group_key",
        )
        _assert(
            str(proposal.get("status") or "") == "pending",
            f"suppressed proposal {proposal.get('id')} must retain pending status",
        )

    print(f"Visible pending proposals: {len(visible_pending)}")
    print(f"Suppressed in review: {suppressed_count}")


def _assert_house_state_plugin_claimed(summary: dict[str, Any]) -> None:
    plugins = summary.get("plugins", {})
    _assert(isinstance(plugins, dict), "learning_summary.plugins must be a dict")
    house_state = plugins.get("builtin.house_state_contexts")
    _assert(isinstance(house_state, dict), "missing builtin.house_state_contexts plugin summary")
    _assert(
        HOUSE_STATE_PROPOSAL_TYPE in set(house_state.get("proposal_types") or []),
        "house-state lifecycle plugin does not claim house_state_learned_context",
    )

    unclaimed = set(summary.get("unclaimed_proposal_types") or [])
    _assert(
        HOUSE_STATE_PROPOSAL_TYPE not in unclaimed,
        "house_state_learned_context should not be unclaimed after lifecycle registration",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima proposal review grouping live test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()

    client.call_service(
        "heima",
        "command",
        {"command": "learning_run", "target": {"entry_id": entry_id}},
    )

    proposals_diag = _proposal_diagnostics(client, entry_id)
    summary = _learning_summary(client, entry_id)
    _assert_grouping_contract(proposals_diag)
    _assert_house_state_plugin_claimed(summary)

    sensor_count = _sensor_pending_count(client)
    diag_pending = int(proposals_diag.get("pending") or 0)
    _assert(
        sensor_count == diag_pending,
        f"sensor pending count {sensor_count} != diagnostics pending count {diag_pending}",
    )

    print("PASS: proposal review grouping live diagnostics are coherent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
