#!/usr/bin/env python3
"""Live smoke test for the House State learning matrix's Remove action (Phase AW: AW3).

Covers what tests/test_admin_panel.py's static-asset assertions structurally cannot: the real
heima/observability/action review_proposal websocket call reaching the real coordinator ->
ProposalEngine -> ApprovalStore for a house_state_learned_context proposal, exactly as the panel's
Remove button sends it (button[data-action="review_proposal"] reusing the pre-existing
_runAction/_actionPayload — AW3 added no new frontend wiring, only the button's attributes).

Non-destructive: operates on whichever house_state_learned_context proposal is currently accepted
on the test lab (there must be at least one). This test intentionally does not manufacture one by
accepting a pending proposal as setup — unlike reject-then-re-accept on an already-accepted one,
that setup step would leave a proposal that started as "pending" permanently changed. Rejects the
proposal (the action under test), verifies it disappears from the accepted set and would no longer
join into the matrix (mirroring the panel's own _houseStateAcceptedProposalsByContextKey()), then
restores it to accepted in `finally`, regardless of outcome.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_websocket import HAWebSocketClient

HOUSE_STATE_PROPOSAL_PREFIX = "house_state_learned_context:"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _snapshot(ws: HAWebSocketClient) -> dict[str, Any]:
    result = ws.call("heima/observability/snapshot")
    _assert(isinstance(result, dict), f"observability snapshot must be a dict: {type(result)}")
    return result


def _house_state_proposals(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    proposals = snapshot.get("proposals", {}).get("raw", {}).get("proposals", []) or []
    return [
        p
        for p in proposals
        if str(p.get("identity_key") or "").startswith(HOUSE_STATE_PROPOSAL_PREFIX)
    ]


def _accepted_context_keys(snapshot: dict[str, Any]) -> set[str]:
    # Mirrors heima-admin-panel.js's _houseStateAcceptedProposalsByContextKey() exactly.
    keys = set()
    for proposal in _house_state_proposals(snapshot):
        if proposal.get("status") != "accepted":
            continue
        keys.add(str(proposal["identity_key"])[len(HOUSE_STATE_PROPOSAL_PREFIX) :])
    return keys


def _review_proposal(ws: HAWebSocketClient, proposal_id: str, decision: str) -> dict[str, Any]:
    result = ws.call(
        "heima/observability/action",
        action="review_proposal",
        payload={"proposal_id": proposal_id, "decision": decision},
    )
    _assert(
        isinstance(result, dict) and result.get("ok") is True,
        f"review_proposal ({decision}) failed: {result}",
    )
    return result["snapshot"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="House State learning matrix Remove action (Phase AW, AW3) live smoke test"
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        print(
            "Finding a currently-accepted house_state_learned_context proposal to test against..."
        )
        snapshot = _snapshot(ws)
        accepted = [p for p in _house_state_proposals(snapshot) if p.get("status") == "accepted"]
        _assert(
            bool(accepted),
            "no accepted house_state_learned_context proposal found on this test lab — AW3's "
            "Remove action needs at least one to test a real reject-then-restore round trip "
            "against (this test intentionally does not manufacture one from a pending proposal, "
            "since that setup step would not be cleanly reversible). Accept one via the admin "
            "panel or heima/observability/action review_proposal first, then re-run.",
        )
        proposal = accepted[0]
        proposal_id = str(proposal["id"])
        context_key = str(proposal["identity_key"])[len(HOUSE_STATE_PROPOSAL_PREFIX) :]
        print(f"PASS found accepted proposal {proposal_id} (context_key={context_key})")

        try:
            print("Rejecting it via the exact call the panel's Remove button sends...")
            snapshot = _review_proposal(ws, proposal_id, "rejected")
            updated = next(p for p in _house_state_proposals(snapshot) if p["id"] == proposal_id)
            _assert(
                updated.get("status") == "rejected",
                f"expected status=rejected after review_proposal, got {updated.get('status')!r}",
            )
            print(f"PASS proposal {proposal_id} status is now 'rejected'")

            print("Verifying it no longer joins into the matrix's accepted-proposals map...")
            remaining_keys = _accepted_context_keys(snapshot)
            _assert(
                context_key not in remaining_keys,
                f"expected context_key {context_key!r} excluded from accepted proposals after "
                f"reject, still present in {remaining_keys}",
            )
            print("PASS matrix join (_houseStateAcceptedProposalsByContextKey) excludes it")
        finally:
            print(f"Restoring proposal {proposal_id} to 'accepted' (non-destructive cleanup)...")
            snapshot = _review_proposal(ws, proposal_id, "approved")
            restored = next(p for p in _house_state_proposals(snapshot) if p["id"] == proposal_id)
            if restored.get("status") == "accepted":
                print(f"PASS restored proposal {proposal_id} to 'accepted'")
            else:
                print(
                    f"WARN failed to restore proposal {proposal_id} to 'accepted', "
                    f"current status={restored.get('status')!r}",
                    file=sys.stderr,
                )

    print("PASS: House State Remove action (Phase AW, AW3) is live-valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
